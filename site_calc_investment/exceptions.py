# SYNC: This file may be synced between investment and operational clients
"""Custom exceptions for the investment client."""

from typing import Any, Dict, Optional


class SiteCalcError(Exception):
    """Base exception for all Site-Calc client errors."""

    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ApiError(SiteCalcError):
    """General API error."""

    pass


class ValidationError(SiteCalcError):
    """Request validation failed."""

    pass


class AuthenticationError(SiteCalcError):
    """Authentication failed (invalid API key)."""

    pass


class ForbiddenFeatureError(SiteCalcError):
    """Attempted to use a feature not available for this client type.

    Examples:
        - Investment client trying to use ancillary_services
        - Investment client trying to access /optimal-bidding endpoint
    """

    pass


class LimitExceededError(SiteCalcError):
    """Request exceeded client limits.

    Examples:
        - Too many intervals
        - Wrong resolution
        - Request too large
    """

    def __init__(
        self,
        message: str,
        requested: Optional[int] = None,
        max_allowed: Optional[int] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.requested = requested
        self.max_allowed = max_allowed
        super().__init__(message, code, details)


class TimeoutError(SiteCalcError):
    """Request or operation timed out."""

    def __init__(self, message: str, timeout: Optional[float] = None, code: Optional[str] = None):
        self.timeout = timeout
        super().__init__(message, code)


class OptimizationError(SiteCalcError):
    """Optimization solver error.

    Examples:
        - Infeasible problem
        - Unbounded problem
        - Solver timeout
    """

    pass


class JobNotFoundError(SiteCalcError):
    """Job ID not found."""

    pass
