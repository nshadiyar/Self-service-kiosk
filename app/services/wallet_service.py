from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TransactionType, UserRole
from app.core.exceptions import NotFoundError
from app.models.facility import Facility
from app.models.user import User
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.schemas.wallet import InmateWalletResponse


class WalletService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: UUID) -> Wallet:
        result = await self.db.execute(select(Wallet).where(Wallet.user_id == user_id))
        w = result.scalar_one_or_none()
        if not w:
            raise NotFoundError("Wallet not found")
        return w

    async def create_for_user(self, user_id: UUID) -> Wallet:
        """Create an empty wallet for a new user."""
        wallet = Wallet(user_id=user_id)
        self.db.add(wallet)
        await self.db.flush()
        await self.db.refresh(wallet)
        return wallet

    async def top_up(self, user_id: UUID, amount: Decimal) -> Wallet:
        wallet = await self.get_by_user_id(user_id)
        wallet.balance = (wallet.balance or Decimal(0)) + amount
        tx = WalletTransaction(
            wallet_id=wallet.id,
            type=TransactionType.TOP_UP,
            amount=amount,
            balance_after=wallet.balance,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(wallet)
        return wallet

    async def reset_monthly_spending(self) -> None:
        await self.db.execute(text("UPDATE wallets SET monthly_spent = 0.00"))
        await self.db.commit()

    async def list_inmate_wallets(
        self,
        facility_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[InmateWalletResponse]:
        query = (
            select(
                User.id.label("user_id"),
                User.full_name,
                User.iin,
                User.facility_id,
                Facility.name.label("facility_name"),
                Wallet.balance,
                Wallet.monthly_spent,
                Wallet.monthly_limit,
            )
            .join(Wallet, Wallet.user_id == User.id)
            .outerjoin(Facility, Facility.id == User.facility_id)
            .where(User.role == UserRole.INMATE, User.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        if facility_id is not None:
            query = query.where(User.facility_id == facility_id)

        result = await self.db.execute(query)
        rows = result.mappings().all()
        return [InmateWalletResponse(**row) for row in rows]
