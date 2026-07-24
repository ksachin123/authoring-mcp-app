import sqlite3
from datetime import datetime, timezone
from research_authoring.db.source_repository import create_source
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Source


def ingest_web_result(
    db: sqlite3.Connection,
    *,
    retrieved_by: str,
    context: str,
    raw_content_ref: str,
    external_url: str,
) -> Source:
    """Register content found via ChatGPT's native web search as a governed
    Source. Mirrors ingest_connector_result -- our server never performs the
    search itself, it only captures and governs whatever ChatGPT already
    found."""
    source = create_source(
        db,
        type="web_search",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        retrieved_by=retrieved_by,
        context=context,
        raw_content_ref=raw_content_ref,
        external_url=external_url,
    )

    write_audit_entry(
        db,
        actor=retrieved_by,
        action="ingest_web_result",
        target_type="source",
        target_id=source.id,
        target_version=None,
        eval_run_id=None,
        diff=None,
    )

    return source
