from research_authoring.db.connection import create_db
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.ingest_document import ingest_document
from research_authoring.tools.ingest_connector_result import ingest_connector_result
from research_authoring.tools.ingest_web_result import ingest_web_result


def test_ingest_document_creates_an_upload_source_and_an_audit_entry(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    source = ingest_document(
        db,
        retrieved_by="analyst-1",
        context="Q2 10-Q upload",
        raw_content_ref="blob://uploads/q2-10q.pdf",
    )
    assert source.type == "upload"

    trail = get_audit_trail_for_target(db, "source", source.id)
    assert len(trail) == 1
    assert trail[0].action == "ingest_document"


def test_ingest_connector_result_tags_the_source_with_the_connector_name_and_writes_an_audit_entry(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    source = ingest_connector_result(
        db,
        retrieved_by="analyst-1",
        connector_name="factset",
        context="FactSet fundamentals for AAPL, fetched via ChatGPT's FactSet connector",
        raw_content_ref='{"epsEstimateFY26": 7.42}',
    )

    assert source.type == "connector:factset"
    assert "AAPL" in source.context

    trail = get_audit_trail_for_target(db, "source", source.id)
    assert len(trail) == 1
    assert trail[0].action == "ingest_connector_result"


def test_ingest_web_result_tags_the_source_as_web_search_and_writes_an_audit_entry(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    source = ingest_web_result(
        db,
        retrieved_by="analyst-1",
        context="Acme Corp Q2 revenue growth, per analyst commentary",
        raw_content_ref="Acme Corp reported 12% YoY revenue growth in Q2.",
        external_url="https://example.com/acme-q2-analysis",
    )

    assert source.type == "web_search"
    assert source.external_url == "https://example.com/acme-q2-analysis"

    trail = get_audit_trail_for_target(db, "source", source.id)
    assert len(trail) == 1
    assert trail[0].action == "ingest_web_result"
