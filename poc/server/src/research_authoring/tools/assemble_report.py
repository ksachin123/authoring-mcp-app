import sqlite3
from research_authoring.db.report_repository import (
    get_latest_report_section,
    create_report_version,
    get_or_create_default_report,
)
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Report


def assemble_report(db: sqlite3.Connection, *, actor: str, section_order: list[str]) -> Report:
    report = get_or_create_default_report(db)

    if not section_order:
        raise ValueError("section_order must not be empty")

    for section_id in section_order:
        section = get_latest_report_section(db, section_id)
        if section is None or section.status != "committed":
            raise ValueError(f"Section {section_id} is not committed and cannot be assembled")

    updated = create_report_version(db, report.id, section_ids=section_order, status="ready_for_export")

    write_audit_entry(
        db,
        actor=actor,
        action="assemble_report",
        target_type="report",
        target_id=updated.id,
        target_version=updated.version,
        eval_run_id=None,
        diff=None,
    )

    return updated
