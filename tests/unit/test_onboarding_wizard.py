from pathlib import Path

import pytest

from src.onboarding.wizard import (
    OnboardingAnswers,
    _prompt_approved_directory,
    build_env_map,
    extract_first_sender,
    parse_int_list,
)


def test_parse_int_list_from_csv() -> None:
    assert parse_int_list("123, 456,789") == [123, 456, 789]


def test_parse_int_list_rejects_non_numeric_values() -> None:
    with pytest.raises(ValueError):
        parse_int_list("123,firat")


def test_extract_first_sender_prefers_username_when_present() -> None:
    payload = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "from": {
                        "id": 123456,
                        "first_name": "Firat",
                        "username": "serrrfirat",
                    }
                },
            }
        ],
    }

    sender = extract_first_sender(payload)

    assert sender == (123456, "@serrrfirat")


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


def test_prompt_approved_directory_defaults_to_sandboxed(tmp_path: Path) -> None:
    responses = iter([""])

    approved_directory = _prompt_approved_directory(
        lambda _: next(responses), project_root=tmp_path
    )

    assert approved_directory == str(tmp_path.resolve())


def test_prompt_approved_directory_supports_host_access(tmp_path: Path) -> None:
    responses = iter(["2", "HOST"])

    approved_directory = _prompt_approved_directory(
        lambda _: next(responses), project_root=tmp_path
    )

    assert approved_directory == str(Path("/").resolve())


def test_prompt_approved_directory_requires_host_confirmation(tmp_path: Path) -> None:
    responses = iter(["2", "nope"])

    approved_directory = _prompt_approved_directory(
        lambda _: next(responses), project_root=tmp_path
    )

    assert approved_directory == str(tmp_path.resolve())
