import json
import sqlite3
import uuid
from research_authoring.eval.groundedness_eval import evaluate_claim_groundedness
from research_authoring.db.claim_repository import get_claim, update_claim_eval
from research_authoring.db.artefact_repository import get_latest_artefact, create_artefact_version
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Artefact


def run_eval(db: sqlite3.Connection, *, actor: str, artefact_id: str) -> tuple[Artefact, str]:
    artefact = get_latest_artefact(db, artefact_id)
    if artefact is None:
        raise ValueError(f"Artefact {artefact_id} not found")

    eval_run_id = str(uuid.uuid4())
    all_grounded = True

    for claim_id in artefact.claim_ids:
        claim = get_claim(db, claim_id)
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")

        verdict = evaluate_claim_groundedness(claim_text=claim.text, source_excerpt=claim.source_excerpt)
        update_claim_eval(db, claim.id, verdict["status"], verdict["score"], eval_run_id)
        if verdict["status"] != "grounded":
            all_grounded = False

    updated_artefact = create_artefact_version(
        db, artefact.id, status="pending_approval" if all_grounded else "draft"
    )

    write_audit_entry(
        db,
        actor=actor,
        action="run_eval",
        target_type="artefact",
        target_id=updated_artefact.id,
        target_version=updated_artefact.version,
        eval_run_id=eval_run_id,
        diff=json.dumps({"status": {"from": artefact.status, "to": updated_artefact.status}}),
    )

    return updated_artefact, eval_run_id
