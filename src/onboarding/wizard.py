"""Quick CLI onboarding wizard for OpenCode Telegram bot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Callable


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
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


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


def prompt_answers(input_fn: Callable[[str], str] = input) -> OnboardingAnswers:
    token = input_fn("Telegram bot token: ").strip()
    username = input_fn("Telegram bot username (without @): ").strip()

    default_dir = str(Path.cwd())
    approved_directory = (
        input_fn(f"Approved directory [{default_dir}]: ").strip() or default_dir
    )

    users_raw = input_fn("Allowed Telegram user IDs (comma-separated): ").strip()
    allowed_users = parse_int_list(users_raw)

    provider = (input_fn("Agent provider [opencode/claude] (default opencode): ").strip().lower() or "opencode")
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
