import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import create_artefact
from research_authoring.db.report_repository import (
    get_or_create_default_report,
    get_latest_report_section,
)
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.draft_section import draft_section
from research_authoring.tools.commit_section import commit_section


def _make_approved_artefact(db, claim_ids):
    return create_artefact(
        db, type="thesis_point", content="x", claim_ids=claim_ids, status="approved",
        approved_by="analyst-1", approved_at="2026-07-24T12:00:00Z",
    )


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

    draft = draft_section(section_type="investment_thesis", approved_artefacts=[artefact])

    assert draft["section_type"] == "investment_thesis"
    assert "Margin expansion driven by pricing power." in draft["draft_content"]
    assert draft["claim_ids"] == ["claim-1"]


def test_commit_section_auto_creates_the_default_report_and_appends_the_section_on_first_commit(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    artefact = _make_approved_artefact(db, ["claim-1"])

    section = commit_section(
        db,
        actor="analyst-1",
        section_type="investment_thesis",
        content="Margin expansion driven by pricing power.",
        claim_ids=["claim-1"],
        approved_artefact_ids=[artefact.id],
    )

    assert section.status == "committed"
    assert section.version == 1

    report = get_or_create_default_report(db)
    assert report.section_ids == [section.id]

    trail = get_audit_trail_for_target(db, "report_section", section.id)
    assert any(e.action == "commit_section" for e in trail)


def test_commit_section_reuses_the_same_default_report_across_multiple_commits(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    artefact = _make_approved_artefact(db, ["claim-1"])

    first = commit_section(
        db, actor="analyst-1", section_type="investment_thesis",
        content="thesis text", claim_ids=["claim-1"], approved_artefact_ids=[artefact.id],
    )
    second = commit_section(
        db, actor="analyst-1", section_type="risks",
        content="risk text", claim_ids=["claim-1"], approved_artefact_ids=[artefact.id],
    )

    report = get_or_create_default_report(db)
    assert report.section_ids == [first.id, second.id]


def test_commit_section_versions_an_existing_section_without_duplicating_the_report_section_list(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    artefact = _make_approved_artefact(db, ["claim-1", "claim-2"])
    first = commit_section(
        db, actor="analyst-1", section_type="investment_thesis",
        content="v1 text", claim_ids=["claim-1"], approved_artefact_ids=[artefact.id],
    )

    second = commit_section(
        db, actor="analyst-1", section_type="investment_thesis",
        content="v2 text, refined", claim_ids=["claim-1", "claim-2"],
        existing_section_id=first.id, approved_artefact_ids=[artefact.id],
    )

    assert second.id == first.id
    assert second.version == 2

    report = get_or_create_default_report(db)
    assert report.section_ids == [first.id]
    assert get_latest_report_section(db, first.id).content == "v2 text, refined"


def test_commit_section_raises_when_existing_section_id_does_not_exist(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    artefact = _make_approved_artefact(db, ["claim-1"])

    with pytest.raises(ValueError, match="Section nonexistent-section not found"):
        commit_section(
            db,
            actor="analyst-1",
            section_type="investment_thesis",
            content="v2 text",
            claim_ids=["claim-1"],
            existing_section_id="nonexistent-section",
            approved_artefact_ids=[artefact.id],
        )


def test_commit_section_raises_when_an_approved_artefact_id_does_not_exist(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    with pytest.raises(ValueError, match="Artefact nonexistent-artefact not found"):
        commit_section(
            db,
            actor="analyst-1",
            section_type="investment_thesis",
            content="some content",
            claim_ids=["claim-1"],
            approved_artefact_ids=["nonexistent-artefact"],
        )


def test_commit_section_raises_when_an_artefact_id_is_not_approved(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    draft_artefact = create_artefact(
        db, type="thesis_point", content="x", claim_ids=["claim-1"], status="draft",
        approved_by=None, approved_at=None,
    )

    with pytest.raises(
        ValueError,
        match=f"Artefact {draft_artefact.id} is not approved \\(status: draft\\)",
    ):
        commit_section(
            db,
            actor="analyst-1",
            section_type="investment_thesis",
            content="some content",
            claim_ids=["claim-1"],
            approved_artefact_ids=[draft_artefact.id],
        )


def test_commit_section_raises_when_a_claim_id_does_not_belong_to_any_approved_artefact(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    artefact = _make_approved_artefact(db, ["claim-1"])

    with pytest.raises(
        ValueError,
        match="Claim claim-typo is not part of any approved artefact in approved_artefact_ids",
    ):
        commit_section(
            db,
            actor="analyst-1",
            section_type="investment_thesis",
            content="some content",
            claim_ids=["claim-typo"],
            approved_artefact_ids=[artefact.id],
        )
