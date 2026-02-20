"""Tests for OpenCode subprocess integration."""

from src.config import create_test_config
from src.opencode.integration import OpenCodeProcessManager


def test_build_command_uses_opencode_cli(monkeypatch, tmp_path) -> None:
    """OpenCode manager should invoke opencode run JSON mode."""
    monkeypatch.setenv("OPENCODE_BINARY_PATH", "/usr/local/bin/opencode-custom")

    config = create_test_config(approved_directory=str(tmp_path))
    manager = OpenCodeProcessManager(config)

    cmd = manager._build_opencode_command(
        prompt="hello world",
        session_id=None,
        continue_session=False,
        working_directory=tmp_path,
    )

    assert cmd[:6] == [
        "/usr/local/bin/opencode-custom",
        "run",
        "--format",
        "json",
        "--dir",
        str(tmp_path),
    ]
    assert "--model" in cmd
    assert config.opencode_model in cmd
    assert cmd[-1] == "hello world"


def test_build_command_uses_session_resume(tmp_path) -> None:
    """OpenCode manager should resume explicit session IDs."""
    config = create_test_config(approved_directory=str(tmp_path))
    manager = OpenCodeProcessManager(config)

    cmd = manager._build_opencode_command(
        prompt="continue",
        session_id="ses_123",
        continue_session=True,
        working_directory=tmp_path,
    )

    assert "--session" in cmd
    assert "ses_123" in cmd
    assert "--continue" not in cmd


def test_parse_stream_event_normalizes_tool_names_and_inputs(tmp_path) -> None:
    """Tool events should map to validator-compatible names and input keys."""
    config = create_test_config(approved_directory=str(tmp_path))
    manager = OpenCodeProcessManager(config)

    event = {
        "type": "tool_use",
        "part": {
            "tool": "read",
            "callID": "call_1",
            "state": {"input": {"filePath": "/tmp/demo.txt"}},
        },
    }

    update = manager._parse_stream_event(event)

    assert update is not None
    assert update.tool_calls is not None
    assert update.tool_calls[0]["name"] == "Read"
    assert update.tool_calls[0]["input"]["path"] == "/tmp/demo.txt"


def test_extract_error_message_prefers_data_message(tmp_path) -> None:
    """Structured OpenCode errors should surface provider message text."""
    config = create_test_config(approved_directory=str(tmp_path))
    manager = OpenCodeProcessManager(config)

    error_event = {
        "type": "error",
        "error": {
            "name": "UnknownError",
            "data": {"message": "Model not found: openai/unknown"},
        },
    }

    expected = "Model not found: openai/unknown"
    assert manager._extract_error_message(error_event) == expected
