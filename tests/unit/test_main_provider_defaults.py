"""Tests for OpenCode-default application wiring."""

import pytest

from src.main import create_application
from src.opencode import OpenCodeIntegration


@pytest.mark.asyncio
async def test_create_application_uses_opencode_by_default(tmp_path) -> None:
    """Application should build with OpenCode integration by default."""
    from src.config.settings import Settings

    config = Settings(
        telegram_bot_token="test:token",
        telegram_bot_username="testbot",
        approved_directory=tmp_path,
        development_mode=True,
    )

    app = await create_application(config)
    try:
        assert isinstance(app["agent_integration"], OpenCodeIntegration)
        assert app["claude_integration"] is app["agent_integration"]
    finally:
        await app["storage"].close()
