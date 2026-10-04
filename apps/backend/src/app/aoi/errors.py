from __future__ import annotations


class AoiValidationError(ValueError):
    """Input rejected. `code` is stable and shown to clients; `message` explains why."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
