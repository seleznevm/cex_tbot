from __future__ import annotations


class GateDemoTransportError(RuntimeError):
    """Base error for Gate demo transport boundary issues."""


class MissingGateDemoApiError(GateDemoTransportError):
    """Raised when demo mode is requested without the required demo credential."""


class GateLiveModeBlockedError(GateDemoTransportError):
    """Raised when a caller attempts to enable an unsupported live Gate mode."""


class GateDemoDependencyError(GateDemoTransportError):
    """Raised when optional HTTP client dependencies for demo transport are unavailable."""


class MissingGateDemoCredentialsError(GateDemoTransportError):
    """Raised when account-level Gate demo actions are requested without full credentials."""
