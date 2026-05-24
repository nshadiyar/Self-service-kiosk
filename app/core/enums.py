from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    PRISON_ADMIN = "PRISON_ADMIN"
    WAREHOUSE_MANAGER = "WAREHOUSE_MANAGER"
    COURIER = "COURIER"
    INMATE = "INMATE"


class SecurityRegime(str, Enum):
    GENERAL = "GENERAL"
    STRICT = "STRICT"
    MAXIMUM = "MAXIMUM"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PACKING = "PACKING"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    FAILED_DELIVERY = "FAILED_DELIVERY"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class TransactionType(str, Enum):
    TOP_UP = "TOP_UP"
    ORDER_PAYMENT = "ORDER_PAYMENT"
    REFUND = "REFUND"
    MONTHLY_RESET = "MONTHLY_RESET"


class FeedbackType(str, Enum):
    COMPLAINT = "COMPLAINT"
    SUGGESTION = "SUGGESTION"


class FeedbackDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


SPENDING_LIMITS = {
    SecurityRegime.GENERAL: 50000,
    SecurityRegime.STRICT: 25000,
    SecurityRegime.MAXIMUM: 10000,
}
