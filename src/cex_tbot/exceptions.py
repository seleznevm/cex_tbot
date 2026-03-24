from __future__ import annotations


class GateDemoTransportError(RuntimeError):
    """Base error for Gate demo transport boundary issues."""


class MissingGateDemoApiError(GateDemoTransportError):
    """Raised when demo mode is requested without the required demo credential."""


class GateLiveModeBlockedError(GateDemoTransportError):
    """Raised when a caller attempts to enable an unsupported live Gate mode."""
