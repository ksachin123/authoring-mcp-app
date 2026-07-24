import json
import sqlite3
from dataclasses import asdict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from research_authoring.db.artefact_repository import get_latest_artefact
from research_authoring.tools.ingest_document import ingest_document
from research_authoring.tools.ingest_connector_result import ingest_connector_result
from research_authoring.tools.synthesize_artefact import synthesize_artefact
from research_authoring.tools.run_eval import run_eval
from research_authoring.tools.approve_artefact import approve_artefact
from research_authoring.tools.draft_section import draft_section
from research_authoring.tools.commit_section import commit_section
from research_authoring.tools.assemble_report import assemble_report
from research_authoring.tools.export_report import export_report_to_markdown


def register_tools(mcp: FastMCP, db: sqlite3.Connection) -> None:
    @mcp.tool(description="Register an analyst-uploaded document as a Source.")
    def ingest_document_tool(
        actor: str, context: str, raw_content_ref: str, external_url: Optional[str] = None
    ) -> str:
        source = ingest_document(
            db, retrieved_by=actor, context=context, raw_content_ref=raw_content_ref,
            external_url=external_url,
        )
        return json.dumps(asdict(source))

    @mcp.tool(
        description=(
            "Register content already fetched by a ChatGPT-native connector (e.g. FactSet) "
            "as a governed Source. Call this immediately after using the connector's own "
            "tool(s), before synthesizing any artefact from the result."
        )
    )
    def ingest_connector_result_tool(
        actor: str, connector_name: str, context: str, raw_content_ref: str
    ) -> str:
        source = ingest_connector_result(
            db, retrieved_by=actor, connector_name=connector_name, context=context,
            raw_content_ref=raw_content_ref,
        )
        return json.dumps(asdict(source))

    @mcp.tool(description="Draft an intermediate artefact from a source, decomposed into cited claims.")
    def synthesize_artefact_tool(actor: str, type: str, generated_text: str, source_id: str) -> str:
        from research_authoring.db.source_repository import get_source

        source = get_source(db, source_id)
        if source is None:
            raise ValueError(f"Source {source_id} not found")
        artefact = synthesize_artefact(db, actor=actor, type=type, generated_text=generated_text, source=source)
        return json.dumps(asdict(artefact))

    @mcp.tool(description="Run the groundedness eval gate on an artefact before it can be approved.")
    def run_eval_tool(actor: str, artefact_id: str) -> str:
        artefact, eval_run_id = run_eval(db, actor=actor, artefact_id=artefact_id)
        return json.dumps({"artefact": asdict(artefact), "eval_run_id": eval_run_id})

    @mcp.tool(description="Human approval gate: approve or reject a pending_approval artefact.")
    def approve_artefact_tool(actor: str, artefact_id: str, decision: str) -> str:
        artefact = approve_artefact(db, actor=actor, artefact_id=artefact_id, decision=decision)
        return json.dumps(asdict(artefact))

    @mcp.tool(
        description="Assemble a draft section from approved artefacts (not persisted until commit_section)."
    )
    def draft_section_tool(report_id: str, section_type: str, approved_artefact_ids: list[str]) -> str:
        artefacts = []
        for artefact_id in approved_artefact_ids:
            artefact = get_latest_artefact(db, artefact_id)
            if artefact is None:
                raise ValueError(f"Artefact {artefact_id} not found")
            artefacts.append(artefact)
        draft = draft_section(report_id=report_id, section_type=section_type, approved_artefacts=artefacts)
        return json.dumps(draft)

    @mcp.tool(description="Commit analyst-refined section prose into the governed report document.")
    def commit_section_tool(
        actor: str,
        report_id: str,
        section_type: str,
        content: str,
        claim_ids: list[str],
        approved_artefact_ids: list[str],
        existing_section_id: Optional[str] = None,
    ) -> str:
        section = commit_section(
            db, actor=actor, report_id=report_id, section_type=section_type, content=content,
            claim_ids=claim_ids, approved_artefact_ids=approved_artefact_ids,
            existing_section_id=existing_section_id,
        )
        return json.dumps(asdict(section))

    @mcp.tool(description="Validate and order committed sections into a ready-for-export report.")
    def assemble_report_tool(actor: str, report_id: str, section_order: list[str]) -> str:
        report = assemble_report(db, actor=actor, report_id=report_id, section_order=section_order)
        return json.dumps(asdict(report))

    @mcp.tool(description="Export a ready-for-export report to Markdown with resolved citations.")
    def export_report_tool(actor: str, report_id: str, template_title: str) -> str:
        markdown, _report = export_report_to_markdown(
            db, actor=actor, report_id=report_id, template_title=template_title
        )
        return markdown
