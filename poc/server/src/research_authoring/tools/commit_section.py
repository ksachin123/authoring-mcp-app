import sqlite3
from datetime import datetime, timezone
from typing import Optional
from research_authoring.db.report_repository import (
    create_report_section,
    create_report_section_version,
    get_latest_report,
    create_report_version,
)
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import ReportSection


def commit_section(
    db: sqlite3.Connection,
    *,
    actor: str,
    report_id: str,
    section_type: str,
    content: str,
    claim_ids: list[str],
    existing_section_id: Optional[str] = None,
) -> ReportSection:
    now = datetime.now(timezone.utc).isoformat()

    if existing_section_id:
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
        section = create_report_section(
            db,
            report_id=report_id,
            section_type=section_type,
            content=content,
            claim_ids=claim_ids,
            status="committed",
            committed_by=actor,
            committed_at=now,
        )
        report = get_latest_report(db, report_id)
        if report is None:
            raise ValueError(f"Report {report_id} not found")
        create_report_version(db, report_id, section_ids=[*report.section_ids, section.id])

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
