import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.schemas.intent import IntentExtractionResult

def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "prompts").is_dir():
            return parent
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _find_project_root()
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system_prompt.txt"
FEW_SHOT_PATH = PROJECT_ROOT / "prompts" / "examples" / "few_shot_examples.json"

CATEGORIES_LOWER = {
    "antibiotics": "Antibiotics",
    "antibiotic": "Antibiotics",
    "analgesics": "Analgesics",
    "analgesic": "Analgesics",
    "painkiller": "Analgesics",
    "painkillers": "Analgesics",
    "cardiology": "Cardiology",
    "endocrinology": "Endocrinology",
    "consumables": "Consumables",
    "consumable": "Consumables",
    "vaccines": "Vaccines",
    "vaccine": "Vaccines",
    "iv fluids": "IV Fluids",
    "iv fluid": "IV Fluids",
    "surgical": "Surgical",
}

PERMISSION_ALIASES = {
    "inventory edit": "inventory.update",
    "inventory update": "inventory.update",
    "edit inventory": "inventory.update",
    "update inventory": "inventory.update",
    "inventory.update": "inventory.update",
    "inventory read": "inventory.read",
    "read inventory": "inventory.read",
    "view inventory": "inventory.read",
    "inventory.read": "inventory.read",
    "inventory delete": "inventory.delete",
    "delete inventory": "inventory.delete",
    "inventory.delete": "inventory.delete",
    "bills read": "bills.read",
    "read bills": "bills.read",
    "view bills": "bills.read",
    "bills.read": "bills.read",
    "bills discount": "bills.discount",
    "apply discount": "bills.discount",
    "bills.discount": "bills.discount",
    "bills update status": "bills.update_status",
    "bills.update_status": "bills.update_status",
    "users read": "users.read",
    "users.read": "users.read",
    "manage access": "users.manage_access",
    "users.manage_access": "users.manage_access",
}

ROLE_ALIASES = {
    "admin": "Admin",
    "administrator": "Admin",
    "billing manager": "Billing Manager",
    "pharmacist": "Pharmacist",
    "front desk": "Front Desk",
    "doctor": "Doctor",
}


def _load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return "Extract hospital operations intent into strict JSON."


def _load_few_shot_examples() -> List[Dict[str, Any]]:
    if FEW_SHOT_PATH.exists():
        return json.loads(FEW_SHOT_PATH.read_text(encoding="utf-8"))
    return []


