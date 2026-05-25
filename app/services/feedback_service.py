from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.enums import FeedbackDeliveryStatus, FeedbackType, UserRole
from app.core.exceptions import AuthorizationError, BromartException, NotFoundError, ValidationError
from app.models.feedback import Feedback
from app.models.facility import Facility
from app.models.user import User
from app.schemas.feedback import FeedbackCreate
from app.services.email_service import EmailService


class FeedbackService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()

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
        recipient_email = await self._resolve_feedback_recipient_email()
        facility_name = await self._resolve_facility_name(current_user.facility_id)

        feedback = Feedback(
            user_id=current_user.id,
            facility_id=current_user.facility_id,
            type=data.type.value,
            subject=data.subject.strip(),
            message=data.message.strip(),
            recipient_email=recipient_email,
            delivery_status=FeedbackDeliveryStatus.PENDING.value,
        )
        self.db.add(feedback)
        await self.db.flush()

        email_subject = f"{settings.feedback_subject_prefix}: {self._type_label(data.type)}"
        email_body = self._build_email_body(
            current_user=current_user,
            data=data,
            facility_name=facility_name,
        )

        try:
            await self.email_service.send_feedback_email(
                to_email=recipient_email,
                subject=email_subject,
                body=email_body,
            )
            feedback.delivery_status = FeedbackDeliveryStatus.SENT.value
            feedback.sent_at = datetime.now(timezone.utc)
            feedback.delivery_error = None
        except Exception as exc:
            feedback.delivery_status = FeedbackDeliveryStatus.FAILED.value
            feedback.delivery_error = str(exc)[:1000]
            await self.db.flush()
            raise BromartException("Не удалось отправить обращение на электронную почту", status_code=500)

        await self.db.flush()
        return await self.get_by_id(feedback.id)

    async def _resolve_feedback_recipient_email(self) -> str:
        result = await self.db.execute(
            select(User.email)
            .where(User.role == UserRole.SUPER_ADMIN, User.is_active == True)
            .order_by(User.created_at.asc())
        )
        emails = [email for email in result.scalars().all() if email]
        if emails:
            return emails[0]
        if settings.feedback_recipient_email:
            return settings.feedback_recipient_email
        raise ValidationError("Не найден активный SUPER_ADMIN для получения обращений")

    async def _resolve_facility_name(self, facility_id: UUID | None) -> str:
        if facility_id is None:
            return "Не указано"
        result = await self.db.execute(select(Facility.name).where(Facility.id == facility_id))
        facility_name = result.scalar_one_or_none()
        return facility_name or "Не указано"

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

    @staticmethod
    def _type_label(feedback_type: FeedbackType) -> str:
        return "Жалоба" if feedback_type == FeedbackType.COMPLAINT else "Предложение"

    def _build_email_body(self, *, current_user: User, data: FeedbackCreate, facility_name: str) -> str:
        return (
            f"Тип обращения: {self._type_label(data.type)}\n"
            f"Пользователь: {current_user.full_name}\n"
            f"Email: {current_user.email}\n"
            f"Роль: {current_user.role.value}\n"
            f"Учреждение: {facility_name}\n"
            f"ID пользователя: {current_user.id}\n"
            f"\n"
            f"Тема: {data.subject.strip()}\n"
            f"\n"
            f"Текст обращения:\n{data.message.strip()}\n"
        )
