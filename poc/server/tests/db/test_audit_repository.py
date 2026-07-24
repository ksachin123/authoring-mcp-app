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


def test_retrieves_entries_in_insertion_order_when_timestamps_are_identical(tmp_path):
    """Test that entries with identical timestamps are ordered by insertion order (rowid)."""
    db = create_db(str(tmp_path / "test.db"))

    # Write two audit entries
    entry1 = write_audit_entry(
        db,
        actor="analyst-1",
        action="first_action",
        target_type="artefact",
        target_id="artefact-1",
        target_version=1,
        eval_run_id=None,
        diff=None,
    )
    entry2 = write_audit_entry(
        db,
        actor="analyst-1",
        action="second_action",
        target_type="artefact",
        target_id="artefact-1",
        target_version=2,
        eval_run_id=None,
        diff=None,
    )

    # Force both entries to have identical timestamps
    identical_timestamp = "2026-07-24T12:00:00.000000+00:00"
    db.execute(
        "UPDATE audit_log SET timestamp = ? WHERE id = ?",
        (identical_timestamp, entry1.id),
    )
    db.execute(
        "UPDATE audit_log SET timestamp = ? WHERE id = ?",
        (identical_timestamp, entry2.id),
    )
    db.commit()

    # Retrieve entries and verify they're in insertion order
    trail = get_audit_trail_for_target(db, "artefact", "artefact-1")
    assert len(trail) == 2
    # Without rowid tie-breaker, this could fail if SQLite returns them in arbitrary order
    assert trail[0].action == "first_action", (
        "Expected first entry (by insertion order) to come first, "
        f"but got {trail[0].action} at position 0"
    )
    assert trail[1].action == "second_action", (
        "Expected second entry (by insertion order) to come second, "
        f"but got {trail[1].action} at position 1"
    )
    db.close()
