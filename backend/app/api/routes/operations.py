from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_context
from app.core.database import get_db
from app.schemas.agent import (
    CancelRequest,
    CancelResponse,
    ConfirmRequest,
    ConfirmResponse,
    PreviewPayload,
    PreviewRequest,
)
from app.schemas.auth import CurrentUserContext
from app.services.operations.common import (
    OperationClarificationError,
    OperationDeniedError,
    OperationNotFoundError,
)
from app.services.preview.confirmation_service import (
    ConfirmationError,
    ConfirmationService,
)

router = APIRouter(prefix="/api/operations", tags=["Operations"])


@router.post("/preview", response_model=PreviewPayload)
def create_operation_preview(
    payload: PreviewRequest,
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> PreviewPayload:
    try:
        preview_data, record, raw_token = ConfirmationService.create_preview(
            db,
            current_user,
            payload.operation,
            payload.parameters,
            payload.raw_user_query or f"[direct_preview:{payload.operation}]",
        )
        return PreviewPayload(
            confirmation_token=raw_token,
            operation=preview_data.operation,
            summary=preview_data.summary,
            affected_rows=preview_data.affected_rows,
            requires_exact_row_count=preview_data.requires_exact_row_count,
            samples=preview_data.samples,
            financial_impact=preview_data.financial_impact,
            resolved_date_range=preview_data.resolved_date_range,
            business_rules_note=preview_data.business_rules_note,
            expires_at=record.expires_at,
        )
    except OperationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.reason) from exc
    except OperationClarificationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.question) from exc
    except OperationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (ConfirmationError, ValidationError, ValueError) as exc:
        msg = exc.message if isinstance(exc, ConfirmationError) else str(exc)
        code = exc.status_code if isinstance(exc, ConfirmationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=msg) from exc


@router.post("/confirm", response_model=ConfirmResponse)
def confirm_operation(
    payload: ConfirmRequest,
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> ConfirmResponse:
    try:
        result = ConfirmationService.confirm_and_execute(
            db,
            current_user,
            payload.confirmation_token,
            exact_row_count=payload.exact_row_count,
        )
        return ConfirmResponse(
            status="confirmed",
            operation=result.operation,
            message=result.message,
            affected_rows=result.affected_rows,
            financial_impact=result.financial_impact,
            before_data=result.before_data,
            after_data=result.after_data,
        )
    except OperationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.reason) from exc
    except ConfirmationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/cancel", response_model=CancelResponse)
def cancel_operation(
    payload: CancelRequest,
    current_user: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> CancelResponse:
    try:
        record = ConfirmationService.cancel_preview(db, current_user, payload.confirmation_token)
        return CancelResponse(
            status="cancelled",
            operation=record.operation,
            message=f"Cancelled pending preview for {record.operation}. No database changes were made.",
        )
    except OperationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.reason) from exc
    except ConfirmationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

