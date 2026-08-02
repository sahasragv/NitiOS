"""Framework-independent application exception definitions."""


class BaseApplicationException(Exception):
    """Base exception for expected NitiOS application failures.

    Subclasses can provide domain-specific defaults while preserving a consistent
    error message, machine-readable code, and HTTP status mapping.
    """

    def __init__(self, message: str, error_code: str, status_code: int) -> None:
        """Initialize an application exception.

        Args:
            message: Human-readable explanation of the failure.
            error_code: Stable, machine-readable identifier for the failure.
            status_code: HTTP status code used by transport adapters.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
