class BromartException(Exception):
    """Base exception for Bromart API"""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class AuthenticationError(BromartException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(detail, status_code=401)


class AuthorizationError(BromartException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail, status_code=403)


class NotFoundError(BromartException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail, status_code=404)


class ValidationError(BromartException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(detail, status_code=422)


class ConflictError(BromartException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(detail, status_code=409)


class InsufficientFundsError(BromartException):
    def __init__(self, detail: str = "Insufficient wallet balance"):
        super().__init__(detail, status_code=400)


class SpendingLimitExceededError(BromartException):
    def __init__(self, detail: str = "Monthly spending limit exceeded"):
        super().__init__(detail, status_code=400)


class InsufficientStockError(BromartException):
    def __init__(self, detail: str = "Insufficient product stock"):
        super().__init__(detail, status_code=400)
