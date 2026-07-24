import sqlite3
from datetime import datetime, timezone
from typing import Optional
from research_authoring.db.report_repository import (
    create_report_section,
    create_report_section_version,
    get_latest_report_section,
    create_report_version,
    get_or_create_default_report,
)
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.artefact_repository import get_latest_artefact
from research_authoring.db.types import ReportSection


def commit_section(
    db: sqlite3.Connection,
    *,
    actor: str,
    section_type: str,
    content: str,
    claim_ids: list[str],
    approved_artefact_ids: list[str],
    existing_section_id: Optional[str] = None,
) -> ReportSection:
    now = datetime.now(timezone.utc).isoformat()

    # Enforce the approval gate at commit_section (not only at ingest), so a
    # claim can't be laundered into a committed section by carrying it forward
    # from a draft/rejected artefact or a typo'd claim id.
    valid_claim_ids: set[str] = set()
    for artefact_id in approved_artefact_ids:
        artefact = get_latest_artefact(db, artefact_id)
        if artefact is None:
            raise ValueError(f"Artefact {artefact_id} not found")
        if artefact.status != "approved":
            raise ValueError(f"Artefact {artefact_id} is not approved (status: {artefact.status})")
        valid_claim_ids.update(artefact.claim_ids)

    for claim_id in claim_ids:
        if claim_id not in valid_claim_ids:
            raise ValueError(f"Claim {claim_id} is not part of any approved artefact in approved_artefact_ids")

    if existing_section_id:
        current_section = get_latest_report_section(db, existing_section_id)
        if current_section is None:
            raise ValueError(f"Section {existing_section_id} not found")

        section = create_report_section_version(
            db,
            existing_section_id,
            content=content,
            claim_ids=claim_ids,
            status="committed",
            committed_by=actor,
            committed_at=now,
        )
    else:
        # This POC has one implicit report per session, auto-created here on
        # first commit -- see get_or_create_default_report.
        report = get_or_create_default_report(db)

        section = create_report_section(
            db,
            report_id=report.id,
            section_type=section_type,
            content=content,
            claim_ids=claim_ids,
            status="committed",
            committed_by=actor,
            committed_at=now,
        )
        create_report_version(db, report.id, section_ids=[*report.section_ids, section.id])

    write_audit_entry(
        db,
        actor=actor,
        action="commit_section",
        target_type="report_section",
        target_id=section.id,
        target_version=section.version,
        eval_run_id=None,
        diff=None,
    )

    return section
