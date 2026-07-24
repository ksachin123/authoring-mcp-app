# Research Authoring on ChatGPT — Design

**Status:** Approved for planning
**Date:** 2026-07-24

## Purpose

A Research Authoring solution for sell-side equity research analysts, using ChatGPT as the exclusive frontend. Analysts synthesize investment theses and produce structured, multi-section research reports for institutional clients, drawing on analyst-supplied documents, web search, and third-party financial data reached through MCP connectors (e.g. FactSet, LSEG).

Core requirements:
- Inline citations showing the source of AI-generated content.
- Refinement of content via AI conversation or manual edit.
- Intermediate artefacts (thesis points, data extracts, comparisons) that the analyst must review and explicitly approve before they can be used in the final report.
- Fit for a large organization (hundreds–thousands of analysts) under sell-side research compliance obligations (e.g. FINRA Rule 2241).

## Platform Constraints (as of mid-2026)

- **Canvas is retired**; its replacement, Writing Blocks, is a native-only ChatGPT feature with no third-party API. No app can open, write into, or drive a Writing Block.
- **Apps SDK** (MCP server + widget UI, rendered inline/fullscreen/PiP) is the only extensibility surface with a UI and app-controlled state.
- **Skills** (launched July 2026) are a separate, lighter primitive — packaged workflow instructions with no UI or persistent state of their own. Not a substitute for an App; usable later as a thin layer to standardize how analysts invoke this platform.
- Native ChatGPT citation chips apply only to in-chat text and are not app-controllable; an app that renders its own document (as this one must) needs its own citation UI.
- MCP connectors use per-connector OAuth; Enterprise/Edu workspaces have connectors off by default (admin-gated), Business on by default once published.
- No platform-level compliance safety net exists for prompt injection, model risk management, audit logging, or versioning — these are the application's responsibility.

## Chosen Approach: Hybrid (Option C)

Three options were evaluated:

| | A — Custom widget only | B — Native chat only | **C — Hybrid (chosen)** |
|---|---|---|---|
| Content lives in | Our widget, entirely | Chat / Writing Blocks | Widget owns structure & artefacts; chat drafts prose, explicitly committed |
| Citations | Custom, full control | Native chips only | Custom, attached at commit |
| Approval gating | First-class | Not supported | First-class |
| Persistence | Durable | None (thread-scoped) | Durable |
| Engineering lift | Highest | Lowest | Moderate |
| Compliance fit | Strong | Weak | Strong, reached sooner |

Option B fails outright on governance (no persistence to gate). Option C ships a governed skeleton first — durable state, citations, and approval — while deferring a full in-widget WYSIWYG editor; prose drafting stays in natural chat conversation until the analyst explicitly commits it into the governed document.

