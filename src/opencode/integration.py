"""OpenCode subprocess manager compatibility wrapper."""

from src.claude.integration import ClaudeProcessManager


class OpenCodeProcessManager(ClaudeProcessManager):
    """Subprocess manager for OpenCode provider."""
