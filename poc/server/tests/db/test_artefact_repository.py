import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import (
    create_artefact,
    get_latest_artefact,
    create_artefact_version,
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
