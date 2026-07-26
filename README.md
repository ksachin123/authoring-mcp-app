# Research Authoring on ChatGPT — POC

A proof-of-concept validating a ChatGPT-native research authoring architecture for sell-side
equity research: a Python MCP server backing a React Apps SDK widget inside ChatGPT, with
claim-level citations, an approval gate, and a full audit trail.

- **Design spec:** [`docs/superpowers/specs/2026-07-24-research-authoring-design.md`](docs/superpowers/specs/2026-07-24-research-authoring-design.md)
- **Implementation plan:** [`docs/superpowers/plans/2026-07-24-research-authoring-poc.md`](docs/superpowers/plans/2026-07-24-research-authoring-poc.md)

## Architecture at a glance

- **`poc/server/`** — Python MCP server ([`mcp`](https://github.com/modelcontextprotocol/python-sdk) SDK's `FastMCP`), exposing nine tools across the pipeline: ingest → synthesize → eval → approve → draft → commit → assemble → export. Backed by SQLite with append-only versioning and a full audit log.
- **`poc/widget/`** — React/TypeScript Apps SDK widget (the only non-Python part of the stack — ChatGPT renders Apps SDK UI in a browser iframe). Built with esbuild, served as static assets by the Python server.
- **`poc/skill/`** — A ChatGPT Skill definition that sequences tool calls correctly (ingest → synthesize → eval → approve → commit → assemble → export).
- **`render.yaml`** — Render.com free-tier deployment config.

Two deliberate scope decisions for this POC phase, both documented in the plan:

- **No LLM calls anywhere.** Claim extraction and groundedness evaluation are deterministic, non-AI stubs — they prove the pipeline's sequencing and governance, not real AI judgment. Swapping in real implementations later won't require changing any caller.
- **FactSet is accessed only via ChatGPT's own FactSet connector**, never a direct API integration owned by this server. Our server only captures whatever the connector already fetched, via `ingest_connector_result`.

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm (for building the widget)
- A ChatGPT workspace with [Developer Mode](https://developers.openai.com/apps-sdk/build/chatgpt-ui) and Skills enabled, plus FactSet's own connector enabled if you want to exercise that path

## Setup

### 1. Server

```bash
cd poc/server
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # defaults are fine for local dev
```

Run the tests:

```bash
pytest -v
```

### 2. Widget

```bash
cd poc/widget
npm install
npm run build
```

This produces `poc/widget/dist/bundle.js` and `dist/index.html`, which the Python server serves.

### 3. Run the server locally

```bash
cd poc/server
mkdir -p data
PORT=8000 .venv/bin/python -m research_authoring.server
```

The MCP server listens on `http://0.0.0.0:8000`, exposing:

- **`/mcp`** — the MCP endpoint itself (streamable-HTTP/JSON-RPC). Point ChatGPT Developer Mode (or any MCP client) at `http://localhost:8000/mcp` (or your deployed URL, e.g. `https://<your-render-service>.onrender.com/mcp`) to register the app — see [Apps SDK docs](https://developers.openai.com/apps-sdk/build/chatgpt-ui) for the current registration flow.
- **`/health`** — plain HTTP health check, returns `200 ok`. Used by Render's health monitor (`render.yaml`'s `healthCheckPath`); also handy for confirming the server is up: `curl http://localhost:8000/health`.
- **`/widget/bundle.js`** — the built widget's JS bundle, served as a static asset and loaded internally by the `ui://widget/report-workspace.html` resource. Not something you need to reference directly.

The widget UI itself isn't a separate URL — it's registered as the MCP resource `ui://widget/report-workspace.html`, which a client fetches via `resources/read` over the `/mcp` connection when a tool response references it.

#### Testing the MCP server locally without ChatGPT

Plain `curl` won't get you far against `/mcp` since it's a stateful JSON-RPC session. Use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) instead:

```bash
npx @modelcontextprotocol/inspector
```

Then point it at `http://localhost:8000/mcp` to list/call tools and resources, including rendering the widget, without needing ChatGPT Developer Mode.

#### Iterating on the widget UI without ChatGPT

MCP Inspector proves the wiring works, but for actually seeing and clicking through the
widget's UI, use the dev harness instead — a plain HTML page that mocks `window.openai`
(seeded with sample artefact data covering different states: pending artefacts, an empty
list, and a many-artefacts scroll/size test) and loads the real built `dist/bundle.js`
directly:

```bash
cd poc/widget
npm run build          # rebuild after any widget change
npx serve .
```

Open `dev-harness.html` at the URL `serve` prints. Switch scenarios with the buttons in
the dark bar at the top, and watch `notifyIntrinsicHeight`/`callTool` calls in the log
strip beneath it. This is the fastest loop for widget layout/behavior changes — no
Render deploy, no ChatGPT reconnect, no resource-caching surprises, since it's a normal
browser tab loading `bundle.js` over plain HTTP rather than through the `ui://` scheme
ChatGPT uses.

### 4. Configure the Skill

Upload [`poc/skill/report-authoring-skill.md`](poc/skill/report-authoring-skill.md) as a workspace Skill following [OpenAI's current instructions](https://help.openai.com/en/articles/20001066-skills-in-chatgpt), scoped to your test user/role.

### 5. Try it end-to-end

In a ChatGPT conversation with the app, the Skill, and (optionally) FactSet's connector all enabled:

1. Ask ChatGPT to research a company — via an uploaded document or FactSet's connector.
2. Watch it synthesize an artefact, run the eval gate, and present it in the widget for your approval.
3. Approve it, draft a report section, commit it, then assemble and export the report to Markdown.
4. Inspect the audit trail: `sqlite3 poc/server/data/poc.db "SELECT actor, action, target_type, target_id, timestamp FROM audit_log ORDER BY timestamp;"`

## Sample walkthrough

A representative session, turn by turn, with what to expect in ChatGPT at each step.
This assumes the Skill and the app are both enabled in the conversation.

| # | Analyst says | Tools called (via the Skill) | What you see in ChatGPT |
|---|---|---|---|
| 1 | *"I want to research Acme Corp's Q2 revenue growth. I've attached their earnings release PDF — draft a thesis point on it."* | `ingest_document_tool` → `synthesize_artefact_tool` → `run_eval_tool` | Chat narration ("I've registered the source and drafted a thesis point…"), then ChatGPT **switches surfaces**: the `report-workspace` widget opens inline/fullscreen, showing a "Pending Artefacts" list with the artefact's cited text, numbered citation markers (`[1]`, `[2]`…), and an **Approve** button. |
| 2 | *(inside the widget)* clicks `[1]` | — (widget-local; no tool call) | A small panel opens showing the claim's citation. |
| 3 | *(inside the widget)* clicks **Approve** | `approve_artefact_tool` (called directly from the widget) | The artefact's status updates to `approved` in place inside the widget. |
| 4 | *"Looks good, approved. Now draft the risk factors section."* | `draft_section_tool` | No widget — this stays in plain chat. ChatGPT prints the assembled draft text; refine it conversationally like any other chat turn. |
| 5 | *"Commit that section."* | `commit_section_tool` | Plain chat confirmation that the section is now persisted server-side as a versioned `ReportSection`. |
| 6 | *"Now research the same quarter using a recent analyst note you can find on the web."* | web search → `ingest_web_result_tool` → `synthesize_artefact_tool` → `run_eval_tool` | Same as turn 1: the widget opens with the new artefact pending approval, sourced and cited from the web result. |
| 7 | *"Assemble the report with intro then risk factors, and export it."* | `assemble_report_tool` → `export_report_tool` | No widget — the final Markdown deliverable (headers, section prose, numbered Sources list) is printed directly in chat. |

**Which tools render the widget:** only `run_eval_tool` and `approve_artefact_tool` carry
the `_meta["openai/outputTemplate"]` pointing at `ui://widget/report-workspace.html` — every
other tool is plain chat. If a turn that should hit `run_eval_tool` (e.g. turn 1) instead
returns a plain text answer with no tool-call trace at all, ChatGPT likely read the attached
material natively and skipped the Skill entirely rather than something being broken
server-side — see the Skill's explicit "Do not answer directly from an attached file…"
instruction in [`poc/skill/report-authoring-skill.md`](poc/skill/report-authoring-skill.md).

## Deploying to Render (free tier)

`render.yaml` at the repo root is a ready-to-use Render Blueprint. In the Render dashboard, choose
**New → Blueprint** and point it at this repo.

Two things to know about the free tier:

- **No persistent disk.** The SQLite file is wiped on every redeploy, restart, or wake-from-idle. This POC accepts that tradeoff deliberately — do the end-to-end walkthrough in one continuous session.
- **Cold starts.** The instance spins down after ~15 minutes idle; the first request afterward can take up to ~50 seconds to wake up. If ChatGPT's connection attempt times out, just retry.

## Project layout

```
poc/
  server/           Python MCP server
    src/research_authoring/
      db/           SQLite schema, dataclasses, repositories (append-only versioning)
      eval/         Deterministic (non-LLM) claim extraction & groundedness eval stubs
      tools/        The nine MCP tools + server registration
      server.py     Entrypoint
    tests/          pytest suite (41 tests)
  widget/           React/TypeScript Apps SDK widget
  skill/            ChatGPT Skill definition
render.yaml         Render.com free-tier deployment config
docs/superpowers/
  specs/            Design spec
  plans/            Implementation plan
```

## Known limitations (by design, for this POC phase)

- Eval and claim extraction are non-AI stubs — see `poc/server/src/research_authoring/eval/`.
- Claim citation excerpts currently resolve to `Source.raw_content_ref` (often a pointer/URI, not retrieved text) — see the comment in `synthesize_artefact.py`.
- Excludes: LSEG connector, full financial-error-taxonomy eval suite, second-tier compliance-reviewer gate, RBAC/multi-tenant rollout, PDF/Word export (Markdown only).
