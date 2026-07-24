import json
from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.synthesize_artefact import synthesize_artefact


def test_extracts_claims_persists_them_linked_to_the_source_and_creates_a_draft_artefact(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    source = create_source(
        db,
        type="connector:factset",
        retrieved_at="2026-07-24T12:00:00Z",
        retrieved_by="analyst-1",
        context="FactSet fundamentals for AAPL",
        raw_content_ref=json.dumps({"epsEstimateFY26": 7.42}),
        external_url=None,
    )

    artefact = synthesize_artefact(
        db,
        actor="analyst-1",
        type="data_extract",
        generated_text="Consensus FY26 EPS is $7.42.",
        source=source,
    )

    assert artefact.status == "draft"
    assert artefact.version == 1
    assert len(artefact.claim_ids) == 1

    trail = get_audit_trail_for_target(db, "artefact", artefact.id)
    assert len(trail) == 1
    assert trail[0].action == "synthesize_artefact"
