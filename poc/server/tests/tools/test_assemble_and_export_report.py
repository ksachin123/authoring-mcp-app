import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source
from research_authoring.db.claim_repository import create_claim
from research_authoring.db.report_repository import (
    create_report,
    create_report_section,
    create_report_version,
    get_or_create_default_report,
)
from research_authoring.tools.assemble_report import assemble_report
from research_authoring.tools.export_report import export_report_to_markdown


def _setup_two_section_report(db):
    source = create_source(
        db, type="connector:factset", retrieved_at="2026-07-24T12:00:00Z",
        retrieved_by="analyst-1", context="FactSet fundamentals for AAPL",
        raw_content_ref="epsEstimateFY26: 7.42", external_url=None,
    )
    claim = create_claim(
        db, text="Consensus FY26 EPS is $7.42", source_id=source.id,
        source_excerpt="epsEstimateFY26: 7.42", eval_status="grounded",
        eval_score=1.0, eval_run_id="eval-run-1",
    )

    # This POC has a single implicit report per session -- create_report here
    # stands in for the auto-creation get_or_create_default_report would do
    # on first commit_section_tool call, so assemble_report/export_report
    # (which resolve the same default report internally) pick this one up.
    report = create_report(db, "equity-initiation-v1")
    thesis_section = create_report_section(
        db, report_id=report.id, section_type="investment_thesis",
        content="Margin expansion driven by pricing power.", claim_ids=[],
        status="committed", committed_by="analyst-1", committed_at="2026-07-24T12:05:00Z",
    )
    valuation_section = create_report_section(
        db, report_id=report.id, section_type="valuation",
        content="Consensus FY26 EPS is $7.42.", claim_ids=[claim.id],
        status="committed", committed_by="analyst-1", committed_at="2026-07-24T12:10:00Z",
    )
    create_report_version(db, report.id, section_ids=[thesis_section.id, valuation_section.id])

    return report, thesis_section, valuation_section, source, claim


def test_assemble_report_marks_ready_for_export_when_all_referenced_sections_are_committed(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    _report, thesis_section, valuation_section, _source, _claim = _setup_two_section_report(db)

    assembled = assemble_report(
        db, actor="analyst-1",
        section_order=[thesis_section.id, valuation_section.id],
    )

    assert assembled.status == "ready_for_export"
    assert assembled.section_ids == [thesis_section.id, valuation_section.id]


def test_assemble_report_raises_if_section_order_is_empty(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    _setup_two_section_report(db)

    with pytest.raises(ValueError, match="section_order must not be empty"):
        assemble_report(db, actor="analyst-1", section_order=[])


def test_assemble_report_raises_if_a_referenced_section_is_not_committed(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    _report, thesis_section, _valuation_section, _source, _claim = _setup_two_section_report(db)

    with pytest.raises(ValueError, match="is not committed"):
        assemble_report(
            db, actor="analyst-1",
            section_order=[thesis_section.id, "missing-section"],
        )


def test_assemble_report_auto_creates_the_default_report_when_none_exists_yet(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    with pytest.raises(ValueError, match="section_order must not be empty"):
        assemble_report(db, actor="analyst-1", section_order=[])

    # Even though it errored, a default report should now exist.
    report = get_or_create_default_report(db)
    assert report.status == "in_progress"


def test_export_report_to_markdown_renders_sections_in_order_with_a_footnote_citation(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report, thesis_section, valuation_section, _source, _claim = _setup_two_section_report(db)
    assemble_report(
        db, actor="analyst-1",
        section_order=[thesis_section.id, valuation_section.id],
    )

    markdown, exported = export_report_to_markdown(
        db, actor="analyst-1", template_title="AAPL — Initiation of Coverage"
    )

    assert "# AAPL — Initiation of Coverage" in markdown
    assert "## Investment Thesis" in markdown
    assert "Margin expansion driven by pricing power." in markdown
    assert "## Valuation" in markdown
    assert "Consensus FY26 EPS is $7.42. [1]" in markdown
    assert "[1]: epsEstimateFY26: 7.42" in markdown
    assert exported.status == "exported"
    assert get_or_create_default_report(db).id == report.id
    assert get_or_create_default_report(db).status == "exported"


def test_export_report_to_markdown_raises_when_report_is_not_ready_for_export(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    create_report(db, "equity-initiation-v1")

    with pytest.raises(ValueError, match="Report must be ready_for_export before exporting"):
        export_report_to_markdown(db, actor="analyst-1", template_title="AAPL — Initiation of Coverage")


def test_export_report_to_markdown_raises_on_a_dangling_claim_reference(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")
    section = create_report_section(
        db, report_id=report.id, section_type="investment_thesis",
        content="Some text.", claim_ids=["nonexistent-claim"],
        status="committed", committed_by="analyst-1", committed_at="2026-07-24T12:05:00Z",
    )
    create_report_version(db, report.id, section_ids=[section.id])
    assemble_report(db, actor="analyst-1", section_order=[section.id])

    with pytest.raises(
        ValueError,
        match=f"Claim nonexistent-claim referenced by section {section.id} not found",
    ):
        export_report_to_markdown(db, actor="analyst-1", template_title="AAPL — Initiation of Coverage")
