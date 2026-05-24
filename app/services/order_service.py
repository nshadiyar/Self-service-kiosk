from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import OrderStatus, UserRole
from app.core.exceptions import (
    InsufficientFundsError,
    NotFoundError,
    SpendingLimitExceededError,
    ValidationError,
)
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.order import OrderCreate
from app.services.wallet_service import WalletService


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: UUID) -> Order:
        result = await self.db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.user),
                selectinload(Order.courier),
                selectinload(Order.facility),
            )
        )
        o = result.scalar_one_or_none()
        if not o:
            raise NotFoundError("Заказ не найден")
        return o

    async def list_orders(
        self,
        user_id: UUID | None = None,
        courier_id: UUID | None = None,
        facility_id: UUID | None = None,
        status: OrderStatus | None = None,
        full_name: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 20,
    ):
        q = select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.user),
            selectinload(Order.courier),
            selectinload(Order.facility),
        )
        if user_id is not None:
            q = q.where(Order.user_id == user_id)
        if courier_id is not None:
            q = q.where(Order.courier_id == courier_id)
        if facility_id is not None:
            q = q.where(Order.facility_id == facility_id)
        if status is not None:
            q = q.where(Order.status == status)
        if full_name is not None and full_name.strip():
            q = q.join(Order.user).where(User.full_name.ilike(f"%{full_name.strip()}%"))
        if date_from is not None:
            start_dt = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
            q = q.where(Order.created_at >= start_dt)
        if date_to is not None:
            end_dt = datetime.combine(date_to + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
            q = q.where(Order.created_at < end_dt)
        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def create(self, user: User, data: OrderCreate) -> Order:
        if not user.facility_id:
            raise ValidationError("У пользователя не указано учреждение")
        facility_id = user.facility_id

        total = Decimal(0)
        wallet_result = await self.db.execute(select(Wallet).where(Wallet.user_id == user.id))
        wallet = wallet_result.scalar_one_or_none()
        if not wallet:
            raise NotFoundError("Кошелек не найден")

        items_data = []
        for item in data.items:
            result = await self.db.execute(select(Product).where(Product.id == item.product_id))
            product = result.scalar_one_or_none()
            if not product:
                raise NotFoundError(f"Товар {item.product_id} не найден")
            if not product.is_active:
                raise ValidationError(f"Товар недоступен: {product.name}")
            if product.facility_id is not None and product.facility_id != facility_id:
                raise ValidationError(f"Товар недоступен для учреждения: {product.name}")
            if product.stock_quantity < item.quantity:
                raise ValidationError(f"Недостаточно товара на складе: {product.name}")
            subtotal = product.price * item.quantity
            total += subtotal
            items_data.append((product.id, item.quantity, product.price, subtotal))

        if (wallet.balance or 0) < total:
            raise InsufficientFundsError("Недостаточно средств на кошельке")
        projected_monthly_spent = (wallet.monthly_spent or 0) + total
        if wallet.monthly_limit is not None and projected_monthly_spent > wallet.monthly_limit:
            raise SpendingLimitExceededError("Превышен месячный лимит расходов")

        order = Order(user_id=user.id, facility_id=facility_id, total_amount=total, status=OrderStatus.PENDING)
        self.db.add(order)
        await self.db.flush()

        for product_id, qty, unit_price, subtotal in items_data:
            oi = OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=qty,
                unit_price=unit_price,
                subtotal=subtotal,
            )
            self.db.add(oi)
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order.id)

    async def approve(self, order_id: UUID) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.PENDING:
            raise ValidationError("Заказ нельзя одобрить")
        await self._validate_order_inventory(order)
        await self._validate_wallet_for_order(order)
        wallet_svc = WalletService(self.db)
        await wallet_svc.apply_order_payment(order.user_id, order.total_amount, order.id)
        order.status = OrderStatus.APPROVED
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def reject(self, order_id: UUID, reason: str) -> Order:
        order = await self.get_by_id(order_id)
        if order.status not in {OrderStatus.PENDING, OrderStatus.APPROVED}:
            raise ValidationError("Заказ нельзя отклонить")
        previous_status = order.status
        order.status = OrderStatus.REJECTED
        order.rejection_reason = reason
        if self._is_wallet_charged(previous_status):
            wallet_svc = WalletService(self.db)
            await wallet_svc.refund_order_payment(order.user_id, order.total_amount, order.id)
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def start_packing(self, order_id: UUID) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.APPROVED:
            raise ValidationError("Заказ нельзя взять в сборку")
        await self._reserve_stock(order)
        order.status = OrderStatus.PACKING
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def assign_courier(self, order_id: UUID, courier_id: UUID) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.PACKING:
            raise ValidationError("Курьера можно назначить только для заказа в сборке")

        courier = await self.db.scalar(select(User).where(User.id == courier_id, User.is_active == True))
        if courier is None:
            raise NotFoundError("Курьер не найден")
        if courier.role != UserRole.COURIER:
            raise ValidationError("Пользователь не является курьером")
        if courier.facility_id is not None and courier.facility_id != order.facility_id:
            raise ValidationError("Курьер не привязан к учреждению заказа")

        order.courier_id = courier.id
        order.status = OrderStatus.READY_FOR_SHIPMENT
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def mark_departed(self, order_id: UUID) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.READY_FOR_SHIPMENT:
            raise ValidationError("Заказ нельзя отметить как выехавший")
        if order.courier_id is None:
            raise ValidationError("Для заказа не назначен курьер")
        order.status = OrderStatus.OUT_FOR_DELIVERY
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def mark_arrived_at_facility(self, order_id: UUID) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.OUT_FOR_DELIVERY:
            raise ValidationError("Заказ нельзя отметить как прибывший в учреждение")
        if order.courier_id is None:
            raise ValidationError("Для заказа не назначен курьер")
        order.status = OrderStatus.ARRIVED_AT_FACILITY
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def deliver(self, order_id: UUID, recipient_employee_name: str) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.ARRIVED_AT_FACILITY:
            raise ValidationError("Заказ нельзя отметить как доставленный")
        if order.courier_id is None:
            raise ValidationError("Для заказа не назначен курьер")
        recipient_employee_name = " ".join(recipient_employee_name.split())
        if not recipient_employee_name:
            raise ValidationError("Необходимо указать ФИО принимающего сотрудника")
        recipient_admin = await self.db.scalar(
            select(User).where(
                User.role == UserRole.PRISON_ADMIN,
                User.is_active == True,
                User.facility_id == order.facility_id,
                func.lower(User.full_name) == recipient_employee_name.lower(),
            )
        )
        if recipient_admin is None:
            raise ValidationError("Указанный принимающий сотрудник не найден среди администраторов учреждения")
        order.recipient_employee_name = recipient_admin.full_name
        order.status = OrderStatus.DELIVERED
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def fail_delivery(self, order_id: UUID, reason: str) -> Order:
        order = await self.get_by_id(order_id)
        if order.status not in {
            OrderStatus.PACKING,
            OrderStatus.READY_FOR_SHIPMENT,
            OrderStatus.OUT_FOR_DELIVERY,
            OrderStatus.ARRIVED_AT_FACILITY,
            OrderStatus.IN_TRANSIT,
        }:
            raise ValidationError("Проблему доставки можно отметить только после начала сборки")

        order.status = OrderStatus.FAILED_DELIVERY
        order.rejection_reason = reason
        await self._restore_stock(order)
        if self._is_wallet_charged(order.status):
            wallet_svc = WalletService(self.db)
            await wallet_svc.refund_order_payment(order.user_id, order.total_amount, order.id)
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def _validate_order_inventory(self, order: Order) -> None:
        for item in order.items:
            product = item.product
            if product is None:
                raise NotFoundError(f"Товар {item.product_id} не найден")
            if not product.is_active:
                raise ValidationError(f"Товар недоступен: {product.name}")
            if product.stock_quantity < item.quantity:
                raise ValidationError(f"Недостаточно товара на складе: {product.name}")

    async def _validate_wallet_for_order(self, order: Order) -> None:
        wallet_result = await self.db.execute(select(Wallet).where(Wallet.user_id == order.user_id))
        wallet = wallet_result.scalar_one_or_none()
        if not wallet:
            raise NotFoundError("Кошелек не найден")
        if (wallet.balance or Decimal(0)) < order.total_amount:
            raise InsufficientFundsError("Недостаточно средств на кошельке")
        projected_monthly_spent = (wallet.monthly_spent or Decimal(0)) + order.total_amount
        if wallet.monthly_limit is not None and projected_monthly_spent > wallet.monthly_limit:
            raise SpendingLimitExceededError("Превышен месячный лимит расходов")

    async def _reserve_stock(self, order: Order) -> None:
        for item in order.items:
            product = item.product
            if product is None:
                result = await self.db.execute(select(Product).where(Product.id == item.product_id))
                product = result.scalar_one_or_none()
            if product is None:
                raise NotFoundError(f"Товар {item.product_id} не найден")
            if product.stock_quantity < item.quantity:
                raise ValidationError(f"Недостаточно товара на складе: {product.name}")
            product.stock_quantity -= item.quantity

    async def _restore_stock(self, order: Order) -> None:
        for item in order.items:
            result = await self.db.execute(select(Product).where(Product.id == item.product_id))
            product = result.scalar_one_or_none()
            if product is not None:
                product.stock_quantity += item.quantity

    @staticmethod
    def _is_wallet_charged(status: OrderStatus) -> bool:
        return status in {
            OrderStatus.APPROVED,
            OrderStatus.PACKING,
            OrderStatus.READY_FOR_SHIPMENT,
            OrderStatus.OUT_FOR_DELIVERY,
            OrderStatus.ARRIVED_AT_FACILITY,
            OrderStatus.IN_TRANSIT,
            OrderStatus.DELIVERED,
            OrderStatus.FAILED_DELIVERY,
        }
