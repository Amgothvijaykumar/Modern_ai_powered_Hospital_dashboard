from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


class PreviewPayload(BaseModel):
    confirmation_token: str
    operation: str
    summary: str
    affected_rows: int
    requires_exact_row_count: bool
    samples: List[Dict[str, Any]]
    financial_impact: Optional[Dict[str, Any]] = None
    resolved_date_range: Optional[Dict[str, Any]] = None
    business_rules_note: Optional[str] = None
    expires_at: datetime


class AgentChatResponse(BaseModel):
    status: str  # completed | preview_required | clarification_required | denied | unsupported | invalid | not_found
    message: str
    intent: Optional[str] = None
    operation: Optional[str] = None
    extractor_source: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    preview: Optional[PreviewPayload] = None
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[str]] = None
    audit_id: Optional[uuid.UUID] = None


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    raw_user_query: Optional[str] = None


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation_token: str = Field(min_length=10)
    exact_row_count: Optional[int] = Field(default=None, ge=0)


class ConfirmResponse(BaseModel):
    status: str
    operation: str
    message: str
    affected_rows: int
    financial_impact: Optional[Dict[str, Any]] = None
    before_data: Dict[str, Any]
    after_data: Dict[str, Any]


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation_token: str = Field(min_length=10)


class CancelResponse(BaseModel):
    status: str
    operation: str
    message: str


class AuditLogItem(BaseModel):
    id: uuid.UUID
    hospital_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    raw_user_query: str
    parsed_intent: Optional[Dict[str, Any]]
    operation: Optional[str]
    authorization_result: str
    decision_reason: str
    affected_rows: Optional[int]
    execution_status: str
    before_data: Optional[Dict[str, Any]]
    after_data: Optional[Dict[str, Any]]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total_count: int
    items: List[AuditLogItem]

