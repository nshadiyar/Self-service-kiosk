class BromartException(Exception):
    """Base exception for Bromart API"""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class AuthenticationError(BromartException):
    def __init__(self, detail: str = "Ошибка аутентификации"):
        super().__init__(detail, status_code=401)


class AuthorizationError(BromartException):
    def __init__(self, detail: str = "Недостаточно прав"):
        super().__init__(detail, status_code=403)


class NotFoundError(BromartException):
    def __init__(self, detail: str = "Ресурс не найден"):
        super().__init__(detail, status_code=404)


class ValidationError(BromartException):
    def __init__(self, detail: str = "Ошибка валидации"):
        super().__init__(detail, status_code=422)


class ConflictError(BromartException):
    def __init__(self, detail: str = "Конфликт данных"):
        super().__init__(detail, status_code=409)


class InsufficientFundsError(BromartException):
    def __init__(self, detail: str = "Недостаточно средств на кошельке"):
        super().__init__(detail, status_code=400)


class SpendingLimitExceededError(BromartException):
    def __init__(self, detail: str = "Превышен месячный лимит расходов"):
        super().__init__(detail, status_code=400)


class InsufficientStockError(BromartException):
    def __init__(self, detail: str = "Недостаточно товара на складе"):
        super().__init__(detail, status_code=400)
