from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TransactionType
from app.core.exceptions import NotFoundError
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction


class WalletService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: int) -> Wallet:
        result = await self.db.execute(select(Wallet).where(Wallet.user_id == user_id))
        w = result.scalar_one_or_none()
        if not w:
            raise NotFoundError("Wallet not found")
        return w

    async def top_up(self, user_id: int, amount: Decimal) -> Wallet:
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
