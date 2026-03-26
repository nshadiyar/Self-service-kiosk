from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import OrderStatus
from app.core.exceptions import NotFoundError, ValidationError, InsufficientFundsError
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.order import OrderCreate


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: UUID) -> Order:
        result = await self.db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.user), selectinload(Order.facility))
        )
        o = result.scalar_one_or_none()
        if not o:
            raise NotFoundError("Order not found")
        return o

    async def list_orders(
        self,
        user_id: UUID | None = None,
        facility_id: UUID | None = None,
        status: OrderStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ):
        q = select(Order).options(selectinload(Order.items), selectinload(Order.user), selectinload(Order.facility))
        if user_id is not None:
            q = q.where(Order.user_id == user_id)
        if facility_id is not None:
            q = q.where(Order.facility_id == facility_id)
        if status is not None:
            q = q.where(Order.status == status)
        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def create(self, user: User, data: OrderCreate) -> Order:
        if not user.facility_id:
            raise ValidationError("User has no facility")
        facility_id = user.facility_id

        total = Decimal(0)
        items_data = []
        for item in data.items:
            result = await self.db.execute(select(Product).where(Product.id == item.product_id))
            product = result.scalar_one_or_none()
            if not product:
                raise NotFoundError(f"Product {item.product_id} not found")
            if product.stock_quantity < item.quantity:
                raise ValidationError(f"Insufficient stock for {product.name}")
            subtotal = product.price * item.quantity
            total += subtotal
            items_data.append((product, item.quantity, subtotal))

        wallet_result = await self.db.execute(select(Wallet).where(Wallet.user_id == user.id))
        wallet = wallet_result.scalar_one_or_none()
        if not wallet:
            raise NotFoundError("Wallet not found")
        if (wallet.balance or 0) < total:
            raise InsufficientFundsError("Insufficient wallet balance")

        order = Order(user_id=user.id, facility_id=facility_id, total_amount=total, status=OrderStatus.PENDING)
        self.db.add(order)
        await self.db.flush()

        for product, qty, subtotal in items_data:
            oi = OrderItem(order_id=order.id, product_id=product.id, quantity=qty, unit_price=product.price, subtotal=subtotal)
            self.db.add(oi)
            product.stock_quantity -= qty

        wallet.balance = (wallet.balance or 0) - total
        wallet.monthly_spent = (wallet.monthly_spent or 0) + total
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order.id)

    async def approve(self, order_id: UUID) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.PENDING:
            raise ValidationError("Order cannot be approved")
        order.status = OrderStatus.APPROVED
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)

    async def reject(self, order_id: UUID, reason: str) -> Order:
        order = await self.get_by_id(order_id)
        if order.status != OrderStatus.PENDING:
            raise ValidationError("Order cannot be rejected")
        order.status = OrderStatus.REJECTED
        order.rejection_reason = reason
        wallet_result = await self.db.execute(select(Wallet).where(Wallet.user_id == order.user_id))
        wallet = wallet_result.scalar_one_or_none()
        if wallet:
            wallet.balance = (wallet.balance or 0) + order.total_amount
            wallet.monthly_spent = (wallet.monthly_spent or 0) - order.total_amount
        await self.db.flush()
        await self.db.refresh(order)
        return await self.get_by_id(order_id)
