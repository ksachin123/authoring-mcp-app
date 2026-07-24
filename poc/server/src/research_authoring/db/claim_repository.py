import sqlite3
import uuid
from typing import Optional
from .types import Claim


def _row_to_claim(row: sqlite3.Row) -> Claim:
    return Claim(
        id=row["id"],
        text=row["text"],
        source_id=row["source_id"],
        source_excerpt=row["source_excerpt"],
        eval_status=row["eval_status"],
        eval_score=row["eval_score"],
        eval_run_id=row["eval_run_id"],
    )


def create_claim(
    db: sqlite3.Connection,
    *,
    text: str,
    source_id: str,
    source_excerpt: str,
    eval_status: str,
    eval_score: Optional[float],
    eval_run_id: Optional[str],
) -> Claim:
    claim = Claim(
        id=str(uuid.uuid4()),
        text=text,
        source_id=source_id,
        source_excerpt=source_excerpt,
        eval_status=eval_status,
        eval_score=eval_score,
        eval_run_id=eval_run_id,
    )
    db.execute(
        """INSERT INTO claims (id, text, source_id, source_excerpt, eval_status, eval_score, eval_run_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            claim.id,
            claim.text,
            claim.source_id,
            claim.source_excerpt,
            claim.eval_status,
            claim.eval_score,
            claim.eval_run_id,
        ),
    )
    db.commit()
    return claim


def get_claim(db: sqlite3.Connection, id: str) -> Optional[Claim]:
    row = db.execute("SELECT * FROM claims WHERE id = ?", (id,)).fetchone()
    return _row_to_claim(row) if row else None


def update_claim_eval(
    db: sqlite3.Connection,
    id: str,
    eval_status: str,
    eval_score: float,
    eval_run_id: str,
) -> Claim:
    db.execute(
        "UPDATE claims SET eval_status = ?, eval_score = ?, eval_run_id = ? WHERE id = ?",
        (eval_status, eval_score, eval_run_id, id),
    )
    db.commit()
    return get_claim(db, id)  # type: ignore[return-value]
