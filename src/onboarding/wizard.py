"""CLI onboarding wizard for OpenCode Telegram bot (Ironclaw-style flow)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class OnboardingAnswers:
    telegram_bot_token: str
    telegram_bot_username: str
    approved_directory: str
    allowed_users: list[int]
    agent_provider: str
    use_sdk: bool


def parse_int_list(raw: str) -> list[int]:
    if not raw.strip():
        return []

    result: list[int] = []
    for part in raw.split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        if not cleaned.isdigit():
            raise ValueError(f"Invalid Telegram user id: {cleaned}")
        result.append(int(cleaned))
    return result


def build_env_map(answers: OnboardingAnswers) -> dict[str, str]:
    return {
        "TELEGRAM_BOT_TOKEN": answers.telegram_bot_token,
        "TELEGRAM_BOT_USERNAME": answers.telegram_bot_username,
        "APPROVED_DIRECTORY": answers.approved_directory,
        "ALLOWED_USERS": ",".join(str(uid) for uid in answers.allowed_users),
        "AGENT_PROVIDER": answers.agent_provider,
        "USE_SDK": "true" if answers.use_sdk else "false",
    }


def write_env_file(path: Path, env_map: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in env_map.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _telegram_get(
    token: str, method: str, params: dict[str, str] | None = None
) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    url = f"https://api.telegram.org/bot{token}/{method}{query}"
    req = Request(url, method="GET")
    with urlopen(req, timeout=20) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
        return cast(dict[str, Any], payload)


def validate_bot_token(token: str) -> tuple[bool, str | None, str | None]:
    try:
        payload = _telegram_get(token, "getMe")
    except Exception as exc:
        return False, None, str(exc)

    if not payload.get("ok"):
        description = payload.get("description", "Token validation failed")
        return False, None, description

    username = payload.get("result", {}).get("username")
    return True, username, None


def extract_first_sender(payload: dict) -> tuple[int, str] | None:
    if not payload.get("ok"):
        return None

    for update in payload.get("result", []):
        msg = update.get("message") or {}
        sender = msg.get("from") or {}
        sender_id = sender.get("id")
        if sender_id is None:
            continue

        username = sender.get("username")
        if username:
            return int(sender_id), f"@{username}"

        first_name = sender.get("first_name") or "unknown"
        return int(sender_id), str(first_name)

    return None


def wait_for_pairing_sender(
    token: str, timeout_seconds: int = 120
) -> tuple[int, str] | None:
    deadline = time.time() + timeout_seconds
    offset: int | None = None

    try:
        _telegram_get(token, "deleteWebhook")
    except Exception:
        # Best effort only. Polling still may work.
        pass

    while time.time() < deadline:
        params = {"timeout": "25", "allowed_updates": '["message"]'}
        if offset is not None:
            params["offset"] = str(offset)

        payload = _telegram_get(token, "getUpdates", params)

        sender = extract_first_sender(payload)
        if sender:
            if payload.get("result"):
                last_id = payload["result"][-1].get("update_id")
                if isinstance(last_id, int):
                    offset = last_id + 1
                    try:
                        _telegram_get(token, "getUpdates", {"offset": str(offset)})
                    except Exception:
                        pass
            return sender

        if payload.get("result"):
            last_id = payload["result"][-1].get("update_id")
            if isinstance(last_id, int):
                offset = last_id + 1

    return None


def _prompt_manual_ids(input_fn: Callable[[str], str]) -> list[int]:
    while True:
        users_raw = input_fn(
            "Allowed Telegram user IDs (comma-separated numeric IDs): "
        ).strip()
        try:
            return parse_int_list(users_raw)
        except ValueError as exc:
            print(f"❌ {exc}")
            print("Tip: usernames are not valid here. Use numeric Telegram IDs only.")


def _prompt_approved_directory(
    input_fn: Callable[[str], str], project_root: Path | None = None
) -> str:
    """Prompt for filesystem access scope and return approved directory."""
    project_root = (project_root or Path.cwd()).resolve()

    print("\nFilesystem access")
    print(
        "1) Sandboxed (recommended): only the current project directory\n"
        "2) Host access: full filesystem (/)"
    )
    print("3) Custom directory")
    scope_choice = input_fn("Select [1/2/3] (default 1): ").strip() or "1"

    if scope_choice == "2":
        warning = (
            "Host access allows the bot to read and run commands across your "
            "entire machine. Type HOST to confirm: "
        )
        if input_fn(warning).strip() == "HOST":
            return str(Path("/").resolve())

        print("⚠️ Host access not confirmed. Using sandboxed mode.")
        return str(project_root)

    if scope_choice == "3":
        while True:
            custom_raw = input_fn(f"Approved directory [{project_root}]: ").strip()
            candidate = Path(custom_raw).expanduser() if custom_raw else project_root
            candidate = candidate.resolve()

            if not candidate.exists():
                print("❌ Directory does not exist.")
                continue

            if not candidate.is_dir():
                print("❌ Path is not a directory.")
                continue

            return str(candidate)

    if scope_choice not in {"1", "2", "3"}:
        print("⚠️ Unknown choice. Using sandboxed mode.")

    return str(project_root)


def prompt_answers(input_fn: Callable[[str], str] = input) -> OnboardingAnswers:
    print("\nTelegram setup")
    print("- Create bot via @BotFather (/newbot)")
    print("- Paste token here")
    print("- Optionally pair this machine by sending /start to your bot")

    while True:
        token = input_fn("Telegram bot token: ").strip()
        ok, detected_username, err = validate_bot_token(token)
        if ok:
            shown = (
                f"@{detected_username}" if detected_username else "(username unknown)"
            )
            print(f"✅ Token validated. Bot: {shown}")
            break
        print(f"❌ Token validation failed: {err}")
        retry = input_fn("Try again? [Y/n]: ").strip().lower()
        if retry in {"n", "no"}:
            raise SystemExit(1)

    suggested_username = (detected_username or "").strip()
    username_prompt = "Telegram bot username (without @)"
    if suggested_username:
        username_prompt += f" [{suggested_username}]"
    username = input_fn(username_prompt + ": ").strip() or suggested_username

    approved_directory = _prompt_approved_directory(input_fn)

    print("\nAccess control")
    print(
        "1) Pair now (recommended): send a DM to your bot and auto-capture your Telegram ID"
    )
    print("2) Enter allowed user IDs manually")
    print("3) Skip (dev mode / allow-all fallback)")
    access_choice = input_fn("Select [1/2/3] (default 1): ").strip() or "1"

    allowed_users: list[int] = []
    if access_choice == "1":
        print("\n📲 Pairing mode")
        print("Send any message (for example /start) to your bot now.")
        print("Waiting up to 120 seconds...")
        try:
            sender = wait_for_pairing_sender(token)
        except Exception as exc:
            sender = None
            print(f"❌ Pairing failed: {exc}")

        if sender:
            user_id, display = sender
            print(f"✅ Paired {display} (ID: {user_id})")
            allowed_users = [user_id]
        else:
            print("⚠️ Pairing timed out. Falling back to manual IDs.")
            allowed_users = _prompt_manual_ids(input_fn)
    elif access_choice == "2":
        allowed_users = _prompt_manual_ids(input_fn)
    else:
        allowed_users = []
        print("⚠️ No allowlist configured. In development this can allow all users.")

    provider = (
        input_fn("Agent provider [opencode/claude] (default opencode): ")
        .strip()
        .lower()
        or "opencode"
    )
    if provider not in {"opencode", "claude"}:
        provider = "opencode"

    use_sdk_raw = input_fn("Use SDK integration? [Y/n]: ").strip().lower()
    use_sdk = use_sdk_raw not in {"n", "no"}

    return OnboardingAnswers(
        telegram_bot_token=token,
        telegram_bot_username=username,
        approved_directory=approved_directory,
        allowed_users=allowed_users,
        agent_provider=provider,
        use_sdk=use_sdk,
    )


def maybe_start_program(input_fn: Callable[[str], str] = input) -> bool:
    start_raw = input_fn("Start bot now? [Y/n]: ").strip().lower()
    return start_raw not in {"n", "no"}


def main() -> int:
    print("🧭 OpenCode Telegram onboarding")
    answers = prompt_answers()
    env_map = build_env_map(answers)
    env_path = Path.cwd() / ".env"
    write_env_file(env_path, env_map)
    print(f"✅ Wrote {env_path}")

    if maybe_start_program():
        print("🚀 Starting bot...")
        return subprocess.call([sys.executable, "-m", "src.main"])

    print("Done. Run: python -m src.main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
