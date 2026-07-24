from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source, get_source
from research_authoring.db.claim_repository import create_claim, get_claim, update_claim_eval


def test_creates_and_retrieves_a_source(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    created = create_source(
        db,
        type="upload",
        retrieved_at="2026-07-24T10:00:00Z",
        retrieved_by="analyst-1",
        context="Q2 10-Q upload",
        raw_content_ref="blob://uploads/q2-10q.pdf",
        external_url=None,
    )
    fetched = get_source(db, created.id)
    assert fetched == created
    db.close()


def test_creates_a_claim_linked_to_a_source_and_updates_its_eval_result(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    source = create_source(
        db,
        type="connector:factset",
        retrieved_at="2026-07-24T10:05:00Z",
        retrieved_by="analyst-1",
        context="FactSet consensus EPS query",
        raw_content_ref="factset://fundamentals/AAPL",
        external_url="https://factset.com",
    )
    claim = create_claim(
        db,
        text="Consensus FY26 EPS is $7.42",
        source_id=source.id,
        source_excerpt="FY26 EPS estimate: 7.42",
        eval_status="pending",
        eval_score=None,
        eval_run_id=None,
    )
    assert claim.source_id == source.id

    updated = update_claim_eval(db, claim.id, "grounded", 0.94, "eval-run-1")
    assert updated.eval_status == "grounded"
    assert updated.eval_score == 0.94
    assert get_claim(db, claim.id) == updated
    db.close()
