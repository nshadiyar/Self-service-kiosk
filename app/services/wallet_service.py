from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SPENDING_LIMITS, SecurityRegime, TransactionType, UserRole
from app.core.exceptions import NotFoundError
from app.models.security_regime_limit import SecurityRegimeLimit
from app.models.facility import Facility
from app.models.user import User
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.schemas.wallet import InmateWalletResponse, SecurityRegimeLimitResponse


class WalletService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: UUID) -> Wallet:
        result = await self.db.execute(select(Wallet).where(Wallet.user_id == user_id))
        w = result.scalar_one_or_none()
        if not w:
            raise NotFoundError("Кошелек не найден")
        return w

    async def get_monthly_limit_for_regime(self, security_regime: SecurityRegime | str) -> Decimal:
        regime_value = security_regime.value if isinstance(security_regime, SecurityRegime) else security_regime
        result = await self.db.execute(
            select(SecurityRegimeLimit).where(SecurityRegimeLimit.security_regime == regime_value)
        )
        record = result.scalar_one_or_none()
        if record:
            return Decimal(record.monthly_limit)
        return Decimal(SPENDING_LIMITS[SecurityRegime(regime_value)])

    async def create_for_user(self, user_id: UUID, security_regime: SecurityRegime | str = SecurityRegime.GENERAL) -> Wallet:
        """Create an empty wallet for a new user."""
        monthly_limit = await self.get_monthly_limit_for_regime(security_regime)
        wallet = Wallet(user_id=user_id, monthly_limit=monthly_limit)
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

    async def update_monthly_limit(self, user_id: UUID, monthly_limit: Decimal | None) -> Wallet:
        wallet = await self.get_by_user_id(user_id)
        wallet.monthly_limit = monthly_limit
        await self.db.flush()
        await self.db.refresh(wallet)
        return wallet

    async def list_security_regime_limits(self) -> list[SecurityRegimeLimitResponse]:
        configured_result = await self.db.execute(select(SecurityRegimeLimit))
        configured = {
            row.security_regime: Decimal(row.monthly_limit)
            for row in configured_result.scalars().all()
        }
        responses: list[SecurityRegimeLimitResponse] = []
        for regime in SecurityRegime:
            responses.append(
                SecurityRegimeLimitResponse(
                    security_regime=regime,
                    monthly_limit=configured.get(regime.value, Decimal(SPENDING_LIMITS[regime])),
                )
            )
        return responses

    async def upsert_security_regime_limit(
        self,
        security_regime: SecurityRegime,
        monthly_limit: Decimal,
    ) -> SecurityRegimeLimitResponse:
        result = await self.db.execute(
            select(SecurityRegimeLimit).where(SecurityRegimeLimit.security_regime == security_regime.value)
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = SecurityRegimeLimit(
                security_regime=security_regime.value,
                monthly_limit=monthly_limit,
            )
            self.db.add(record)
        else:
            record.monthly_limit = monthly_limit

        await self.db.execute(
            text(
                """
                UPDATE wallets w
                SET monthly_limit = :monthly_limit
                FROM users u
                WHERE u.id = w.user_id
                  AND u.role = 'INMATE'
                  AND u.security_regime = :security_regime
                """
            ),
            {
                "monthly_limit": monthly_limit,
                "security_regime": security_regime.value,
            },
        )
        await self.db.flush()
        return SecurityRegimeLimitResponse(
            security_regime=security_regime,
            monthly_limit=monthly_limit,
        )

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
