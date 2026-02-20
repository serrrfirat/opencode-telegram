"""OpenCode SDK manager compatibility wrapper.

OpenCode currently exposes CLI access in this project, so SDK mode reuses the
OpenCode subprocess manager implementation.
"""

from .integration import OpenCodeProcessManager


class OpenCodeSDKManager(OpenCodeProcessManager):
    """SDK-mode compatibility manager for OpenCode provider."""
