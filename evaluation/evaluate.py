"""Evaluation script for the 100+ business-case catalog.

Measures:
1. Intent classification accuracy
2. Parameter extraction accuracy
3. Clarification accuracy
4. Unsupported-intent rejection accuracy
5. Authorization & constraint enforcement accuracy
6. Prompt-injection resistance (spoofed identity/role in prompt cannot pass auth)

Run from backend/venv:
    python ../evaluation/evaluate.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import resolve_user_context_by_auth_id
from app.core.database import Base
from app.models import User
from app.registry.operation_registry import OPERATION_REGISTRY
from app.services.intent.validator import IntentValidator
from app.services.llm.intent_extractor import IntentExtractorService
from app.services.permissions.engine import PermissionEngine
from seed.seed_data import seed_database

ROLE_EMAILS = {
    "Admin": "admin.a@metrogeneral.org",
    "Billing Manager": "billing.a@metrogeneral.org",
    "Pharmacist": "pharmacist.a@metrogeneral.org",
    "Front Desk": "frontdesk.a@metrogeneral.org",
    "Doctor": "doctor.a@metrogeneral.org",
}


def run_evaluation() -> int:
    cases_path = ROOT / "evaluation" / "dataset" / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        db_url = f"sqlite:///{tmpdir}/eval.db"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

        with SessionLocal() as db:
            seed_database(db, inventory_per_hospital=620, bills_per_hospital=520)
            user_contexts = {}
            for role_name, email in ROLE_EMAILS.items():
                u = db.scalar(select(User).where(User.email == email))
                user_contexts[role_name] = resolve_user_context_by_auth_id(
                    db, u.auth_user_id, "demo"
                )

            extractor = IntentExtractorService()
            perm_engine = PermissionEngine(db)

            total = len(cases)
            intent_correct = 0
            param_correct = 0
            clarification_correct = 0
            auth_correct = 0
            expected_allowed_count = 0
            expected_denied_count = 0
            false_allows = 0
            false_denies = 0
            failures = []

            for case in cases:
                ctx = user_contexts[case["role"]]
                extraction = extractor.extract(case["query"])
                outcome = IntentValidator.validate(extraction, ctx, case["query"])

                # 1. Intent check
                got_intent = extraction.intent
                if got_intent == case["expected_intent"]:
                    intent_correct += 1
                else:
                    failures.append(f"{case['id']}: intent got={got_intent} exp={case['expected_intent']}")

                # 2. Clarification check
                got_clar = outcome.status == "clarification_required"
                if got_clar == case["expected_clarification"]:
                    clarification_correct += 1
                else:
                    failures.append(
                        f"{case['id']}: clar got={got_clar} ({outcome.status}) exp={case['expected_clarification']}"
                    )

                # 3. Parameter check (subset match on expected_params)
                params_ok = True
                for k, exp_v in case["expected_params"].items():
                    got_v = extraction.parameters.get(k)
                    if str(got_v).lower() != str(exp_v).lower():
                        params_ok = False
                        failures.append(
                            f"{case['id']}: param '{k}' got={got_v!r} exp={exp_v!r}"
                        )
                        break
                if params_ok:
                    param_correct += 1

                # 4. Authorization / security check + false-allow / false-deny tracking
                exp_auth = bool(case["expected_authorized"])
                if exp_auth:
                    expected_allowed_count += 1
                else:
                    expected_denied_count += 1

                if case["expected_intent"] == "unsupported":
                    got_auth = outcome.status == "unsupported"
                    # expected_authorized is False for unsupported cases -> we expect rejection!
                    if got_auth and not exp_auth:
                        auth_correct += 1
                    else:
                        false_allows += 1
                        failures.append(f"{case['id']}: unsupported rejection failed")
                elif case["expected_clarification"]:
                    if outcome.status == "clarification_required":
                        auth_correct += 1
                    else:
                        if exp_auth:
                            false_denies += 1
                        else:
                            false_allows += 1
                        failures.append(f"{case['id']}: clarification did not halt execution")
                elif outcome.status == "valid" and outcome.spec is not None:
                    spec = OPERATION_REGISTRY[outcome.spec.operation_key]
                    vp = outcome.validated_params
                    kwargs = {}
                    if spec.operation_key == "inventory.update":
                        # Full inventory ("all") affects 620 rows (>500 cap)
                        if getattr(vp, "filter", None) == "all":
                            kwargs["requested_rows"] = 620
                        else:
                            kwargs["requested_rows"] = 35
                    elif spec.operation_key == "bills.discount":
                        kwargs["discount_pct"] = Decimal(str(vp.discount_percentage))
                    elif spec.operation_key == "users.manage_access":
                        kwargs["access_action"] = vp.action
                        kwargs["target_role_name"] = vp.role_name
                        kwargs["target_permission_key"] = vp.permission_key
                        if vp.target_user_id == ctx.user_id:
                            kwargs["target_user_id"] = ctx.user_id

                    dec = perm_engine.authorize(ctx, spec.required_permission, **kwargs)
                    if dec.allowed == exp_auth:
                        auth_correct += 1
                    else:
                        if dec.allowed and not exp_auth:
                            false_allows += 1
                        elif not dec.allowed and exp_auth:
                            false_denies += 1
                        failures.append(
                            f"{case['id']}: auth got={dec.allowed} ({dec.reason}) exp={exp_auth}"
                        )
                else:
                    if exp_auth:
                        false_denies += 1
                    failures.append(f"{case['id']}: unexpected outcome status={outcome.status}")

        engine.dispose()

    false_allow_rate = (false_allows / expected_denied_count * 100) if expected_denied_count else 0.0
    false_deny_rate = (false_denies / expected_allowed_count * 100) if expected_allowed_count else 0.0

    print(f"Total Evaluation Cases: {total}")
    print(f"Intent Accuracy:        {intent_correct}/{total} ({intent_correct/total*100:.1f}%)")
    print(f"Parameter Accuracy:     {param_correct}/{total} ({param_correct/total*100:.1f}%)")
    print(f"Clarification Accuracy: {clarification_correct}/{total} ({clarification_correct/total*100:.1f}%)")
    print(f"Authorization/Security: {auth_correct}/{total} ({auth_correct/total*100:.1f}%)")
    print(f"False-Allow Rate:       {false_allows}/{expected_denied_count} ({false_allow_rate:.2f}%)")
    print(f"False-Deny Rate:        {false_denies}/{expected_allowed_count} ({false_deny_rate:.2f}%)")

    if failures:
        print("\nFailures:")
        for f in failures[:20]:
            print(" -", f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_evaluation())

