from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_context
from app.core.database import get_db
from app.schemas.agent import AuditLogItem, AuditLogListResponse
from app.schemas.auth import CurrentUserContext
from app.services.audit.audit_service import AuditService
from app.services.operations.common import OperationDeniedError

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=AuditLogListResponse)
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    operation: Optional[str] = Query(default=None),
    execution_status: Optional[str] = Query(default=None),
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    try:
        rows, total_count = AuditService.list_audit_logs(
            db,
            current_user,
            limit=limit,
            offset=offset,
            operation=operation,
            execution_status=execution_status,
        )
        return AuditLogListResponse(
            total_count=total_count,
            items=[
                AuditLogItem(
                    id=r.id,
                    hospital_id=r.hospital_id,
                    user_id=r.user_id,
                    raw_user_query=r.raw_user_query,
                    parsed_intent=r.parsed_intent,
                    operation=r.operation,
                    authorization_result=r.authorization_result,
                    decision_reason=r.decision_reason,
                    affected_rows=r.affected_rows,
                    execution_status=r.execution_status,
                    before_data=r.before_data,
                    after_data=r.after_data,
                    created_at=r.created_at,
                )
                for r in rows
            ],
        )
    except OperationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.reason) from exc

