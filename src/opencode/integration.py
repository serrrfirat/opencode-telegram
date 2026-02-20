"""OpenCode subprocess management.

Features:
- Async subprocess execution via `opencode run`
- JSON event stream parsing
- Session resume support
- Claude-compatible response objects
"""

import asyncio
import json
import os
import uuid
from asyncio.subprocess import Process
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

import structlog

from src.claude.exceptions import (
    ClaudeParsingError,
    ClaudeProcessError,
    ClaudeTimeoutError,
)
from src.claude.integration import ClaudeProcessManager, ClaudeResponse, StreamUpdate

logger = structlog.get_logger()

_TOOL_NAME_MAP = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "bash": "Bash",
    "glob": "Glob",
    "grep": "Grep",
    "ls": "LS",
    "task": "Task",
    "multiedit": "MultiEdit",
    "notebookread": "NotebookRead",
    "notebookedit": "NotebookEdit",
    "webfetch": "WebFetch",
    "todoread": "TodoRead",
    "todowrite": "TodoWrite",
    "websearch": "WebSearch",
}


class OpenCodeProcessManager(ClaudeProcessManager):
    """Manage OpenCode subprocess execution."""

    StreamCallback = Callable[[StreamUpdate], Optional[Awaitable[None]]]

    async def execute_command(
        self,
        prompt: str,
        working_directory: Path,
        session_id: Optional[str] = None,
        continue_session: bool = False,
        stream_callback: Optional[StreamCallback] = None,
    ) -> ClaudeResponse:
        """Execute OpenCode command and parse JSON stream output."""
        start_time = asyncio.get_event_loop().time()
        timeout_seconds = getattr(
            self.config,
            "opencode_timeout_seconds",
            self.config.claude_timeout_seconds,
        )

        cmd = self._build_opencode_command(
            prompt=prompt,
            session_id=session_id,
            continue_session=continue_session,
            working_directory=working_directory,
        )

        process_id = str(uuid.uuid4())

        logger.info(
            "Starting OpenCode process",
            process_id=process_id,
            working_directory=str(working_directory),
            session_id=session_id,
            continue_session=continue_session,
            model=getattr(self.config, "opencode_model", None),
        )

        try:
            process = await self._start_process(cmd, working_directory)
            self.active_processes[process_id] = process

            result = await asyncio.wait_for(
                self._handle_opencode_output(
                    process,
                    stream_callback,
                    start_time,
                    session_id,
                ),
                timeout=timeout_seconds,
            )

            logger.info(
                "OpenCode process completed successfully",
                process_id=process_id,
                cost=result.cost,
                duration_ms=result.duration_ms,
            )
            return result

        except asyncio.TimeoutError:
            if process_id in self.active_processes:
                self.active_processes[process_id].kill()
                await self.active_processes[process_id].wait()

            logger.error(
                "OpenCode process timed out",
                process_id=process_id,
                timeout_seconds=timeout_seconds,
            )
            raise ClaudeTimeoutError(f"OpenCode timed out after {timeout_seconds}s")

        except Exception as e:
            logger.error(
                "OpenCode process failed",
                process_id=process_id,
                error=str(e),
            )
            raise

        finally:
            if process_id in self.active_processes:
                del self.active_processes[process_id]

    def _build_opencode_command(
        self,
        prompt: str,
        session_id: Optional[str],
        continue_session: bool,
        working_directory: Path,
    ) -> List[str]:
        """Build OpenCode command with arguments."""
        cmd = [
            self._resolve_opencode_binary(),
            "run",
            "--format",
            "json",
            "--dir",
            str(working_directory),
        ]

        model = getattr(self.config, "opencode_model", None)
        if model:
            cmd.extend(["--model", model])

        if continue_session:
            if session_id:
                cmd.extend(["--session", session_id])
            else:
                cmd.append("--continue")

        if prompt:
            cmd.append(prompt)

        logger.debug("Built OpenCode command", command=cmd)
        return cmd

    async def _handle_opencode_output(
        self,
        process: Process,
        stream_callback: Optional[StreamCallback],
        start_time: float,
        fallback_session_id: Optional[str],
    ) -> ClaudeResponse:
        """Parse OpenCode JSON event stream into Claude-compatible response."""
        content_parts: List[str] = []
        tools_used: List[Dict[str, Any]] = []
        assistant_message_ids = set()
        total_cost = 0.0
        current_session_id = fallback_session_id
        event_start_timestamp: Optional[int] = None
        event_end_timestamp: Optional[int] = None
        structured_error: Optional[str] = None
        parse_error_count = 0

        async for line in self._read_stream_bounded(process.stdout):
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                parse_error_count += 1
                logger.debug(
                    "Skipping non-JSON OpenCode output", line_preview=line[:200]
                )
                continue

            if not isinstance(event, dict):
                continue

            event_type = event.get("type")
            timestamp = event.get("timestamp")
            if isinstance(timestamp, int):
                if event_start_timestamp is None:
                    event_start_timestamp = timestamp
                event_end_timestamp = timestamp

            current_session_id = event.get("sessionID") or current_session_id

            if stream_callback:
                update = self._parse_stream_event(event)
                if update:
                    try:
                        callback_result = stream_callback(update)
                        if callback_result is not None:
                            await callback_result
                    except Exception as e:
                        logger.warning(
                            "Stream callback failed",
                            error=str(e),
                            update_type=update.type,
                        )

            if event_type == "text":
                part = event.get("part", {})
                if not isinstance(part, dict):
                    continue

                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    content_parts.append(text)

                message_id = part.get("messageID")
                if isinstance(message_id, str):
                    assistant_message_ids.add(message_id)

            elif event_type == "tool_use":
                tool = self._extract_tool_usage(event)
                if tool:
                    tools_used.append(tool)

            elif event_type == "step_finish":
                part = event.get("part", {})
                if not isinstance(part, dict):
                    continue

                cost = part.get("cost")
                if isinstance(cost, (int, float)):
                    total_cost += float(cost)

            elif event_type == "error":
                structured_error = self._extract_error_message(event)

        return_code = await process.wait()
        stderr_text = ""
        stderr_stream = process.stderr
        if stderr_stream is not None:
            stderr = await stderr_stream.read()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if structured_error:
            raise ClaudeProcessError(structured_error)

        if return_code != 0:
            error_message = stderr_text or f"OpenCode exited with code {return_code}"
            raise ClaudeProcessError(error_message)

        content = "\n".join(content_parts).strip()
        if not content:
            raise ClaudeParsingError("No response content received from OpenCode")

        if parse_error_count:
            logger.warning(
                "OpenCode stream contained non-JSON lines",
                count=parse_error_count,
            )

        duration_ms = self._compute_duration_ms(
            start_time=start_time,
            event_start_timestamp=event_start_timestamp,
            event_end_timestamp=event_end_timestamp,
        )

        final_session_id = (
            current_session_id or fallback_session_id or str(uuid.uuid4())
        )

        return ClaudeResponse(
            content=content,
            session_id=final_session_id,
            cost=total_cost,
            duration_ms=duration_ms,
            num_turns=max(len(assistant_message_ids), 1),
            tools_used=tools_used,
        )

    def _parse_stream_event(self, event: Dict[str, Any]) -> Optional[StreamUpdate]:
        """Map OpenCode event shape into shared StreamUpdate structure."""
        event_type = event.get("type")

        if event_type == "text":
            part = event.get("part", {})
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text:
                    return StreamUpdate(type="assistant", content=text)

        if event_type == "tool_use":
            part = event.get("part", {})
            if not isinstance(part, dict):
                return None

            tool_name = self._normalize_tool_name(part.get("tool"))
            state = part.get("state", {})
            tool_input = {}
            if isinstance(state, dict):
                raw_input = state.get("input", {})
                if isinstance(raw_input, dict):
                    tool_input = self._normalize_tool_input(raw_input)

            return StreamUpdate(
                type="assistant",
                tool_calls=[
                    {
                        "name": tool_name,
                        "input": tool_input,
                        "id": part.get("callID"),
                    }
                ],
            )

        if event_type == "error":
            return StreamUpdate(
                type="error", content=self._extract_error_message(event)
            )

        return None

    def _extract_tool_usage(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract normalized tool usage entry from a tool event."""
        part = event.get("part", {})
        if not isinstance(part, dict):
            return None

        raw_name = part.get("tool")
        if not isinstance(raw_name, str):
            return None

        tool_name = self._normalize_tool_name(raw_name)

        state = part.get("state", {})
        raw_input = state.get("input", {}) if isinstance(state, dict) else {}
        tool_input = self._normalize_tool_input(raw_input) if raw_input else {}

        return {
            "name": tool_name,
            "timestamp": event.get("timestamp"),
            "input": tool_input,
        }

    def _extract_error_message(self, event: Dict[str, Any]) -> str:
        """Extract user-facing error text from an OpenCode error event."""
        error_obj = event.get("error")

        if isinstance(error_obj, dict):
            data = error_obj.get("data")
            if isinstance(data, dict):
                message = data.get("message")
                if isinstance(message, str) and message:
                    return message

            message = error_obj.get("message")
            if isinstance(message, str) and message:
                return message

            name = error_obj.get("name")
            if isinstance(name, str) and name:
                return name

        return "OpenCode returned an unknown error"

    def _compute_duration_ms(
        self,
        start_time: float,
        event_start_timestamp: Optional[int],
        event_end_timestamp: Optional[int],
    ) -> int:
        """Compute duration from event timestamps, falling back to wall-clock."""
        if (
            event_start_timestamp is not None
            and event_end_timestamp is not None
            and event_end_timestamp >= event_start_timestamp
        ):
            return event_end_timestamp - event_start_timestamp

        return int((asyncio.get_event_loop().time() - start_time) * 1000)

    def _resolve_opencode_binary(self) -> str:
        """Resolve OpenCode executable path."""
        return os.environ.get("OPENCODE_BINARY_PATH", "opencode")

    def _normalize_tool_name(self, tool_name: Any) -> str:
        """Normalize OpenCode tool names to Claude-style names."""
        if not isinstance(tool_name, str):
            return "unknown"

        key = tool_name.strip().lower()
        return _TOOL_NAME_MAP.get(key, tool_name)

    def _normalize_tool_input(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize OpenCode camelCase tool inputs for validator compatibility."""
        normalized = dict(tool_input)

        if "filePath" in normalized and "path" not in normalized:
            normalized["path"] = normalized["filePath"]

        if "oldPath" in normalized and "old_path" not in normalized:
            normalized["old_path"] = normalized["oldPath"]

        if "newPath" in normalized and "new_path" not in normalized:
            normalized["new_path"] = normalized["newPath"]

        return normalized
