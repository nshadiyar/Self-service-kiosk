from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.enums import FeedbackDeliveryStatus, FeedbackType
from app.core.security import get_current_user_dep, require_admin
from app.dependencies import get_db
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.audit_service import AuditService
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _to_feedback_response(feedback) -> FeedbackResponse:
    payload = FeedbackResponse.model_validate(feedback).model_dump()
    payload["user_full_name"] = feedback.user.full_name if feedback.user else None
    payload["facility_name"] = feedback.facility.name if feedback.facility else None
    return FeedbackResponse(**payload)


@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    data: FeedbackCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = FeedbackService(db)
    feedback = await svc.create(current_user, data)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="CREATE_FEEDBACK",
        entity_type="feedback",
        entity_id=str(feedback.id),
        summary=f"Создано обращение {feedback.subject}",
        payload_after=_to_feedback_response(feedback).model_dump(mode="json"),
    )
    return _to_feedback_response(feedback)


@router.get("/my", response_model=list[FeedbackResponse])
async def list_my_feedback(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = FeedbackService(db)
    feedback_items = await svc.list_my(current_user, skip=skip, limit=limit)
    return [_to_feedback_response(item) for item in feedback_items]


@router.get("", response_model=list[FeedbackResponse])
async def list_feedback(
    user_id: UUID | None = Query(None),
    facility_id: UUID | None = Query(None),
    feedback_type: FeedbackType | None = Query(None, alias="type"),
    delivery_status: FeedbackDeliveryStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = FeedbackService(db)
    feedback_items = await svc.list_all(
        current_user=current_user,
        user_id=user_id,
        facility_id=facility_id,
        feedback_type=feedback_type,
        delivery_status=delivery_status,
        skip=skip,
        limit=limit,
    )
    return [_to_feedback_response(item) for item in feedback_items]


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = FeedbackService(db)
    feedback = await svc.get_by_id(feedback_id)
    if current_user.role.value == "INMATE" and feedback.user_id != current_user.id:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Доступ запрещен")
    if current_user.role.value == "PRISON_ADMIN" and feedback.facility_id != current_user.facility_id:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Доступ запрещен")
    return _to_feedback_response(feedback)
