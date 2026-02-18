from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.core import ClaudeCodeBot


@pytest.mark.asyncio
async def test_set_bot_commands_retries_on_transient_network_error(monkeypatch):
    settings = SimpleNamespace(
        telegram_token_str="123:abc",
        webhook_url=None,
        webhook_port=0,
        webhook_path="/",
    )
    bot = ClaudeCodeBot(settings=settings, dependencies={})

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("src.bot.core.asyncio.sleep", fake_sleep)

    set_commands = AsyncMock(side_effect=[Exception("connect"), None])
    bot.app = SimpleNamespace(bot=SimpleNamespace(set_my_commands=set_commands))
    bot.orchestrator = SimpleNamespace(
        get_bot_commands=AsyncMock(return_value=[SimpleNamespace(command="start")])
    )

    await bot._set_bot_commands()

    assert set_commands.await_count == 2
    assert sleep_calls == [1]


@pytest.mark.asyncio
async def test_set_bot_commands_raises_after_retry_budget(monkeypatch):
    settings = SimpleNamespace(
        telegram_token_str="123:abc",
        webhook_url=None,
        webhook_port=0,
        webhook_path="/",
    )
    bot = ClaudeCodeBot(settings=settings, dependencies={})

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("src.bot.core.asyncio.sleep", fake_sleep)

    set_commands = AsyncMock(side_effect=Exception("still failing"))
    bot.app = SimpleNamespace(bot=SimpleNamespace(set_my_commands=set_commands))
    bot.orchestrator = SimpleNamespace(
        get_bot_commands=AsyncMock(return_value=[SimpleNamespace(command="start")])
    )

    with pytest.raises(Exception, match="still failing"):
        await bot._set_bot_commands()

    assert set_commands.await_count == 5
    assert sleep_calls == [1, 2, 4, 8]
