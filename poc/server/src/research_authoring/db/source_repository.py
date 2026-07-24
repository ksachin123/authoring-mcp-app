import sqlite3
import uuid
from typing import Optional
from .types import Source


def create_source(
    db: sqlite3.Connection,
    *,
    type: str,
    retrieved_at: str,
    retrieved_by: str,
    context: str,
    raw_content_ref: str,
    external_url: Optional[str],
) -> Source:
    source = Source(
        id=str(uuid.uuid4()),
        type=type,
        retrieved_at=retrieved_at,
        retrieved_by=retrieved_by,
        context=context,
        raw_content_ref=raw_content_ref,
        external_url=external_url,
    )
    db.execute(
        """INSERT INTO sources (id, type, retrieved_at, retrieved_by, context, raw_content_ref, external_url)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            source.id,
            source.type,
            source.retrieved_at,
            source.retrieved_by,
            source.context,
            source.raw_content_ref,
            source.external_url,
        ),
    )
    db.commit()
    return source


def get_source(db: sqlite3.Connection, id: str) -> Optional[Source]:
    row = db.execute("SELECT * FROM sources WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return Source(
        id=row["id"],
        type=row["type"],
        retrieved_at=row["retrieved_at"],
        retrieved_by=row["retrieved_by"],
        context=row["context"],
        raw_content_ref=row["raw_content_ref"],
        external_url=row["external_url"],
    )
