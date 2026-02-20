"""OpenCode integration facade.

OpenCode currently reuses the mature Claude integration implementation.
This class exists to provide explicit provider semantics while we keep
compatibility with existing Claude-named internals.
"""

from typing import Optional, cast

from src.claude.monitor import ToolMonitor
from src.claude.facade import ClaudeIntegration
from src.claude.sdk_integration import ClaudeSDKManager
from src.claude.session import SessionManager
from src.config.settings import Settings

from .integration import OpenCodeProcessManager
from .sdk_integration import OpenCodeSDKManager


class OpenCodeIntegration(ClaudeIntegration):
    """Provider facade for OpenCode."""

    def __init__(
        self,
        config: Settings,
        process_manager: Optional[OpenCodeProcessManager] = None,
        sdk_manager: Optional[OpenCodeSDKManager] = None,
        session_manager: Optional[SessionManager] = None,
        tool_monitor: Optional[ToolMonitor] = None,
    ):
        """Initialize OpenCode integration with OpenCode-native managers."""
        process_manager = process_manager or OpenCodeProcessManager(config)

        if config.use_sdk:
            sdk_manager = sdk_manager or OpenCodeSDKManager(config)

        super().__init__(
            config=config,
            process_manager=process_manager,
            sdk_manager=cast(Optional[ClaudeSDKManager], sdk_manager),
            session_manager=session_manager,
            tool_monitor=tool_monitor,
        )
