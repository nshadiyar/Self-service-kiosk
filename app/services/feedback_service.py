from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import FeedbackDeliveryStatus, FeedbackType, UserRole
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreate


class FeedbackService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, feedback_id: UUID) -> Feedback:
        result = await self.db.execute(
            select(Feedback)
            .where(Feedback.id == feedback_id)
            .options(selectinload(Feedback.user), selectinload(Feedback.facility))
        )
        feedback = result.scalar_one_or_none()
        if feedback is None:
            raise NotFoundError("Обращение не найдено")
        return feedback

    async def create(self, current_user: User, data: FeedbackCreate) -> Feedback:
        feedback = Feedback(
            user_id=current_user.id,
            facility_id=current_user.facility_id,
            type=data.type.value,
            subject=data.subject.strip(),
            message=data.message.strip(),
            recipient_email="SUPER_ADMIN",
            delivery_status=FeedbackDeliveryStatus.SENT.value,
            sent_at=datetime.now(timezone.utc),
            delivery_error=None,
        )
        self.db.add(feedback)
        await self.db.flush()
        await self.db.flush()
        return await self.get_by_id(feedback.id)

    async def list_my(self, current_user: User, skip: int = 0, limit: int = 20) -> list[Feedback]:
        result = await self.db.execute(
            select(Feedback)
            .where(Feedback.user_id == current_user.id)
            .options(selectinload(Feedback.user), selectinload(Feedback.facility))
            .order_by(Feedback.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        current_user: User,
        user_id: UUID | None = None,
        facility_id: UUID | None = None,
        feedback_type: FeedbackType | None = None,
        delivery_status: FeedbackDeliveryStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Feedback]:
        q = (
            select(Feedback)
            .options(selectinload(Feedback.user), selectinload(Feedback.facility))
            .order_by(Feedback.created_at.desc())
        )

        if current_user.role == UserRole.PRISON_ADMIN:
            if not current_user.facility_id:
                raise AuthorizationError("У администратора не указано учреждение")
            q = q.where(Feedback.facility_id == current_user.facility_id)
        elif current_user.role != UserRole.SUPER_ADMIN:
            raise AuthorizationError("Недостаточно прав")

        if user_id is not None:
            q = q.where(Feedback.user_id == user_id)
        if facility_id is not None:
            q = q.where(Feedback.facility_id == facility_id)
        if feedback_type is not None:
            q = q.where(Feedback.type == feedback_type.value)
        if delivery_status is not None:
            q = q.where(Feedback.delivery_status == delivery_status.value)

        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())
