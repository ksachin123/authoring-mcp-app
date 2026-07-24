from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import create_artefact
from research_authoring.db.report_repository import (
    create_report,
    get_latest_report,
    get_latest_report_section,
)
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.draft_section import draft_section
from research_authoring.tools.commit_section import commit_section


def test_draft_section_assembles_draft_content_and_claim_ids_from_approved_artefacts(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    artefact = create_artefact(
        db,
        type="thesis_point",
        content="Margin expansion driven by pricing power.",
        claim_ids=["claim-1"],
        status="approved",
        approved_by="analyst-1",
        approved_at="2026-07-24T12:00:00Z",
    )

    draft = draft_section(
        report_id="report-1", section_type="investment_thesis", approved_artefacts=[artefact]
    )

    assert draft["section_type"] == "investment_thesis"
    assert "Margin expansion driven by pricing power." in draft["draft_content"]
    assert draft["claim_ids"] == ["claim-1"]


def test_commit_section_creates_a_new_section_and_appends_it_to_the_report_on_first_commit(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")

    section = commit_section(
        db,
        actor="analyst-1",
        report_id=report.id,
        section_type="investment_thesis",
        content="Margin expansion driven by pricing power.",
        claim_ids=["claim-1"],
    )

    assert section.status == "committed"
    assert section.version == 1

    updated_report = get_latest_report(db, report.id)
    assert updated_report.section_ids == [section.id]

    trail = get_audit_trail_for_target(db, "report_section", section.id)
    assert any(e.action == "commit_section" for e in trail)


def test_commit_section_versions_an_existing_section_without_duplicating_the_report_section_list(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")
    first = commit_section(
        db, actor="analyst-1", report_id=report.id, section_type="investment_thesis",
        content="v1 text", claim_ids=["claim-1"],
    )

    second = commit_section(
        db, actor="analyst-1", report_id=report.id, section_type="investment_thesis",
        content="v2 text, refined", claim_ids=["claim-1", "claim-2"],
        existing_section_id=first.id,
    )

    assert second.id == first.id
    assert second.version == 2

    updated_report = get_latest_report(db, report.id)
    assert updated_report.section_ids == [first.id]
    assert get_latest_report_section(db, first.id).content == "v2 text, refined"


def test_commit_section_raises_and_does_not_persist_a_section_when_report_id_is_nonexistent(tmp_path):
    """Test that commit_section with nonexistent report_id raises ValueError and does NOT persist an orphaned section."""
    db = create_db(str(tmp_path / "test.db"))

    # Count sections before
    count_before = db.execute("SELECT COUNT(*) FROM report_sections").fetchone()[0]

    # Try to commit a section to a nonexistent report
    import pytest
    with pytest.raises(ValueError, match="Report nonexistent-report-id not found"):
        commit_section(
            db,
            actor="analyst-1",
            report_id="nonexistent-report-id",
            section_type="investment_thesis",
            content="some content",
            claim_ids=["claim-1"],
        )

    # Count sections after - should be the same (no orphaned section created)
    count_after = db.execute("SELECT COUNT(*) FROM report_sections").fetchone()[0]
    assert count_before == count_after, f"Expected no section to be created, but count increased from {count_before} to {count_after}"


def test_commit_section_raises_when_existing_section_id_does_not_belong_to_report_id(tmp_path):
    """Test that commit_section raises ValueError when existing_section_id belongs to a different report."""
    db = create_db(str(tmp_path / "test.db"))

    # Create two separate reports
    report1 = create_report(db, "report-1")
    report2 = create_report(db, "report-2")

    # Commit a section to the first report
    section = commit_section(
        db,
        actor="analyst-1",
        report_id=report1.id,
        section_type="investment_thesis",
        content="v1 text",
        claim_ids=["claim-1"],
    )

    # Try to version that section as if it belonged to report2
    import pytest
    with pytest.raises(ValueError, match=f"Section {section.id} does not belong to report {report2.id}"):
        commit_section(
            db,
            actor="analyst-1",
            report_id=report2.id,
            section_type="investment_thesis",
            content="v2 text",
            claim_ids=["claim-1"],
            existing_section_id=section.id,
        )
