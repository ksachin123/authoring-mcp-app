import sqlite3
from datetime import datetime, timezone
from research_authoring.db.report_repository import (
    get_latest_report,
    get_latest_report_section,
    create_report_version,
)
from research_authoring.db.claim_repository import get_claim
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Report

_SECTION_TITLES = {
    "investment_thesis": "Investment Thesis",
    "valuation": "Valuation",
    "risks": "Risks",
}


def export_report_to_markdown(
    db: sqlite3.Connection, *, actor: str, report_id: str, template_title: str
) -> tuple[str, Report]:
    report = get_latest_report(db, report_id)
    if report is None:
        raise ValueError(f"Report {report_id} not found")
    if report.status != "ready_for_export":
        raise ValueError("Report must be ready_for_export before exporting")

    lines = [f"# {template_title}", ""]
    footnotes = []
    footnote_index = 1

    for section_id in report.section_ids:
        section = get_latest_report_section(db, section_id)
        if section is None:
            raise ValueError(f"Section {section_id} not found")

        lines.append(f"## {_SECTION_TITLES.get(section.section_type, section.section_type)}")
        lines.append("")

        content = section.content
        for claim_id in section.claim_ids:
            claim = get_claim(db, claim_id)
            if claim is None:
                continue
            content += f" [{footnote_index}]"
            footnotes.append(f"[{footnote_index}]: {claim.source_excerpt}")
            footnote_index += 1
        lines.append(content)
        lines.append("")

    if footnotes:
        lines.append("---")
        lines.extend(footnotes)

    markdown = "\n".join(lines)

    exported = create_report_version(
        db, report_id, status="exported",
        exported_at=datetime.now(timezone.utc).isoformat(),
        export_ref=f"markdown:{report_id}",
    )

    write_audit_entry(
        db,
        actor=actor,
        action="export_report",
        target_type="report",
        target_id=exported.id,
        target_version=exported.version,
        eval_run_id=None,
        diff=None,
    )

    return markdown, exported
