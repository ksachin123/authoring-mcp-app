import sqlite3
from research_authoring.eval.claim_extractor import extract_claims
from research_authoring.db.claim_repository import create_claim
from research_authoring.db.artefact_repository import create_artefact
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Artefact, Source


def synthesize_artefact(
    db: sqlite3.Connection,
    *,
    actor: str,
    type: str,
    generated_text: str,
    source: Source,
) -> Artefact:
    extracted = extract_claims(generated_text=generated_text, source_excerpt=source.raw_content_ref)

    claims = [
        create_claim(
            db,
            text=c["text"],
            source_id=source.id,
            source_excerpt=c["source_excerpt"],
            eval_status="pending",
            eval_score=None,
            eval_run_id=None,
        )
        for c in extracted
    ]

    artefact = create_artefact(
        db,
        type=type,
        content=generated_text,
        claim_ids=[c.id for c in claims],
        status="draft",
        approved_by=None,
        approved_at=None,
    )

    write_audit_entry(
        db,
        actor=actor,
        action="synthesize_artefact",
        target_type="artefact",
        target_id=artefact.id,
        target_version=artefact.version,
        eval_run_id=None,
        diff=None,
    )

    return artefact
