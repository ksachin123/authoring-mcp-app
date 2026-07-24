import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import create_artefact, create_artefact_version
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.approve_artefact import approve_artefact


def _make_pending_artefact(db):
    draft = create_artefact(
        db, type="thesis_point", content="x", claim_ids=[], status="draft",
        approved_by=None, approved_at=None,
    )
    return create_artefact_version(db, draft.id, status="pending_approval")


def test_approves_a_pending_approval_artefact_and_records_who_when(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    pending = _make_pending_artefact(db)

    approved = approve_artefact(db, actor="analyst-1", artefact_id=pending.id, decision="approve")

    assert approved.status == "approved"
    assert approved.approved_by == "analyst-1"
    assert approved.approved_at

    trail = get_audit_trail_for_target(db, "artefact", pending.id)
    assert any(e.action == "approve_artefact" for e in trail)


def test_rejects_the_artefact_when_decision_is_reject(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    pending = _make_pending_artefact(db)

    rejected = approve_artefact(db, actor="analyst-1", artefact_id=pending.id, decision="reject")
    assert rejected.status == "rejected"


def test_raises_if_the_artefact_is_not_pending_approval(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    draft = create_artefact(
        db, type="thesis_point", content="x", claim_ids=[], status="draft",
        approved_by=None, approved_at=None,
    )
    with pytest.raises(ValueError, match="Artefact is not pending approval"):
        approve_artefact(db, actor="analyst-1", artefact_id=draft.id, decision="approve")
