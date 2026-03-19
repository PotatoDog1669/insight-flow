"""Shared provider error types."""

from __future__ import annotations


class ProviderUnavailableError(RuntimeError):
    """Raised when a configured provider is not usable and should not be retried/fallbacked."""

    def __init__(
        self,
        *,
        provider: str,
        reason: str,
        status_code: int | None = None,
        stage: str | None = None,
    ) -> None:
        self.provider = str(provider or "").strip()
        self.reason = str(reason or "").strip() or "provider_unavailable"
        self.status_code = status_code
        self.stage = str(stage or "").strip() or None
        message = self.reason
        if self.status_code is not None:
            message = f"{message} (status_code={self.status_code})"
        super().__init__(message)
