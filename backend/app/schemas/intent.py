from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ApprovedIntentLiteral = Literal[
    "inventory.read",
    "inventory.update",
    "inventory.delete",
    "bills.read",
    "bills.discount",
    "bills.update_status",
    "users.read",
    "users.manage_access",
    "operations.undo",
    "approvals.read",
    "approvals.resolve",
    "unsupported",
]


class IntentExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: ApprovedIntentLiteral
    parameters: Dict[str, Any] = Field(default_factory=dict)
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    extractor_source: str = "gemini"

