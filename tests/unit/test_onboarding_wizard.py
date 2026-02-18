from pathlib import Path

from src.onboarding.wizard import OnboardingAnswers, build_env_map, parse_int_list


def test_parse_int_list_from_csv() -> None:
    assert parse_int_list("123, 456,789") == [123, 456, 789]


def test_build_env_map_contains_required_fields(tmp_path: Path) -> None:
    answers = OnboardingAnswers(
        telegram_bot_token="123:ABC",
        telegram_bot_username="mybot",
        approved_directory=str(tmp_path),
        allowed_users=[111, 222],
        agent_provider="opencode",
        use_sdk=True,
    )

    env_map = build_env_map(answers)

    assert env_map["TELEGRAM_BOT_TOKEN"] == "123:ABC"
    assert env_map["TELEGRAM_BOT_USERNAME"] == "mybot"
    assert env_map["APPROVED_DIRECTORY"] == str(tmp_path)
    assert env_map["ALLOWED_USERS"] == "111,222"
    assert env_map["AGENT_PROVIDER"] == "opencode"
    assert env_map["USE_SDK"] == "true"
