from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, List, Optional


class OperationDeniedError(Exception):
    def __init__(self, reason: str, source: str = "permission_denied"):
        self.reason = reason
        self.source = source
        super().__init__(reason)


class OperationClarificationError(Exception):
    def __init__(self, question: str, options: Optional[List[str]] = None):
        self.question = question
        self.options = options or []
        super().__init__(question)


class OperationNotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class StalePreviewError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class OperationPreviewData:
    operation: str
    summary: str
    affected_rows: int
    requires_exact_row_count: bool
    samples: List[Dict[str, Any]]
    financial_impact: Optional[Dict[str, Any]] = None
    resolved_date_range: Optional[Dict[str, Any]] = None
    business_rules_note: Optional[str] = None
    snapshot_hash: str = ""
    target_ids: List[str] = field(default_factory=list)


@dataclass
class OperationExecutionResult:
    operation: str
    message: str
    affected_rows: int
    before_data: Dict[str, Any]
    after_data: Dict[str, Any]
    financial_impact: Optional[Dict[str, Any]] = None


def compute_snapshot_hash(records_state: List[Any]) -> str:
    serialized = json.dumps(records_state, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

