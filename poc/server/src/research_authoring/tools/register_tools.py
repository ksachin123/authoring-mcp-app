import json
import sqlite3
from dataclasses import asdict
from typing import Any, Optional
from mcp import types
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


_WIDGET_OUTPUT_TEMPLATE = {"openai/outputTemplate": "ui://widget/report-workspace.html"}


def _widget_result(structured_content: dict[str, Any], summary_text: str) -> types.CallToolResult:
    # ChatGPT's Apps SDK client decides whether to render the widget based on
    # `_meta` on the *per-call* result, not just the tool's static definition
    # (confirmed against the working reference app in ../mcp-app, which sets
    # it in both places). The installed mcp SDK's default @mcp.tool return
    # handling (plain str/dict) never attaches `_meta` to the CallToolResult,
    # so tools that must trigger the widget return this object directly.
    # CallToolResult.meta is a pydantic field aliased to the wire key `_meta`
    # (see mcp.types.Result), and mcp's model config does not set
    # `populate_by_name=True`. Constructing with the keyword `meta=` (the
    # field name, not its alias) silently misses the real field and -- since
    # the model allows extra attributes -- creates a bogus top-level `meta`
    # key instead of `_meta` on the wire, which ChatGPT's Apps SDK client
    # does not recognize. The alias must be passed explicitly via dict
    # unpacking, since `_meta` is not a valid Python keyword argument name.
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=summary_text)],
        structuredContent=structured_content,
        **{"_meta": _WIDGET_OUTPUT_TEMPLATE},
    )


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

    @mcp.tool(
        description="Run the groundedness eval gate on an artefact before it can be approved.",
        meta=_WIDGET_OUTPUT_TEMPLATE,
    )
    def run_eval_tool(actor: str, artefact_id: str) -> types.CallToolResult:
        artefact, eval_run_id = run_eval(db, actor=actor, artefact_id=artefact_id)
        structured = {"artefact": asdict(artefact), "eval_run_id": eval_run_id}
        return _widget_result(
            structured,
            f"Eval run {eval_run_id} completed for artefact {artefact_id}: status={artefact.status}.",
        )

    @mcp.tool(
        description="Human approval gate: approve or reject a pending_approval artefact.",
        meta=_WIDGET_OUTPUT_TEMPLATE,
    )
    def approve_artefact_tool(actor: str, artefact_id: str, decision: str) -> types.CallToolResult:
        artefact = approve_artefact(db, actor=actor, artefact_id=artefact_id, decision=decision)
        return _widget_result(
            {"artefact": asdict(artefact)},
            f"Artefact {artefact_id} {artefact.status}.",
        )

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
