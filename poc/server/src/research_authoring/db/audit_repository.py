import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional
from .types import AuditLogEntry


def _row_to_entry(row: sqlite3.Row) -> AuditLogEntry:
    return AuditLogEntry(
        id=row["id"],
        actor=row["actor"],
        action=row["action"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        target_version=row["target_version"],
        timestamp=row["timestamp"],
        eval_run_id=row["eval_run_id"],
        diff=row["diff"],
    )


def write_audit_entry(
    db: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    target_version: Optional[int],
    eval_run_id: Optional[str],
    diff: Optional[str],
) -> AuditLogEntry:
    entry = AuditLogEntry(
        id=str(uuid.uuid4()),
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_version=target_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        eval_run_id=eval_run_id,
        diff=diff,
    )
    db.execute(
        """INSERT INTO audit_log
           (id, actor, action, target_type, target_id, target_version, timestamp, eval_run_id, diff)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.id,
            entry.actor,
            entry.action,
            entry.target_type,
            entry.target_id,
            entry.target_version,
            entry.timestamp,
            entry.eval_run_id,
            entry.diff,
        ),
    )
    db.commit()
    return entry


def get_audit_trail_for_target(
    db: sqlite3.Connection, target_type: str, target_id: str
) -> list[AuditLogEntry]:
    rows = db.execute(
        "SELECT * FROM audit_log WHERE target_type = ? AND target_id = ? ORDER BY timestamp ASC, rowid ASC",
        (target_type, target_id),
    ).fetchall()
    return [_row_to_entry(row) for row in rows]
