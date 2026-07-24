from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source
from research_authoring.db.claim_repository import create_claim, get_claim
from research_authoring.db.artefact_repository import create_artefact
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.run_eval import run_eval


def test_moves_the_artefact_to_pending_approval_after_evaluating_every_claim(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    source = create_source(
        db, type="connector:factset", retrieved_at="2026-07-24T12:00:00Z",
        retrieved_by="analyst-1", context="FactSet fundamentals for AAPL",
        raw_content_ref="epsEstimateFY26: 7.42", external_url=None,
    )
    claim = create_claim(
        db, text="Consensus FY26 EPS is $7.42", source_id=source.id,
        source_excerpt="epsEstimateFY26: 7.42", eval_status="pending",
        eval_score=None, eval_run_id=None,
    )
    artefact = create_artefact(
        db, type="data_extract", content=claim.text, claim_ids=[claim.id],
        status="draft", approved_by=None, approved_at=None,
    )

    updated_artefact, eval_run_id = run_eval(db, actor="analyst-1", artefact_id=artefact.id)

    assert updated_artefact.status == "pending_approval"
    assert updated_artefact.version == 2
    updated_claim = get_claim(db, claim.id)
    assert updated_claim.eval_status == "grounded"
    assert updated_claim.eval_run_id == eval_run_id

    trail = get_audit_trail_for_target(db, "artefact", artefact.id)
    assert any(e.action == "run_eval" and e.eval_run_id == eval_run_id for e in trail)
