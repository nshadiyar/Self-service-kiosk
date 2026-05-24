from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import FeedbackDeliveryStatus, FeedbackType


class FeedbackCreate(BaseModel):
    type: FeedbackType
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=5000)


class FeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_full_name: str | None = None
    facility_id: UUID | None
    facility_name: str | None = None
    type: FeedbackType
    subject: str
    message: str
    recipient_email: str
    delivery_status: FeedbackDeliveryStatus
    delivery_error: str | None
    sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
