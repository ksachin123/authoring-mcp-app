import json
from research_authoring.db.connection import create_db
from research_authoring.db.audit_repository import write_audit_entry, get_audit_trail_for_target


def test_writes_entries_and_retrieves_them_in_chronological_order(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    write_audit_entry(
        db,
        actor="analyst-1",
        action="synthesize_artefact",
        target_type="artefact",
        target_id="artefact-1",
        target_version=1,
        eval_run_id=None,
        diff=None,
    )
    write_audit_entry(
        db,
        actor="analyst-1",
        action="approve_artefact",
        target_type="artefact",
        target_id="artefact-1",
        target_version=2,
        eval_run_id="eval-run-1",
        diff=json.dumps({"status": {"from": "pending_approval", "to": "approved"}}),
    )

    trail = get_audit_trail_for_target(db, "artefact", "artefact-1")
    assert len(trail) == 2
    assert trail[0].action == "synthesize_artefact"
    assert trail[1].action == "approve_artefact"
    assert trail[1].eval_run_id == "eval-run-1"
    db.close()
