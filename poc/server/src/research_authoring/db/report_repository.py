import sqlite3
import json
import uuid
from typing import Optional
from .types import Report, ReportSection


def _row_to_report(row: sqlite3.Row) -> Report:
    return Report(
        id=row["id"],
        version=row["version"],
        template_id=row["template_id"],
        section_ids=json.loads(row["section_ids"]),
        status=row["status"],
        exported_at=row["exported_at"],
        export_ref=row["export_ref"],
    )


def _insert_report_row(db: sqlite3.Connection, report: Report) -> None:
    db.execute(
        """INSERT INTO reports (id, version, template_id, section_ids, status, exported_at, export_ref)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            report.id,
            report.version,
            report.template_id,
            json.dumps(report.section_ids),
            report.status,
            report.exported_at,
            report.export_ref,
        ),
    )
    db.commit()


def create_report(db: sqlite3.Connection, template_id: str) -> Report:
    report = Report(
        id=str(uuid.uuid4()),
        version=1,
        template_id=template_id,
        section_ids=[],
        status="in_progress",
        exported_at=None,
        export_ref=None,
    )
    _insert_report_row(db, report)
    return report


def get_latest_report(db: sqlite3.Connection, id: str) -> Optional[Report]:
    row = db.execute(
        "SELECT * FROM reports WHERE id = ? ORDER BY version DESC LIMIT 1", (id,)
    ).fetchone()
    return _row_to_report(row) if row else None


def create_report_version(db: sqlite3.Connection, id: str, **patch) -> Report:
    allowed_fields = {"section_ids", "status", "exported_at", "export_ref"}
    unknown_keys = set(patch.keys()) - allowed_fields
    if unknown_keys:
        raise ValueError(f"Unknown patch field(s): {sorted(unknown_keys)}")

    current = get_latest_report(db, id)
    if current is None:
        raise ValueError(f"Report {id} not found")
    next_report = Report(
        id=current.id,
        version=current.version + 1,
        template_id=current.template_id,
        section_ids=patch.get("section_ids", current.section_ids),
        status=patch.get("status", current.status),
        exported_at=patch.get("exported_at", current.exported_at),
        export_ref=patch.get("export_ref", current.export_ref),
    )
    _insert_report_row(db, next_report)
    return next_report


def _row_to_section(row: sqlite3.Row) -> ReportSection:
    return ReportSection(
        id=row["id"],
        version=row["version"],
        report_id=row["report_id"],
        section_type=row["section_type"],
        content=row["content"],
        claim_ids=json.loads(row["claim_ids"]),
        status=row["status"],
        committed_by=row["committed_by"],
        committed_at=row["committed_at"],
    )


def _insert_section_row(db: sqlite3.Connection, section: ReportSection) -> None:
    db.execute(
        """INSERT INTO report_sections
           (id, version, report_id, section_type, content, claim_ids, status, committed_by, committed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            section.id,
            section.version,
            section.report_id,
            section.section_type,
            section.content,
            json.dumps(section.claim_ids),
            section.status,
            section.committed_by,
            section.committed_at,
        ),
    )
    db.commit()


def create_report_section(
    db: sqlite3.Connection,
    *,
    report_id: str,
    section_type: str,
    content: str,
    claim_ids: list[str],
    status: str,
    committed_by: Optional[str],
    committed_at: Optional[str],
) -> ReportSection:
    section = ReportSection(
        id=str(uuid.uuid4()),
        version=1,
        report_id=report_id,
        section_type=section_type,
        content=content,
        claim_ids=claim_ids,
        status=status,
        committed_by=committed_by,
        committed_at=committed_at,
    )
    _insert_section_row(db, section)
    return section


def get_latest_report_section(db: sqlite3.Connection, id: str) -> Optional[ReportSection]:
    row = db.execute(
        "SELECT * FROM report_sections WHERE id = ? ORDER BY version DESC LIMIT 1", (id,)
    ).fetchone()
    return _row_to_section(row) if row else None


def create_report_section_version(db: sqlite3.Connection, id: str, **patch) -> ReportSection:
    allowed_fields = {"content", "claim_ids", "status", "committed_by", "committed_at"}
    unknown_keys = set(patch.keys()) - allowed_fields
    if unknown_keys:
        raise ValueError(f"Unknown patch field(s): {sorted(unknown_keys)}")

    current = get_latest_report_section(db, id)
    if current is None:
        raise ValueError(f"ReportSection {id} not found")
    next_section = ReportSection(
        id=current.id,
        version=current.version + 1,
        report_id=current.report_id,
        section_type=current.section_type,
        content=patch.get("content", current.content),
        claim_ids=patch.get("claim_ids", current.claim_ids),
        status=patch.get("status", current.status),
        committed_by=patch.get("committed_by", current.committed_by),
        committed_at=patch.get("committed_at", current.committed_at),
    )
    _insert_section_row(db, next_section)
    return next_section
