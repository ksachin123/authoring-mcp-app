import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.report_repository import (
    create_report,
    get_latest_report,
    create_report_version,
    create_report_section,
    get_latest_report_section,
    create_report_section_version,
)


def test_creates_a_report_and_a_section_versions_both_and_orders_sections(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    report = create_report(db, "equity-initiation-v1")
    assert report.version == 1
    assert report.section_ids == []

    section = create_report_section(
        db,
        report_id=report.id,
        section_type="investment_thesis",
        content="Draft thesis text.",
        claim_ids=["claim-1", "claim-2"],
        status="draft_in_chat",
        committed_by=None,
        committed_at=None,
    )
    assert section.version == 1

    committed_section = create_report_section_version(
        db,
        section.id,
        status="committed",
        committed_by="analyst-1",
        committed_at="2026-07-24T11:00:00Z",
    )
    assert committed_section.version == 2
    assert committed_section.status == "committed"

    report_with_section = create_report_version(db, report.id, section_ids=[section.id])
    assert report_with_section.version == 2
    assert report_with_section.section_ids == [section.id]

    assert get_latest_report(db, report.id) == report_with_section
    assert get_latest_report_section(db, section.id) == committed_section
    db.close()


def test_create_report_version_with_unknown_patch_keys(tmp_path):
    """Test that create_report_version rejects unknown patch keys."""
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")

    with pytest.raises(ValueError, match="Unknown patch field"):
        create_report_version(db, report.id, status="ready_for_export", invalid_field="value")
    db.close()


def test_create_report_version_with_nonexistent_id(tmp_path):
    """Test that create_report_version raises ValueError for nonexistent id."""
    db = create_db(str(tmp_path / "test.db"))

    with pytest.raises(ValueError, match="Report .* not found"):
        create_report_version(db, "nonexistent-id", status="ready_for_export")
    db.close()


def test_create_report_section_version_with_unknown_patch_keys(tmp_path):
    """Test that create_report_section_version rejects unknown patch keys."""
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")
    section = create_report_section(
        db,
        report_id=report.id,
        section_type="investment_thesis",
        content="Draft thesis text.",
        claim_ids=["claim-1"],
        status="draft_in_chat",
        committed_by=None,
        committed_at=None,
    )

    with pytest.raises(ValueError, match="Unknown patch field"):
        create_report_section_version(db, section.id, status="committed", invalid_key="value")
    db.close()


def test_create_report_section_version_with_nonexistent_id(tmp_path):
    """Test that create_report_section_version raises ValueError for nonexistent id."""
    db = create_db(str(tmp_path / "test.db"))

    with pytest.raises(ValueError, match="ReportSection .* not found"):
        create_report_section_version(db, "nonexistent-id", status="committed")
    db.close()


def test_report_versioning_is_append_only(tmp_path):
    """Test that report versioning preserves old versions in the database."""
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")
    v1_id = report.id

    # Create version 2
    v2 = create_report_version(db, v1_id, status="ready_for_export")
    assert v2.version == 2

    # Create version 3
    v3 = create_report_version(db, v1_id, status="exported", exported_at="2026-07-24T12:00:00Z")
    assert v3.version == 3

    # Verify we can still query older versions
    v1_from_db = db.execute(
        "SELECT * FROM reports WHERE id = ? AND version = 1", (v1_id,)
    ).fetchone()
    assert v1_from_db is not None
    assert v1_from_db["version"] == 1
    assert v1_from_db["status"] == "in_progress"

    v2_from_db = db.execute(
        "SELECT * FROM reports WHERE id = ? AND version = 2", (v1_id,)
    ).fetchone()
    assert v2_from_db is not None
    assert v2_from_db["version"] == 2
    assert v2_from_db["status"] == "ready_for_export"

    # Verify get_latest_report returns the most recent version
    latest = get_latest_report(db, v1_id)
    assert latest.version == 3
    assert latest.status == "exported"
    db.close()


def test_report_section_versioning_is_append_only(tmp_path):
    """Test that report section versioning preserves old versions in the database."""
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")
    section = create_report_section(
        db,
        report_id=report.id,
        section_type="investment_thesis",
        content="Original content",
        claim_ids=["claim-1"],
        status="draft_in_chat",
        committed_by=None,
        committed_at=None,
    )
    section_id = section.id

    # Create version 2
    v2 = create_report_section_version(
        db,
        section_id,
        content="Updated content",
        status="committed",
        committed_by="analyst-1",
        committed_at="2026-07-24T11:00:00Z",
    )
    assert v2.version == 2

    # Create version 3
    v3 = create_report_section_version(
        db,
        section_id,
        content="Final content",
        status="approved",
        committed_by="reviewer-1",
    )
    assert v3.version == 3

    # Verify we can still query older versions
    v1_from_db = db.execute(
        "SELECT * FROM report_sections WHERE id = ? AND version = 1", (section_id,)
    ).fetchone()
    assert v1_from_db is not None
    assert v1_from_db["version"] == 1
    assert v1_from_db["status"] == "draft_in_chat"
    assert v1_from_db["content"] == "Original content"

    v2_from_db = db.execute(
        "SELECT * FROM report_sections WHERE id = ? AND version = 2", (section_id,)
    ).fetchone()
    assert v2_from_db is not None
    assert v2_from_db["version"] == 2
    assert v2_from_db["status"] == "committed"
    assert v2_from_db["content"] == "Updated content"

    # Verify get_latest_report_section returns the most recent version
    latest = get_latest_report_section(db, section_id)
    assert latest.version == 3
    assert latest.status == "approved"
    assert latest.content == "Final content"
    db.close()
