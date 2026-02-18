"""Tests for provider abstraction and OpenCode defaults."""

from src.agent.provider import (
    AgentProvider,
    get_provider_components,
    normalize_provider,
)
from src.opencode import OpenCodeIntegration, OpenCodeProcessManager, OpenCodeSDKManager


def test_normalize_provider_defaults_to_opencode() -> None:
    """Unknown providers should safely fall back to OpenCode."""
    assert normalize_provider("unknown-provider") == AgentProvider.OPENCODE


def test_provider_components_use_opencode_by_default() -> None:
    """OpenCode provider should resolve to OpenCode integration classes."""
    components = get_provider_components(AgentProvider.OPENCODE)

    assert components.integration_cls is OpenCodeIntegration
    assert components.sdk_manager_cls is OpenCodeSDKManager
    assert components.process_manager_cls is OpenCodeProcessManager