class IntentExtractorService:
    """Extracts structured intents via Google Gemini Structured JSON Outputs, with deterministic local fallback."""

    def __init__(self, gemini_client: Optional[genai.Client] = None):
        self.settings = get_settings()
        self._client = gemini_client
        self.system_prompt = _load_system_prompt()
        self.few_shot_examples = _load_few_shot_examples()

    def _gemini_configured(self) -> bool:
        key = self.settings.GEMINI_API_KEY
        return bool(key) and not key.startswith("your-gemini") and len(key) > 15

    def extract(self, user_query: str) -> IntentExtractionResult:
        if self._client is not None or self._gemini_configured():
            try:
                return self._extract_with_gemini(user_query)
            except Exception:
                # Safe fallback: if external LLM errors, fall back to deterministic parser
                # (never fails open to arbitrary SQL or unchecked execution)
                pass
        return self.extract_deterministic(user_query)

    def _extract_with_gemini(self, user_query: str) -> IntentExtractionResult:
        client = self._client or genai.Client(api_key=self.settings.GEMINI_API_KEY)
        contents: List[types.Content] = []
        for ex in self.few_shot_examples:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=ex["user_query"])],
                )
            )
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=json.dumps(ex["expected"]))],
                )
            )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_query)],
            )
        )

        response = client.models.generate_content(
            model=self.settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        raw_content = response.text or "{}"
        parsed = json.loads(raw_content)
        parsed["extractor_source"] = "gemini"
        return IntentExtractionResult.model_validate(parsed)

    @staticmethod
    def extract_deterministic(user_query: str) -> IntentExtractionResult:
        """Deterministic rule-based intent parser used when Gemini is unconfigured or offline."""
        q = user_query.strip()
        # Ignore embedded prompt-injection phrases when legitimate operational intent is also present
        sanitized = re.sub(
            r"(?:,?\s*where\s+one\s+item'?s\s+name\s+in\s+the\s+db\s+is\s+)?"
            r"ignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules)"
            r"(?:\s+and\s+grant\s+admin\s+to\s+user\s+\d+)?[.,]?\s*",
            " ",
            q,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            r"\b(?:i\s+am|i'm)\s+the\s+admin(?:\s+of\s+[^.?!]+)?[.,]?\s*",
            " ",
            sanitized,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(r"^\s*and\s+", "", sanitized, flags=re.IGNORECASE).strip()
        if sanitized:
            q = sanitized
        ql = q.lower()

        # 0. Reject raw SQL or clearly out-of-scope clinical/scheduling requests immediately
        if re.search(
            r"\b(select\s+.*\s+from|drop\s+table|delete\s+from|insert\s+into|truncate\s+table|alter\s+table)\b",
            ql,
        ) or any(
            oos in ql
            for oos in ("appointment", "diagnosis", "diagnose", "prescribe", "payroll", "salary", "medical record")
        ):
            return IntentExtractionResult(
                intent="unsupported",
                parameters={},
                requires_clarification=False,
                extractor_source="local_deterministic",
            )

        # 0.5 Undo last change (English + Telugu/Hinglish)
        if re.search(
            r"\b(undo|revert|rollback)\b|venakki|wapas\s+karo|pichla\s+change",
            ql,
        ):
            audit_uuid = re.search(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                ql,
            )
            undo_params: Dict[str, Any] = {}
            if audit_uuid:
                undo_params["audit_log_id"] = audit_uuid.group(0)
            return IntentExtractionResult(
                intent="operations.undo",
                parameters=undo_params,
                extractor_source="local_deterministic",
            )

        # 0.6 Approval queue read & resolve (English + Telugu/Hinglish)
        approval_read_kws = (
            "pending approval",
            "pending approvals",
            "pending request",
            "pending requests",
            "approval request",
            "approval requests",
            "approval queue",
            "show approvals",
            "list approvals",
            "view approvals",
            "approved requests",
            "rejected requests",
        )
        is_resolve_verb = bool(
            re.search(r"\b(approve|reject|decline|manjoor)\b|\bdeny\s+(?:the\s+)?(?:pending\s+)?request\b", ql)
        )
        if is_resolve_verb and ("approval" in ql or "request" in ql or "discount" in ql or "#" in ql):
            action = (
                "reject"
                if re.search(r"\b(reject|decline|deny)\b", ql)
                else "approve"
            )
            resolve_params: Dict[str, Any] = {"action": action}
            req_uuid = re.search(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                ql,
            )
            short_m = re.search(r"#([0-9a-f]{6,8})\b", ql)
            if req_uuid:
                resolve_params["request_id"] = req_uuid.group(0)
            elif short_m:
                resolve_params["request_id"] = short_m.group(1)

            req_by_m = re.search(r"(?:from|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", q)
            possessive_m = re.search(r"\b([A-Z][a-z]+)'s\s+(?:pending\s+)?(?:discount\s+)?request", q)
            if req_by_m:
                resolve_params["requester_name"] = req_by_m.group(1).strip()
            elif possessive_m:
                resolve_params["requester_name"] = possessive_m.group(1).strip()

            return IntentExtractionResult(
                intent="approvals.resolve",
                parameters=resolve_params,
                extractor_source="local_deterministic",
            )

        if any(kw in ql for kw in approval_read_kws) or (
            ("approval" in ql or "approvals" in ql)
            and any(w in ql for w in ("show", "list", "view", "check", "chupinchu", "dikhao", "any"))
        ):
            status_val = "PENDING"
            if "all " in ql:
                status_val = "ALL"
            elif "executed" in ql or "approved" in ql:
                status_val = "EXECUTED"
            elif "rejected" in ql:
                status_val = "REJECTED"
            return IntentExtractionResult(
                intent="approvals.read",
                parameters={"status": status_val},
                extractor_source="local_deterministic",
            )

        # 1. Access management / user management
        if any(
            kw in ql
            for kw in (
                "access",
                "permission",
                "role",
                "promote",
                "demote",
                "make me admin",
                "make me an admin",
                "grant ",
                "revoke ",
                "remove ",
                "list users",
                "show users",
                "show all users",
                "all users",
                "all staff",
                "who are the users",
                "employees",
                "staff",
            )
        ):
            # Check users.read first
            if any(
                kw in ql
                for kw in ("list users", "show users", "show all users", "view users", "list staff", "show staff", "who has", "list employees")
            ) and not any(w in ql for w in ("grant", "give", "remove", "revoke", "deny", "delete", "drop", "demote", "make me")):
                role_filter = None
                for alias, canonical in ROLE_ALIASES.items():
                    if alias in ql:
                        role_filter = canonical
                        break
                params: Dict[str, Any] = {"include_permissions": True}
                if role_filter:
                    params["role"] = role_filter
                return IntentExtractionResult(
                    intent="users.read",
                    parameters=params,
                    extractor_source="local_deterministic",
                )

            # Check self-demotion / self-promotion / user access changes
            is_self = any(
                phrase in ql
                for phrase in (
                    "my own",
                    "my admin",
                    "my role",
                    "myself",
                    "make me ",
                    "promote me",
                    "demote me",
                    "remove my ",
                    "delete my ",
                    "revoke my ",
                    "drop my ",
                )
            )
            is_remove = any(
                w in ql
                for w in ("remove", "revoke", "deny", "strip", "take away", "disable", "delete", "drop", "demote")
            )
            is_grant = any(w in ql for w in ("give", "grant", "allow", "add", "promote", "make "))

            matched_perm = None
            for alias, perm_key in PERMISSION_ALIASES.items():
                if alias in ql:
                    matched_perm = perm_key
                    break

            matched_role = None
            for alias, role_name in ROLE_ALIASES.items():
                if re.search(rf"\b{re.escape(alias)}\b", ql):
                    matched_role = role_name
                    break

            # Extract target user name (e.g., "from Ravi", "to Ravi", "for Ravi", or UUID)
            target_user_id = None
            target_user_name = None
            uuid_match = re.search(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                ql,
            )
            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", ql)
            if is_self:
                target_user_name = "self"
            elif uuid_match:
                target_user_id = uuid_match.group(0)
            elif email_match:
                pass
            else:
                name_match = re.search(
                    r"\b(?:from|to|for|user)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
                    q,
                )
                if not name_match:
                    name_match = re.search(
                        r"\b(?:[Gg]ive|[Gg]rant|[Rr]emove|[Rr]evoke|[Dd]eny)\s+([A-Z][a-zA-Z]+)\b",
                        q,
                    )
                if name_match:
                    candidate = name_match.group(1).strip()
                    if candidate.lower() not in ("admin", "inventory", "access", "permission", "role"):
                        target_user_name = candidate

            # Ambiguous access request like "Give Ravi access."
            if (is_grant or is_remove) and not matched_perm and not matched_role:
                who = target_user_name or "the user"
                return IntentExtractionResult(
                    intent="users.manage_access",
                    parameters={"target_user_name": target_user_name} if target_user_name else {},
                    requires_clarification=True,
                    clarification_question=(
                        f"Which specific access, permission, or role should be changed for {who} "
                        "(for example: inventory.read, inventory.update, bills.read, or a role)?"
                    ),
                    extractor_source="local_deterministic",
                )

            if is_remove or is_grant:
                params = {}
                if target_user_id:
                    params["target_user_id"] = target_user_id
                if email_match:
                    params["target_user_email"] = email_match.group(0).lower()
                if target_user_name:
                    params["target_user_name"] = target_user_name

                if matched_perm:
                    params["action"] = "deny_permission" if is_remove else "allow_permission"
                    params["permission_key"] = matched_perm
                elif matched_role:
                    params["action"] = "revoke_role" if is_remove else "grant_role"
                    params["role_name"] = matched_role

                return IntentExtractionResult(
                    intent="users.manage_access",
                    parameters=params,
                    extractor_source="local_deterministic",
                )

        # 2. Billing operations
        if any(
            kw in ql
            for kw in (
                "bill",
                "bills",
                "billu",
                "billuku",
                "invoice",
                "invoices",
                "discount",
                "raiyiti",
                "chhoot",
                "revenue",
            )
        ):
            # Explicit bill deletion is unsupported (no role has bills.delete)
            if re.search(r"\b(?:delete|remove|purge|erase|drop|wipe)\b", ql) and re.search(
                r"\b(?:bill|bills|invoice|invoices)\b", ql
            ):
                return IntentExtractionResult(
                    intent="unsupported",
                    parameters={},
                    requires_clarification=False,
                    clarification_question=(
                        "Deleting bills is not permitted: 'bills.delete' is not supported and no role "
                        "in the permission matrix has bill-deletion access."
                    ),
                    extractor_source="local_deterministic",
                )

            period = IntentExtractorService._extract_period(ql)
            patient_match = re.search(
                r"(?:for patient|patient|bills for)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
                q,
            )
            bill_uuid = re.search(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                ql,
            )

            # Discount (English + Telugu/Hinglish: raiyiti / chhoot)
            if any(w in ql for w in ("discount", "raiyiti", "chhoot")):
                pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", ql)
                if not pct_match:
                    return IntentExtractionResult(
                        intent="bills.discount",
                        parameters={},
                        requires_clarification=True,
                        clarification_question="What discount percentage (0–100%) would you like to apply, and to which bills?",
                        extractor_source="local_deterministic",
                    )
                params = {
                    "discount_percentage": float(pct_match.group(1)),
                    "status_filter": "ALL_ELIGIBLE",
                }
                if period:
                    params["period"] = period
                if bill_uuid:
                    params["bill_id"] = bill_uuid.group(0)
                if patient_match:
                    params["patient_search"] = patient_match.group(1).strip()
                if "pending" in ql:
                    params["status_filter"] = "PENDING"
                return IntentExtractionResult(
                    intent="bills.discount",
                    parameters=params,
                    extractor_source="local_deterministic",
                )

            # Update bill status
            if re.search(r"\b(?:mark|change|update|set)\b.*\bstatus\b|\bmark\b.*\bas\b", ql):
                target_status = None
                status_phrase = re.search(
                    r"\b(?:as|to)\s+(partially_paid|partially paid|cancelled|canceled|refunded|pending|paid)\b",
                    ql,
                )
                if status_phrase:
                    raw_st = status_phrase.group(1).replace(" ", "_").upper()
                    target_status = "CANCELLED" if raw_st == "CANCELED" else raw_st
                else:
                    for st in ("PARTIALLY_PAID", "CANCELLED", "REFUNDED", "PAID", "PENDING"):
                        if st.lower().replace("_", " ") in ql or st.lower() in ql:
                            target_status = st
                            break
                if not target_status:
                    return IntentExtractionResult(
                        intent="bills.update_status",
                        parameters={},
                        requires_clarification=True,
                        clarification_question="Which status should the bills be updated to (PENDING, PAID, PARTIALLY_PAID, CANCELLED, or REFUNDED)?",
                        extractor_source="local_deterministic",
                    )
                params = {"new_status": target_status}
                if bill_uuid:
                    params["bill_id"] = bill_uuid.group(0)
                if patient_match:
                    params["patient_search"] = patient_match.group(1).strip()
                if period:
                    params["period"] = period
                if "pending" in ql and target_status != "PENDING":
                    params["current_status"] = "PENDING"
                return IntentExtractionResult(
                    intent="bills.update_status",
                    parameters=params,
                    extractor_source="local_deterministic",
                )

            # Read bills
            params: Dict[str, Any] = {"filter": "all"}
            if "summary" in ql or "how many" in ql or "total" in ql or "count" in ql:
                params["filter"] = "summary"
            elif "pending" in ql:
                params["filter"] = "pending"
            elif "partially paid" in ql:
                params["filter"] = "partially_paid"
            elif "paid" in ql:
                params["filter"] = "paid"
            elif "cancelled" in ql or "canceled" in ql:
                params["filter"] = "cancelled"
            elif "refunded" in ql:
                params["filter"] = "refunded"
            elif period:
                params["filter"] = "date_range"

            if period:
                params["period"] = period
            if bill_uuid:
                params["bill_id"] = bill_uuid.group(0)
            if patient_match:
                params["patient_search"] = patient_match.group(1).strip()

            return IntentExtractionResult(
                intent="bills.read",
                parameters=params,
                extractor_source="local_deterministic",
            )

        # 3. Inventory operations
        if any(
            kw in ql
            for kw in (
                "inventory",
                "medicine",
                "medicines",
                "mandulu",
                "dawai",
                "dawaiyan",
                "stock",
                "expir",
                "batch",
                "item",
                "items",
                "antibiotic",
                "consumable",
                "analgesic",
                "vaccine",
                "surgical",
                "iv fluid",
                "cardiology",
                "endocrinology",
                "restock",
                "quantity",
                "price",
            )
        ):
            matched_cat = None
            for alias, cat in CATEGORIES_LOWER.items():
                if alias in ql:
                    matched_cat = cat
                    break

            batch_match = re.search(r"\b([A-Z]{2,5}-\d{4}-\d{4})\b", q)
            item_uuid = re.search(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                ql,
            )

            # Delete inventory
            if any(w in ql for w in ("delete ", "remove item", "purge ")):
                params = {}
                if item_uuid:
                    params["item_id"] = item_uuid.group(0)
                if batch_match:
                    params["batch_number"] = batch_match.group(1)
                if matched_cat:
                    params["category"] = matched_cat
                if "expired" in ql:
                    params["filter"] = "expired"
                elif "out of stock" in ql or "zero stock" in ql:
                    params["filter"] = "out_of_stock"
                return IntentExtractionResult(
                    intent="inventory.delete",
                    parameters=params,
                    extractor_source="local_deterministic",
                )

            # Update inventory (English + Telugu/Hinglish)
            if any(
                w in ql
                for w in (
                    "update ",
                    "set ",
                    "increase ",
                    "decrease ",
                    "restock ",
                    "adjust ",
                    "change quantity",
                    "change price",
                    "penchu",
                    "badhao",
                    "tagginchu",
                    "kam karo",
                    "pettu",
                )
            ):
                params: Dict[str, Any] = {}
                set_min_qty = re.search(r"minimum\s+quantity\s+(?:to\s+|of\s+|=\s*)?(\d+)", ql)
                set_qty = (
                    None
                    if set_min_qty
                    else re.search(
                        r"(?:set\s+(?:all\s+\w+\s+)?quantit(?:y|ies)\s+(?:to\s+|of\s+|=\s*)?|(?:with\s+)?quantit(?:y|ies)\s+(?:to\s+|of\s+|=\s*)?|to\s+|ki\s+|ku\s+)(\d+)",
                        ql,
                    )
                )
                inc_qty = re.search(r"(?:increase|add|restock|penchu|badhao)\s+(?:quantity\s+)?(?:by\s+)?(\d+)|(\d+)\s+(?:penchu|badhao)\b", ql)
                dec_qty = re.search(r"(?:decrease|reduce|subtract|tagginchu|kam\s+karo)\s+(?:quantity\s+)?(?:by\s+)?(\d+)|(\d+)\s+(?:tagginchu|kam\s+karo)\b", ql)
                set_price = re.search(r"(?:unit\s+price|price)\s+(?:to\s+)?(\d+(?:\.\d+)?)", ql)

                if set_min_qty:
                    params["set_minimum_quantity"] = int(set_min_qty.group(1))
                elif inc_qty:
                    params["adjust_quantity"] = int(inc_qty.group(1) or inc_qty.group(2))
                elif dec_qty:
                    params["adjust_quantity"] = -int(dec_qty.group(1) or dec_qty.group(2))
                elif set_qty:
                    params["set_quantity"] = int(set_qty.group(1))
                if set_price:
                    params["set_unit_price"] = float(set_price.group(1))

                if item_uuid:
                    params["item_id"] = item_uuid.group(0)
                if batch_match:
                    params["batch_number"] = batch_match.group(1)
                if matched_cat:
                    params["filter"] = "category"
                    params["category"] = matched_cat
                elif "low stock" in ql or "low-stock" in ql:
                    params["filter"] = "low_stock"
                elif "expir" in ql:
                    params["filter"] = "expiring_soon"
                elif any(w in ql for w in ("all inventory", "entire inventory", "all items", "every item", "all stock", "all medicines")):
                    params["filter"] = "all"
                elif not item_uuid and not batch_match:
                    # Try extracting item name before trailing "to <num>" or end of sentence
                    name_m = re.search(
                        r"(?:for|of)\s+([A-Za-z0-9\-\s]{3,40}?)(?:\s+(?:to|by|with)\s+\d+|\s*$)",
                        q,
                        re.IGNORECASE,
                    )
                    if name_m:
                        params["filter"] = "search"
                        params["search"] = name_m.group(1).strip()

                if not any(k in params for k in ("set_quantity", "adjust_quantity", "set_minimum_quantity", "set_unit_price")):
                    return IntentExtractionResult(
                        intent="inventory.update",
                        parameters=params,
                        requires_clarification=True,
                        clarification_question="What exact quantity or price change should be applied, and to which inventory items?",
                        extractor_source="local_deterministic",
                    )

                return IntentExtractionResult(
                    intent="inventory.update",
                    parameters=params,
                    extractor_source="local_deterministic",
                )

            # Read inventory
            params = {"filter": "all"}
            if any(
                kw in ql
                for kw in (
                    "low stock",
                    "low-stock",
                    "running out",
                    "below minimum",
                    "running low",
                    "takkuva stock",
                    "kam stock",
                )
            ):
                params["filter"] = "low_stock"
            elif "out of stock" in ql or "zero stock" in ql or "stock ledu" in ql or "khatam" in ql:
                params["filter"] = "out_of_stock"
            elif "expir" in ql:
                params["filter"] = "expiring_soon"
                days_m = re.search(r"(\d+)\s*(?:days?|rojulu|rojulalo|din)", ql)
                if days_m:
                    params["expiring_days"] = min(max(int(days_m.group(1)), 1), 365)
            elif "summary" in ql or "overview" in ql or "how many" in ql:
                params["filter"] = "summary"
            elif matched_cat:
                params["filter"] = "category"
                params["category"] = matched_cat
            else:
                search_m = re.search(r"(?:find|search|show|check)\s+(?:medicine|medicines|item|items|stock\s+of)\s+(.+)", ql)
                if search_m:
                    term = search_m.group(1).strip().rstrip("?.!")
                    if term not in ("all", "everything", "inventory"):
                        params["filter"] = "search"
                        params["search"] = term

            if matched_cat and params["filter"] != "category":
                params["category"] = matched_cat
            if item_uuid:
                params["item_id"] = item_uuid.group(0)

            return IntentExtractionResult(
                intent="inventory.read",
                parameters=params,
                extractor_source="local_deterministic",
            )

        return IntentExtractionResult(
            intent="unsupported",
            parameters={},
            requires_clarification=False,
            extractor_source="local_deterministic",
        )

    @staticmethod
    def _extract_period(ql: str) -> Optional[str]:
        if any(p in ql for p in ("last month", "previous month", "gata nela", "last nela", "pichle mahine", "pichla mahina")):
            return "last_month"
        if any(p in ql for p in ("this month", "current month", "ee nela", "is mahine", "ye mahina")):
            return "this_month"
        if any(p in ql for p in ("yesterday", "ninna")):
            return "yesterday"
        if any(p in ql for p in ("today", "eeroju", "ee roju", "eroju", "aaj")):
            return "today"
        if any(p in ql for p in ("last 7 days", "past 7 days", "last week", "gata 7 rojulu", "pichle 7 din")):
            return "last_7_days"
        if any(p in ql for p in ("last 30 days", "past 30 days", "gata 30 rojulu", "pichle 30 din")):
            return "last_30_days"
        if any(p in ql for p in ("last 90 days", "past 90 days", "gata 90 rojulu", "pichle 90 din")):
            return "last_90_days"
        return None
