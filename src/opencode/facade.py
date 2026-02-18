"""OpenCode integration facade.

OpenCode currently reuses the mature Claude integration implementation.
This class exists to provide explicit provider semantics while we keep
compatibility with existing Claude-named internals.
"""

from src.claude.facade import ClaudeIntegration


class OpenCodeIntegration(ClaudeIntegration):
    """Provider facade for OpenCode."""