**Principle:** ChatGPT is the conversational and rendering surface only. All state, structure, citations, approvals, and governance live in our MCP server and database. Nothing that must survive across sessions, be audited, or be gated by approval is allowed to live only in chat/message history.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ ChatGPT (analyst's client)                               │
│  - Conversation: intent, drafting, refinement dialogue   │
│  - Our App's widget: inline / fullscreen / PiP surfaces  │
│  - Native web search + native file citations (as inputs) │
│  - OAuth consent for each connector                       │
└───────────────────────────┬───────────────────────────────┘
                            │ MCP (tools + widget bridge)
┌───────────────────────────▼───────────────────────────────┐
│ Our MCP Server (the App backend)                          │
│  - Tool layer: ingest, search, synthesize, draft, approve, │
│    assemble, export                                       │
│  - Orchestration: sequences tool calls, calls eval gate    │
│    before anything is offered for approval                │
└─────┬───────────────┬───────────────┬──────────────────────┘
      │               │               │
┌─────▼─────┐   ┌──────▼──────┐  ┌─────▼──────────────┐
│ Our DB     │   │ Eval engine │  │ External MCP data   │
│ Documents, │   │ Groundedness│  │ sources (FactSet,   │
│ artefacts, │   │ / claim     │  │ LSEG, internal data, │
│ citations, │   │ checks      │  │ analyst uploads)     │
│ approvals, │   │             │  │                     │
│ audit log  │   │             │  │                     │
└────────────┘   └─────────────┘  └─────────────────────┘
```

### Components

**Apps SDK Widget** — One App, multiple views via `_meta.ui.resourceUri`:
- *Inline* cards for quick artefact previews surfaced directly in chat (e.g. "3 data extracts pending review").
- *Fullscreen* mode for the workspace: report outline, section list, artefact review/approval screens, citation panel.
- `window.openai.widgetState` holds only UI-local state (scroll position, selection); artefact/report content is always fetched fresh from the MCP server so the server remains the single source of truth.

**MCP Tool Layer** — Grouped by stage, independently callable from chat:
- `ingest_document` / `search_web` / `fetch_connector_data` — bring in raw source material with full provenance (source, retrieval time, query).
- `synthesize_artefact` — produces an intermediate artefact from one or more sources, with inline claim-level citations.
- `run_eval` — automatically invoked before an artefact is surfaced for approval.
- `request_approval` / `approve_artefact` — human-in-the-loop gate, using the Apps SDK approval-gated tool pattern (`toolInput` stays null until the analyst acts).
- `draft_section` — drafts report-section prose conversationally from approved artefacts.
- `commit_section` — explicit action writing analyst-refined section text into the report document model, carrying its citations. This is the boundary where content leaves "chat draft" and becomes part of the governed report.
- `assemble_report` / `export_report` — compiles committed sections into the final report and exports to PDF/Word.

**Document/Data Layer (our DB)** — Source, Claim, Artefact, ReportSection, Report, AuditLogEntry (see Data Model).

**Eval Engine** — A separate, versioned service the MCP server calls synchronously before any artefact/section can be approved.

**Connector Layer** — Adapters to FactSet/LSEG-style MCP data sources, normalizing outputs into our provenance format, tagged with entitlement scope.

## Data Model

```
Source
 ├─ id, type (upload | web_search | connector:factset | connector:lseg | ...)
 ├─ retrieved_at, retrieved_by, query/context
 └─ raw_content_ref (pointer to stored blob), external_url (if citable)

Claim
 ├─ id, text (atomic claim extracted from generated content)
 ├─ source_id (FK → Source), source_excerpt
 └─ eval_status (grounded | unsupported | conflicting), eval_score, eval_run_id

Artefact  (thesis point, data extract, comparison table, etc.)
 ├─ id, type, content (structured, not just prose)
 ├─ claim_ids[] (every claim composing this artefact)
 ├─ status (draft | pending_approval | approved | rejected)
 ├─ approved_by, approved_at
 └─ version (artefacts are versioned; approval always applies to one version)

ReportSection
 ├─ id, report_id (FK), section_type (e.g. thesis, valuation, risks)
 ├─ content (committed prose), claim_ids[] (inherited from source artefacts + any added at drafting)
 ├─ status (draft_in_chat | committed | approved)
 ├─ committed_by, committed_at
 └─ version

Report
 ├─ id, template_id, section_ids[] (ordered)
 ├─ status (in_progress | ready_for_export | exported)
 └─ version, exported_at, export_ref

AuditLogEntry
 ├─ actor (analyst | system | model), action, target (entity + id + version)
 ├─ timestamp, eval_run_id (if applicable)
 └─ full before/after diff where applicable
```

Design points:
- **Claims are the atomic unit of truth**, not artefacts or sections — every piece of generated text traces to one or more Claims, each pinned to a Source excerpt. This is what makes claim-level groundedness evals and citation UI possible, and what a compliance reviewer would actually inspect.
- **Everything is versioned, nothing is overwritten.** Approvals and commits refer to a specific version; edits create new versions.
- **Approval is a first-class state transition**, not a flag — `approved_by`/`approved_at` plus an AuditLogEntry satisfy a FINRA 2241-style attestation requirement regardless of how content was drafted.
- **Sections track their own citation chain** even when composed from already-approved artefacts, because chat-based drafting can introduce new phrasing that needs re-grounding before commit.

## Workflow & Citation UI

1. **Ingest** — Analyst uploads documents or asks ChatGPT to search the web / pull FactSet or LSEG data. Each result becomes a `Source` with full provenance, surfaced inline in chat as a card.
2. **Synthesize** — Analyst requests a thesis point or data extract; `synthesize_artefact` drafts it, decomposing output into `Claim`s pinned to `Source` excerpts.
3. **Auto-eval** — `run_eval` scores every claim before an artefact can be shown as ready; unsupported/conflicting claims are flagged in the widget, not silently included.
4. **Review & approve** — Fullscreen widget lists pending artefacts; each claim renders with a footnote marker opening a side panel with source excerpt and eval score. The analyst approves, rejects, or sends a claim back for AI/manual refinement (producing a new version that re-enters the eval gate).
5. **Draft sections** — Once artefacts are approved, the analyst asks ChatGPT to draft a report section from them, in normal fluid conversation.
6. **Commit** — `commit_section` (widget button or chat instruction) moves prose from the ephemeral chat turn into a versioned, citation-carrying `ReportSection`. Anything not committed never appears in the report.
7. **Assemble & export** — Widget shows the report outline with per-section status (draft / committed / approved); a compliance reviewer can apply a second approval gate at the section level if required. `export_report` produces the distributable PDF/Word.

**Citation UI:** the widget renders its own footnote markers (`[1]`, `[2]`...) inline in artefact/section content, each resolving to a `Claim → Source` pair with an inline preview (excerpt, retrieval date, connector/type icon) — visually consistent across PDF uploads, web results, and connector pulls, since native ChatGPT citation chips don't apply inside our widget's own rendered content.

## Governance Hooks

- **Prompt injection** — Ingested content (web search, connectors) is stored as inert data, never re-injected as executable instruction context. Tool scopes are narrow (e.g. a data connector can fetch, not trigger downstream actions). Approval/export always require explicit human tool calls, giving injected content no path to those actions.
- **MNPI / entitlement boundaries** — Every `Source` carries the entitlement scope of its connector. The MCP server checks entitlement at `commit_section`, not only at ingest, so entitlement can't be laundered by carrying a claim forward.
- **Audit logging** — Every state transition (ingest, synthesize, eval, approve, reject, commit, export) writes an append-only `AuditLogEntry` with actor, before/after diff, and the eval run that gated it.
- **Model risk management** — Each eval run records model/prompt version, eval engine version, and score against the `Claim`, giving SR 11-7-style traceability even without MCP-specific regulatory guidance to cite yet.
- **Versioning/reproducibility** — Nothing is overwritten; any published report traces back to the exact artefact/claim/source versions that composed it.
- **MCP server governance** — Each external connector is onboarded like a code dependency: reviewed, version-pinned, and scoped to read-only data fetch only.
- **Admin/rollout controls** — Workspace admin publishes the App and enables connectors per role (RBAC). Skills, if adopted later as an invocation layer, are reviewed separately against OpenAI's default-on rollout for Enterprise/Edu workspaces.

## Testing & Evals

**Eval engine (content quality gate):**
- Claim extraction is part of `synthesize_artefact`'s output.
- Grounding check: NLI-style classifier first pass; borderline/low-confidence claims escalate to an LLM-as-judge verdict (grounded / unsupported / conflicting).
- Financial error taxonomy checks layered on top: numeric consistency, entity/ticker match, fiscal-period match.
- The eval engine itself is versioned; every run records which version produced which verdict, so later changes to eval logic don't retroactively alter what an already-approved claim was judged against.
- A passing eval makes an artefact *eligible* for approval — it never substitutes for the analyst's sign-off.

**Eval-of-the-evals:** a held-out labeled set of known-good and known-bad (deliberately unsupported/miscalculated) claims is run through the eval engine on every change to prompts/thresholds/classifier, with precision/recall tracked over time so the gate doesn't quietly drift.

**System testing:**
- Tool-level unit tests for each MCP tool against the data model, independent of ChatGPT.
- Workflow/integration tests simulating full sequences (ingest → synthesize → eval → approve → draft → commit → export), verifying state transitions, versioning, and audit log completeness.
- Widget tests for the fullscreen review UI (citation rendering, approval actions, status display) using Apps SDK local dev/preview tooling against a mocked MCP server.
- Security tests: adversarial content (prompt-injection payloads embedded in mock web/connector sources) run through the ingest → synthesize pipeline to confirm they cannot reach an approval or export action.

## Open Items / Follow-ups

- Verify FactSet's MCP offering directly with the vendor (data coverage, GA status, auth flow, entitlement metadata format) before treating it as load-bearing.
- Evaluate LSEG's announced MCP connector as an alternative/complement to FactSet.
- Confirm data residency specifics for widget-rendered content under the organization's ChatGPT Enterprise agreement.
- Decide whether a second, section-level compliance-reviewer approval gate (distinct from analyst artefact approval) is required by the firm's supervisory procedures.
- Decide the report template(s)/section taxonomy per research desk/sector, if they differ.
