import sqlite3
import json
from datetime import datetime, timezone
from research_authoring.db.artefact_repository import get_latest_artefact, create_artefact_version
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Artefact


def approve_artefact(
    db: sqlite3.Connection, *, actor: str, artefact_id: str, decision: str
) -> Artefact:
    if decision not in ("approve", "reject"):
        raise ValueError(f"decision must be 'approve' or 'reject', got {decision!r}")

    current = get_latest_artefact(db, artefact_id)
    if current is None:
        raise ValueError(f"Artefact {artefact_id} not found")
    if current.status != "pending_approval":
        raise ValueError("Artefact is not pending approval")

    approved = decision == "approve"
    now = datetime.now(timezone.utc).isoformat()
    updated = create_artefact_version(
        db,
        current.id,
        status="approved" if approved else "rejected",
        approved_by=actor if approved else current.approved_by,
        approved_at=now if approved else current.approved_at,
    )

    write_audit_entry(
        db,
        actor=actor,
        action="approve_artefact",
        target_type="artefact",
        target_id=updated.id,
        target_version=updated.version,
        eval_run_id=None,
        diff=json.dumps({"status": {"from": current.status, "to": updated.status}}),
    )

    return updated
