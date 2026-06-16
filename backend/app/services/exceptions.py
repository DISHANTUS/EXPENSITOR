"""Domain-level service exceptions, translated to HTTP responses by routers."""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for service-layer errors."""


class EmailAlreadyExistsError(ServiceError):
    """Raised when registering an email that already exists."""


class InvalidCredentialsError(ServiceError):
    """Raised on failed authentication (wrong email/password or inactive user)."""


class InvalidTokenError(ServiceError):
    """Raised when a refresh token is invalid, expired, or revoked."""


class UnsupportedCurrencyError(ServiceError):
    """Raised when a base currency is not in the supported currencies table."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Unsupported currency: {code}")


class FieldNotNullableError(ServiceError):
    """Raised when a non-nullable settings field is explicitly set to null."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"Field '{field}' cannot be null")


class ResourceNotFoundError(ServiceError):
    """Raised when a resource does not exist or is not owned by the caller."""

    def __init__(self, resource: str = "Resource") -> None:
        self.resource = resource
        super().__init__(f"{resource} not found")


class CurrencyNotFoundError(ServiceError):
    """Raised when a currency code is not in the supported currencies table."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Currency not found: {code}")


class RateNotAvailableError(ServiceError):
    """Raised when no stored exchange rate can resolve a conversion."""

    def __init__(self, from_currency: str, to_currency: str) -> None:
        self.from_currency = from_currency
        self.to_currency = to_currency
        super().__init__(f"No exchange rate available for {from_currency}->{to_currency}")


class InvalidOperationError(ServiceError):
    """Raised on a business-rule violation (maps to HTTP 422)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
