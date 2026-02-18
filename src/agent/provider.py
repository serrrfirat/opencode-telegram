"""Provider abstraction for agent backends."""

from dataclasses import dataclass
from enum import Enum
from typing import Type

from src.claude.facade import ClaudeIntegration
from src.claude.integration import ClaudeProcessManager
from src.claude.sdk_integration import ClaudeSDKManager
from src.opencode import OpenCodeIntegration, OpenCodeProcessManager, OpenCodeSDKManager


class AgentProvider(str, Enum):
    """Supported agent providers."""

    OPENCODE = "opencode"
    CLAUDE = "claude"


@dataclass(frozen=True)
class ProviderComponents:
    """Provider-specific integration and manager classes."""

    integration_cls: Type[ClaudeIntegration]
    sdk_manager_cls: Type[ClaudeSDKManager]
    process_manager_cls: Type[ClaudeProcessManager]


def normalize_provider(value: str) -> AgentProvider:
    """Normalize provider values with safe OpenCode fallback."""
    candidate = (value or "").strip().lower()

    if candidate == AgentProvider.CLAUDE.value:
        return AgentProvider.CLAUDE
    return AgentProvider.OPENCODE


def get_provider_components(provider: AgentProvider) -> ProviderComponents:
    """Resolve provider-specific implementation classes."""
    if provider == AgentProvider.CLAUDE:
        return ProviderComponents(
            integration_cls=ClaudeIntegration,
            sdk_manager_cls=ClaudeSDKManager,
            process_manager_cls=ClaudeProcessManager,
        )

    return ProviderComponents(
        integration_cls=OpenCodeIntegration,
        sdk_manager_cls=OpenCodeSDKManager,
        process_manager_cls=OpenCodeProcessManager,
    )
