from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    actor_role: str | None
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    payload_before: dict | None
    payload_after: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
