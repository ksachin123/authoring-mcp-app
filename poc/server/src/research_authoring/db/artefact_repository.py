import sqlite3
import json
import uuid
from typing import Optional
from .types import Artefact


def _row_to_artefact(row: sqlite3.Row) -> Artefact:
    return Artefact(
        id=row["id"],
        version=row["version"],
        type=row["type"],
        content=row["content"],
        claim_ids=json.loads(row["claim_ids"]),
        status=row["status"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
    )


def _insert_artefact_row(db: sqlite3.Connection, artefact: Artefact) -> None:
    db.execute(
        """INSERT INTO artefacts (id, version, type, content, claim_ids, status, approved_by, approved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            artefact.id,
            artefact.version,
            artefact.type,
            artefact.content,
            json.dumps(artefact.claim_ids),
            artefact.status,
            artefact.approved_by,
            artefact.approved_at,
        ),
    )
    db.commit()


def create_artefact(
    db: sqlite3.Connection,
    *,
    type: str,
    content: str,
    claim_ids: list[str],
    status: str,
    approved_by: Optional[str],
    approved_at: Optional[str],
) -> Artefact:
    artefact = Artefact(
        id=str(uuid.uuid4()),
        version=1,
        type=type,
        content=content,
        claim_ids=claim_ids,
        status=status,
        approved_by=approved_by,
        approved_at=approved_at,
    )
    _insert_artefact_row(db, artefact)
    return artefact


def get_latest_artefact(db: sqlite3.Connection, id: str) -> Optional[Artefact]:
    row = db.execute(
        "SELECT * FROM artefacts WHERE id = ? ORDER BY version DESC LIMIT 1", (id,)
    ).fetchone()
    return _row_to_artefact(row) if row else None


def create_artefact_version(db: sqlite3.Connection, id: str, **patch) -> Artefact:
    current = get_latest_artefact(db, id)
    if current is None:
        raise ValueError(f"Artefact {id} not found")
    next_artefact = Artefact(
        id=current.id,
        version=current.version + 1,
        type=current.type,
        content=patch.get("content", current.content),
        claim_ids=patch.get("claim_ids", current.claim_ids),
        status=patch.get("status", current.status),
        approved_by=patch.get("approved_by", current.approved_by),
        approved_at=patch.get("approved_at", current.approved_at),
    )
    _insert_artefact_row(db, next_artefact)
    return next_artefact
