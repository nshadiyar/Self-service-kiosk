from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        *,
        actor: User | None,
        action: str,
        entity_type: str,
        entity_id: str | None,
        summary: str,
        payload_before: Mapping[str, Any] | None = None,
        payload_after: Mapping[str, Any] | None = None,
    ) -> AuditLog:
        record = AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_role=actor.role.value if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            payload_before=dict(payload_before) if payload_before is not None else None,
            payload_after=dict(payload_after) if payload_after is not None else None,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_events(
        self,
        *,
        actor_user_id=None,
        actor_role: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        if actor_user_id is not None:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        if actor_role is not None:
            query = query.where(AuditLog.actor_role == actor_role)
        if action is not None:
            query = query.where(AuditLog.action == action)
        if entity_type is not None:
            query = query.where(AuditLog.entity_type == entity_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_event(self, event_id) -> AuditLog | None:
        result = await self.db.execute(select(AuditLog).where(AuditLog.id == event_id))
        return result.scalar_one_or_none()
