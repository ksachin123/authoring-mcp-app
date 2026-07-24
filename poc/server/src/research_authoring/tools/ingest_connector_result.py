import sqlite3
from datetime import datetime, timezone
from research_authoring.db.source_repository import create_source
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Source


def ingest_connector_result(
    db: sqlite3.Connection,
    *,
    retrieved_by: str,
    connector_name: str,
    context: str,
    raw_content_ref: str,
) -> Source:
    """Register content a ChatGPT-native connector (e.g. FactSet) already
    fetched. Our server never calls the connector's underlying API itself —
    it only captures and governs whatever the connector returned into the
    conversation."""
    source = create_source(
        db,
        type=f"connector:{connector_name}",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        retrieved_by=retrieved_by,
        context=context,
        raw_content_ref=raw_content_ref,
        external_url=None,
    )

    write_audit_entry(
        db,
        actor=retrieved_by,
        action="ingest_connector_result",
        target_type="source",
        target_id=source.id,
        target_version=None,
        eval_run_id=None,
        diff=None,
    )

    return source
