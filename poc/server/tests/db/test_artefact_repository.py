import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import (
    create_artefact,
    get_latest_artefact,
    create_artefact_version,
    list_artefacts_by_status,
)


def test_creates_version_1_and_a_subsequent_version_without_losing_history(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    v1 = create_artefact(
        db,
        type="thesis_point",
        content="Margin expansion driven by pricing power.",
        claim_ids=["claim-1"],
        status="draft",
        approved_by=None,
        approved_at=None,
    )
    assert v1.version == 1

    v2 = create_artefact_version(db, v1.id, status="pending_approval")
    assert v2.version == 2
    assert v2.status == "pending_approval"
    assert v2.content == v1.content

    latest = get_latest_artefact(db, v1.id)
    assert latest == v2

    v1_row = db.execute(
        "SELECT * FROM artefacts WHERE id = ? AND version = 1", (v1.id,)
    ).fetchone()
    assert v1_row is not None
    db.close()


def test_create_artefact_version_raises_on_nonexistent_id(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    with pytest.raises(ValueError, match="Artefact nonexistent-id not found"):
        create_artefact_version(db, "nonexistent-id", status="approved")

    db.close()


def test_create_artefact_version_rejects_unknown_patch_keys(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    artefact = create_artefact(
        db,
        type="thesis_point",
        content="Initial content",
        claim_ids=["claim-1"],
        status="draft",
        approved_by=None,
        approved_at=None,
    )

    with pytest.raises(ValueError, match="Unknown patch field"):
        create_artefact_version(db, artefact.id, staus="approved")

    db.close()


def test_list_artefacts_by_status_returns_only_the_latest_version_of_matching_artefacts(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    pending = create_artefact(
        db, type="thesis_point", content="v1", claim_ids=["claim-1"],
        status="draft", approved_by=None, approved_at=None,
    )
    create_artefact_version(db, pending.id, status="pending_approval")

    approved = create_artefact(
        db, type="data_extract", content="v1", claim_ids=["claim-2"],
        status="draft", approved_by=None, approved_at=None,
    )
    create_artefact_version(db, approved.id, status="approved", approved_by="analyst-1")

    other_pending = create_artefact(
        db, type="comparison_table", content="v1", claim_ids=["claim-3"],
        status="pending_approval", approved_by=None, approved_at=None,
    )

    results = list_artefacts_by_status(db, "pending_approval")

    assert [a.id for a in results] == [pending.id, other_pending.id]
    assert all(a.status == "pending_approval" for a in results)
    assert results[0].version == 2  # the latest version, not the superseded draft
    assert results[1].version == 1
    db.close()
