from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    PRISON_ADMIN = "PRISON_ADMIN"
    INMATE = "INMATE"


class SecurityRegime(str, Enum):
    GENERAL = "GENERAL"
    STRICT = "STRICT"
    MAXIMUM = "MAXIMUM"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class TransactionType(str, Enum):
    TOP_UP = "TOP_UP"
    ORDER_PAYMENT = "ORDER_PAYMENT"
    REFUND = "REFUND"
    MONTHLY_RESET = "MONTHLY_RESET"


SPENDING_LIMITS = {
    SecurityRegime.GENERAL: 50000,
    SecurityRegime.STRICT: 25000,
    SecurityRegime.MAXIMUM: 10000,
}
