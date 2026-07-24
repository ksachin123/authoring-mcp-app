# Research Authoring POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a proof-of-concept that validates the ChatGPT-native research authoring architecture end-to-end: a real Apps SDK app running in ChatGPT, backed by our own Python MCP server and SQLite datastore, with FactSet data reached via ChatGPT's own FactSet connector (not a direct integration owned by our server), claim-level citations, an eval gate (currently a deterministic stub — no LLM calls in this phase), human approval, a multi-section report template, a ChatGPT Skill wrapping the workflow, and Markdown export.

**Architecture:** A single Python MCP server (using the official `mcp` SDK's `FastMCP`) exposes tools for each pipeline stage (ingest, synthesize, eval, approve, draft, commit, assemble, export) backed by a SQLite database implementing the Source/Claim/Artefact/ReportSection/Report/AuditLogEntry model from the design spec. A React-based Apps SDK widget (fullscreen mode) renders the report workspace, artefact review queue, and citation panel — the widget must be a browser-rendered app because ChatGPT hosts Apps SDK UI in an iframe; this is the one part of the stack that cannot be Python regardless of backend choice. ChatGPT is the conversational and rendering surface only — all durable state lives server-side. FactSet's own MCP connector is enabled directly in ChatGPT alongside this app; our server never calls FactSet's API — it only captures FactSet connector output into governed `Source` records via `ingest_connector_result`. No component in this POC makes an LLM API call: claim extraction and groundedness evaluation (Tasks 7-8) are deterministic, non-AI stubs by explicit project decision, proving the pipeline's sequencing and governance before real AI evaluation is wired in later.

**Tech Stack:** Python 3.11+, `mcp` (official Python MCP SDK, `FastMCP`), stdlib `sqlite3`, `pytest` for tests, `uvicorn` to serve the MCP app. Widget: React + TypeScript + `esbuild`, served as static files alongside the MCP server. No `openai` SDK, no FactSet API client — neither is needed in this phase.

**Spec:** `docs/superpowers/specs/2026-07-24-research-authoring-design.md`

**Deployment target:** Render.com free tier. Free web services have an **ephemeral filesystem** — the local SQLite file is wiped on every redeploy, restart, or wake-from-spin-down — and no persistent disk is available on the free plan. This POC accepts that tradeoff deliberately: SQLite stays as-is (no Postgres migration), and the end-to-end verification (Task 17) must be completed in one continuous session before the free instance spins down from ~15 minutes of inactivity. This is a documented POC limitation, not a defect — the goal is proving the architecture and integration, not persistence durability on this specific host.

## Global Constraints

- Nothing durable (artefacts, sections, approvals, citations, audit entries) may live only in ChatGPT conversation state — the SQLite DB is the source of truth (per design's core principle).
- Every generated claim must carry a `source_id` and `source_excerpt` — no claim may exist without a citation (per Data Model).
- Nothing is ever overwritten — artefacts, sections, and reports use append-only versioning (id + version composite key), matching the design's versioning requirement.
- Every state transition (ingest, synthesize, eval, approve, reject, commit, export) writes an `AuditLogEntry` (per Governance Hooks).
- A passing eval makes an artefact *eligible* for approval; it never auto-approves (per Testing & Evals — human is the final gate).
- **No LLM calls anywhere in this POC.** Claim extraction (Task 7) and groundedness evaluation (Task 8) are deterministic, non-AI stubs by explicit project decision — they prove the eval-gate sequencing (extraction, scoring, persistence, state transition, audit trail) without making any real AI judgment yet. Wiring in real LLM-based versions is deferred to a later iteration; both functions' signatures are written so that swap won't require changing any caller.
- **FactSet is accessed only via ChatGPT's own FactSet connector, never via a direct API integration owned by this server.** There is no FactSet OAuth client, no FactSet API credentials, anywhere in this codebase. `ingest_connector_result_tool` is the single capture point for anything a ChatGPT-native connector (FactSet, and potentially others later) already fetched.
- POC scope excludes: LSEG connector, full financial-error-taxonomy eval suite, eval-of-the-evals regression harness, second-tier compliance-reviewer gate, RBAC/multi-tenant rollout, PDF/Word export (Markdown only), and a custom `search_web` tool (ChatGPT's native web search covers that input path; results are ingested via `ingest_document`).
- All server-side logic (DB, tools, eval) is Python. Only the widget UI is TypeScript/React, because Apps SDK widgets render in a browser iframe inside ChatGPT — this is a platform requirement, not a stack preference.

---

## File Structure

```
poc/
  server/
    pyproject.toml
    .env.example
    src/
      research_authoring/
        __init__.py
        db/
          __init__.py
          schema.sql
          connection.py
          types.py
          source_repository.py
          claim_repository.py
          artefact_repository.py
          report_repository.py        # Report + ReportSection repositories
          audit_repository.py
        eval/
          __init__.py
          claim_extractor.py       # deterministic stub, no LLM call
          groundedness_eval.py     # deterministic stub, no LLM call
        tools/
          __init__.py
          ingest_document.py
          ingest_connector_result.py   # captures ChatGPT-native connector output (e.g. FactSet)
          synthesize_artefact.py
          run_eval.py
          approve_artefact.py
          draft_section.py
          commit_section.py
          assemble_report.py
          export_report.py
          register_tools.py
        server.py
    tests/
      db/test_db.py
      db/test_source_and_claim_repository.py
      db/test_artefact_repository.py
      db/test_report_repository.py
      db/test_audit_repository.py
      eval/test_claim_extractor.py
      eval/test_groundedness_eval.py
      tools/test_ingest_tools.py
      tools/test_synthesize_artefact.py
      tools/test_run_eval.py
      tools/test_approve_artefact.py
      tools/test_draft_and_commit_section.py
      tools/test_assemble_and_export_report.py
  widget/
    package.json
    tsconfig.json
    src/
      openaiBridge.ts
      ReportWorkspace.tsx
      entry.tsx
    index.html
    build.mjs
  skill/
    report-authoring-skill.md
```

---

### Task 1: Python project scaffold & tooling

**Files:**
- Create: `poc/server/pyproject.toml`
- Create: `poc/server/.env.example`
- Create: `poc/server/.gitignore`
- Create: `poc/server/src/research_authoring/__init__.py`

**Interfaces:**
- Produces: a working `pytest` command and installed `research_authoring` package every later task relies on.

- [ ] **Step 1: Create `poc/server/pyproject.toml`**

```toml
[project]
name = "research-authoring-poc"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.2.0",
    "openai>=1.40.0",
    "requests>=2.32.0",
    "uvicorn>=0.30.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.3.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `poc/server/.env.example`**

```
OPENAI_API_KEY=
FACTSET_CLIENT_ID=
FACTSET_CLIENT_SECRET=
FACTSET_API_BASE_URL=https://api.factset.com
DB_PATH=./data/poc.db
```

- [ ] **Step 3: Create `poc/server/.gitignore`**

```
.venv/
__pycache__/
*.pyc
data/*.db
.env
*.egg-info/
```

- [ ] **Step 4: Create `poc/server/src/research_authoring/__init__.py`**

```python
```

(empty file — marks the package)

- [ ] **Step 5: Create a virtualenv, install the package in editable+dev mode, verify pytest runs**

Run:
```bash
cd poc/server
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest --collect-only
```
Expected: `pip install` succeeds; `pytest --collect-only` reports "no tests ran" (no test files exist yet) with no import errors.

- [ ] **Step 6: Commit**

```bash
git add poc/server/pyproject.toml poc/server/.env.example poc/server/.gitignore poc/server/src/research_authoring/__init__.py
git commit -m "chore: scaffold Python MCP server project (pyproject, pytest)"
```

---

### Task 2: Database schema & connection layer

**Files:**
- Create: `poc/server/src/research_authoring/db/__init__.py`
- Create: `poc/server/src/research_authoring/db/schema.sql`
- Create: `poc/server/src/research_authoring/db/types.py`
- Create: `poc/server/src/research_authoring/db/connection.py`
- Test: `poc/server/tests/db/test_db.py`

**Interfaces:**
- Produces: `create_db(path: str) -> sqlite3.Connection` — opens/creates a SQLite DB at `path`, sets `row_factory = sqlite3.Row`, and applies `schema.sql`. All repository tasks (3, 4, 5, 6) consume this.
- Produces (types.py): `Source`, `Claim`, `Artefact`, `ReportSection`, `Report`, `AuditLogEntry` dataclasses used by every repository and tool task.

- [ ] **Step 1: Create `poc/server/src/research_authoring/db/__init__.py`** (empty)

- [ ] **Step 2: Create `poc/server/src/research_authoring/db/types.py`**

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class Source:
    id: str
    type: str  # 'upload' | 'web_search' | 'connector:factset'
    retrieved_at: str
    retrieved_by: str
    context: str
    raw_content_ref: str
    external_url: Optional[str]


@dataclass
class Claim:
    id: str
    text: str
    source_id: str
    source_excerpt: str
    eval_status: str  # 'pending' | 'grounded' | 'unsupported' | 'conflicting'
    eval_score: Optional[float]
    eval_run_id: Optional[str]


@dataclass
class Artefact:
    id: str
    version: int
    type: str  # 'thesis_point' | 'data_extract' | 'comparison_table'
    content: str
    claim_ids: list[str]
    status: str  # 'draft' | 'pending_approval' | 'approved' | 'rejected'
    approved_by: Optional[str]
    approved_at: Optional[str]


@dataclass
class ReportSection:
    id: str
    version: int
    report_id: str
    section_type: str
    content: str
    claim_ids: list[str]
    status: str  # 'draft_in_chat' | 'committed' | 'approved'
    committed_by: Optional[str]
    committed_at: Optional[str]


@dataclass
class Report:
    id: str
    version: int
    template_id: str
    section_ids: list[str]
    status: str  # 'in_progress' | 'ready_for_export' | 'exported'
    exported_at: Optional[str]
    export_ref: Optional[str]


@dataclass
class AuditLogEntry:
    id: str
    actor: str
    action: str
    target_type: str
    target_id: str
    target_version: Optional[int]
    timestamp: str
    eval_run_id: Optional[str]
    diff: Optional[str]
```

- [ ] **Step 3: Create `poc/server/src/research_authoring/db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  retrieved_by TEXT NOT NULL,
  context TEXT NOT NULL,
  raw_content_ref TEXT NOT NULL,
  external_url TEXT
);

CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(id),
  source_excerpt TEXT NOT NULL,
  eval_status TEXT NOT NULL DEFAULT 'pending',
  eval_score REAL,
  eval_run_id TEXT
);

CREATE TABLE IF NOT EXISTS artefacts (
  id TEXT NOT NULL,
  version INTEGER NOT NULL,
  type TEXT NOT NULL,
  content TEXT NOT NULL,
  claim_ids TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  approved_by TEXT,
  approved_at TEXT,
  PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS report_sections (
  id TEXT NOT NULL,
  version INTEGER NOT NULL,
  report_id TEXT NOT NULL,
  section_type TEXT NOT NULL,
  content TEXT NOT NULL,
  claim_ids TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft_in_chat',
  committed_by TEXT,
  committed_at TEXT,
  PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT NOT NULL,
  version INTEGER NOT NULL,
  template_id TEXT NOT NULL,
  section_ids TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'in_progress',
  exported_at TEXT,
  export_ref TEXT,
  PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  target_version INTEGER,
  timestamp TEXT NOT NULL,
  eval_run_id TEXT,
  diff TEXT
);
```

- [ ] **Step 4: Write the failing test**

```python
# poc/server/tests/db/test_db.py
from research_authoring.db.connection import create_db


def test_create_db_creates_all_six_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = create_db(str(db_path))

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [row["name"] for row in rows]

    assert table_names == [
        "artefacts",
        "audit_log",
        "claims",
        "report_sections",
        "reports",
        "sources",
    ]
    conn.close()
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd poc/server && mkdir -p tests/db && pytest tests/db/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.db.connection'`

- [ ] **Step 6: Implement `poc/server/src/research_authoring/db/connection.py`**

```python
import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def create_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.commit()
    return conn
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd poc/server && pytest tests/db/test_db.py -v`
Expected: PASS (1 test)

- [ ] **Step 8: Commit**

```bash
git add poc/server/src/research_authoring/db/__init__.py poc/server/src/research_authoring/db/schema.sql poc/server/src/research_authoring/db/types.py poc/server/src/research_authoring/db/connection.py poc/server/tests/db/test_db.py
git commit -m "feat: add SQLite schema and connection layer"
```

---

### Task 3: Source & Claim repositories

**Files:**
- Create: `poc/server/src/research_authoring/db/source_repository.py`
- Create: `poc/server/src/research_authoring/db/claim_repository.py`
- Test: `poc/server/tests/db/test_source_and_claim_repository.py`

**Interfaces:**
- Consumes: `create_db` from Task 2; `Source`, `Claim` dataclasses from `types.py`.
- Produces: `create_source(db, *, type, retrieved_at, retrieved_by, context, raw_content_ref, external_url) -> Source`, `get_source(db, id) -> Source | None`; `create_claim(db, *, text, source_id, source_excerpt, eval_status, eval_score, eval_run_id) -> Claim`, `get_claim(db, id) -> Claim | None`, `update_claim_eval(db, id, eval_status, eval_score, eval_run_id) -> Claim`. Tasks 9, 10, 11, 12, 13 consume these.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/db/test_source_and_claim_repository.py
from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source, get_source
from research_authoring.db.claim_repository import create_claim, get_claim, update_claim_eval


def test_creates_and_retrieves_a_source(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    created = create_source(
        db,
        type="upload",
        retrieved_at="2026-07-24T10:00:00Z",
        retrieved_by="analyst-1",
        context="Q2 10-Q upload",
        raw_content_ref="blob://uploads/q2-10q.pdf",
        external_url=None,
    )
    fetched = get_source(db, created.id)
    assert fetched == created
    db.close()


def test_creates_a_claim_linked_to_a_source_and_updates_its_eval_result(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    source = create_source(
        db,
        type="connector:factset",
        retrieved_at="2026-07-24T10:05:00Z",
        retrieved_by="analyst-1",
        context="FactSet consensus EPS query",
        raw_content_ref="factset://fundamentals/AAPL",
        external_url="https://factset.com",
    )
    claim = create_claim(
        db,
        text="Consensus FY26 EPS is $7.42",
        source_id=source.id,
        source_excerpt="FY26 EPS estimate: 7.42",
        eval_status="pending",
        eval_score=None,
        eval_run_id=None,
    )
    assert claim.source_id == source.id

    updated = update_claim_eval(db, claim.id, "grounded", 0.94, "eval-run-1")
    assert updated.eval_status == "grounded"
    assert updated.eval_score == 0.94
    assert get_claim(db, claim.id) == updated
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && pytest tests/db/test_source_and_claim_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.db.source_repository'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/db/source_repository.py`**

```python
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
```

- [ ] **Step 4: Implement `poc/server/src/research_authoring/db/claim_repository.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc/server && pytest tests/db/test_source_and_claim_repository.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/server/src/research_authoring/db/source_repository.py poc/server/src/research_authoring/db/claim_repository.py poc/server/tests/db/test_source_and_claim_repository.py
git commit -m "feat: add source and claim repositories"
```

---

### Task 4: Artefact repository with versioning

**Files:**
- Create: `poc/server/src/research_authoring/db/artefact_repository.py`
- Test: `poc/server/tests/db/test_artefact_repository.py`

**Interfaces:**
- Consumes: `create_db` (Task 2), `Artefact` dataclass.
- Produces: `create_artefact(db, *, type, content, claim_ids, status, approved_by, approved_at) -> Artefact` (version 1), `get_latest_artefact(db, id) -> Artefact | None`, `create_artefact_version(db, id, **patch) -> Artefact` (inserts version+1, accepting any of `content`, `claim_ids`, `status`, `approved_by`, `approved_at` as keyword overrides). Tasks 12, 13, 14 consume these.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/db/test_artefact_repository.py
from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import (
    create_artefact,
    get_latest_artefact,
    create_artefact_version,
)


def test_creates_version_1_and_a_subsequent_version_without_losing_history(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    v1 = create_artefact(
        db,
        type="thesis_point",
        content="Margin expansion driven by pricing power.",
        claim_ids=["claim-1"],
        status="draft",
        approved_by=None,
        approved_at=None,
    )
    assert v1.version == 1

    v2 = create_artefact_version(db, v1.id, status="pending_approval")
    assert v2.version == 2
    assert v2.status == "pending_approval"
    assert v2.content == v1.content

    latest = get_latest_artefact(db, v1.id)
    assert latest == v2

    v1_row = db.execute(
        "SELECT * FROM artefacts WHERE id = ? AND version = 1", (v1.id,)
    ).fetchone()
    assert v1_row is not None
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && pytest tests/db/test_artefact_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.db.artefact_repository'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/db/artefact_repository.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/server && pytest tests/db/test_artefact_repository.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/server/src/research_authoring/db/artefact_repository.py poc/server/tests/db/test_artefact_repository.py
git commit -m "feat: add versioned artefact repository"
```

---

### Task 5: Report & ReportSection repositories with versioning

**Files:**
- Create: `poc/server/src/research_authoring/db/report_repository.py`
- Test: `poc/server/tests/db/test_report_repository.py`

**Interfaces:**
- Consumes: `create_db` (Task 2), `Report`, `ReportSection` dataclasses.
- Produces: `create_report(db, template_id) -> Report`, `get_latest_report(db, id) -> Report | None`, `create_report_version(db, id, **patch) -> Report`; `create_report_section(db, *, report_id, section_type, content, claim_ids, status, committed_by, committed_at) -> ReportSection`, `get_latest_report_section(db, id) -> ReportSection | None`, `create_report_section_version(db, id, **patch) -> ReportSection`. Tasks 15, 16 consume these.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/db/test_report_repository.py
from research_authoring.db.connection import create_db
from research_authoring.db.report_repository import (
    create_report,
    get_latest_report,
    create_report_version,
    create_report_section,
    get_latest_report_section,
    create_report_section_version,
)


def test_creates_a_report_and_a_section_versions_both_and_orders_sections(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    report = create_report(db, "equity-initiation-v1")
    assert report.version == 1
    assert report.section_ids == []

    section = create_report_section(
        db,
        report_id=report.id,
        section_type="investment_thesis",
        content="Draft thesis text.",
        claim_ids=["claim-1", "claim-2"],
        status="draft_in_chat",
        committed_by=None,
        committed_at=None,
    )
    assert section.version == 1

    committed_section = create_report_section_version(
        db,
        section.id,
        status="committed",
        committed_by="analyst-1",
        committed_at="2026-07-24T11:00:00Z",
    )
    assert committed_section.version == 2
    assert committed_section.status == "committed"

    report_with_section = create_report_version(db, report.id, section_ids=[section.id])
    assert report_with_section.version == 2
    assert report_with_section.section_ids == [section.id]

    assert get_latest_report(db, report.id) == report_with_section
    assert get_latest_report_section(db, section.id) == committed_section
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && pytest tests/db/test_report_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.db.report_repository'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/db/report_repository.py`**

```python
import sqlite3
import json
import uuid
from typing import Optional
from .types import Report, ReportSection


def _row_to_report(row: sqlite3.Row) -> Report:
    return Report(
        id=row["id"],
        version=row["version"],
        template_id=row["template_id"],
        section_ids=json.loads(row["section_ids"]),
        status=row["status"],
        exported_at=row["exported_at"],
        export_ref=row["export_ref"],
    )


def _insert_report_row(db: sqlite3.Connection, report: Report) -> None:
    db.execute(
        """INSERT INTO reports (id, version, template_id, section_ids, status, exported_at, export_ref)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            report.id,
            report.version,
            report.template_id,
            json.dumps(report.section_ids),
            report.status,
            report.exported_at,
            report.export_ref,
        ),
    )
    db.commit()


def create_report(db: sqlite3.Connection, template_id: str) -> Report:
    report = Report(
        id=str(uuid.uuid4()),
        version=1,
        template_id=template_id,
        section_ids=[],
        status="in_progress",
        exported_at=None,
        export_ref=None,
    )
    _insert_report_row(db, report)
    return report


def get_latest_report(db: sqlite3.Connection, id: str) -> Optional[Report]:
    row = db.execute(
        "SELECT * FROM reports WHERE id = ? ORDER BY version DESC LIMIT 1", (id,)
    ).fetchone()
    return _row_to_report(row) if row else None


def create_report_version(db: sqlite3.Connection, id: str, **patch) -> Report:
    current = get_latest_report(db, id)
    if current is None:
        raise ValueError(f"Report {id} not found")
    next_report = Report(
        id=current.id,
        version=current.version + 1,
        template_id=current.template_id,
        section_ids=patch.get("section_ids", current.section_ids),
        status=patch.get("status", current.status),
        exported_at=patch.get("exported_at", current.exported_at),
        export_ref=patch.get("export_ref", current.export_ref),
    )
    _insert_report_row(db, next_report)
    return next_report


def _row_to_section(row: sqlite3.Row) -> ReportSection:
    return ReportSection(
        id=row["id"],
        version=row["version"],
        report_id=row["report_id"],
        section_type=row["section_type"],
        content=row["content"],
        claim_ids=json.loads(row["claim_ids"]),
        status=row["status"],
        committed_by=row["committed_by"],
        committed_at=row["committed_at"],
    )


def _insert_section_row(db: sqlite3.Connection, section: ReportSection) -> None:
    db.execute(
        """INSERT INTO report_sections
           (id, version, report_id, section_type, content, claim_ids, status, committed_by, committed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            section.id,
            section.version,
            section.report_id,
            section.section_type,
            section.content,
            json.dumps(section.claim_ids),
            section.status,
            section.committed_by,
            section.committed_at,
        ),
    )
    db.commit()


def create_report_section(
    db: sqlite3.Connection,
    *,
    report_id: str,
    section_type: str,
    content: str,
    claim_ids: list[str],
    status: str,
    committed_by: Optional[str],
    committed_at: Optional[str],
) -> ReportSection:
    section = ReportSection(
        id=str(uuid.uuid4()),
        version=1,
        report_id=report_id,
        section_type=section_type,
        content=content,
        claim_ids=claim_ids,
        status=status,
        committed_by=committed_by,
        committed_at=committed_at,
    )
    _insert_section_row(db, section)
    return section


def get_latest_report_section(db: sqlite3.Connection, id: str) -> Optional[ReportSection]:
    row = db.execute(
        "SELECT * FROM report_sections WHERE id = ? ORDER BY version DESC LIMIT 1", (id,)
    ).fetchone()
    return _row_to_section(row) if row else None


def create_report_section_version(db: sqlite3.Connection, id: str, **patch) -> ReportSection:
    current = get_latest_report_section(db, id)
    if current is None:
        raise ValueError(f"ReportSection {id} not found")
    next_section = ReportSection(
        id=current.id,
        version=current.version + 1,
        report_id=current.report_id,
        section_type=current.section_type,
        content=patch.get("content", current.content),
        claim_ids=patch.get("claim_ids", current.claim_ids),
        status=patch.get("status", current.status),
        committed_by=patch.get("committed_by", current.committed_by),
        committed_at=patch.get("committed_at", current.committed_at),
    )
    _insert_section_row(db, next_section)
    return next_section
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/server && pytest tests/db/test_report_repository.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/server/src/research_authoring/db/report_repository.py poc/server/tests/db/test_report_repository.py
git commit -m "feat: add versioned report and report-section repositories"
```

---

### Task 6: Audit log repository

**Files:**
- Create: `poc/server/src/research_authoring/db/audit_repository.py`
- Test: `poc/server/tests/db/test_audit_repository.py`

**Interfaces:**
- Consumes: `create_db` (Task 2), `AuditLogEntry` dataclass.
- Produces: `write_audit_entry(db, *, actor, action, target_type, target_id, target_version, eval_run_id, diff) -> AuditLogEntry`, `get_audit_trail_for_target(db, target_type, target_id) -> list[AuditLogEntry]` (ordered by timestamp ascending). Every tool task (11–16) consumes `write_audit_entry`.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/db/test_audit_repository.py
import json
from research_authoring.db.connection import create_db
from research_authoring.db.audit_repository import write_audit_entry, get_audit_trail_for_target


def test_writes_entries_and_retrieves_them_in_chronological_order(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    write_audit_entry(
        db,
        actor="analyst-1",
        action="synthesize_artefact",
        target_type="artefact",
        target_id="artefact-1",
        target_version=1,
        eval_run_id=None,
        diff=None,
    )
    write_audit_entry(
        db,
        actor="analyst-1",
        action="approve_artefact",
        target_type="artefact",
        target_id="artefact-1",
        target_version=2,
        eval_run_id="eval-run-1",
        diff=json.dumps({"status": {"from": "pending_approval", "to": "approved"}}),
    )

    trail = get_audit_trail_for_target(db, "artefact", "artefact-1")
    assert len(trail) == 2
    assert trail[0].action == "synthesize_artefact"
    assert trail[1].action == "approve_artefact"
    assert trail[1].eval_run_id == "eval-run-1"
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && pytest tests/db/test_audit_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.db.audit_repository'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/db/audit_repository.py`**

```python
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
        "SELECT * FROM audit_log WHERE target_type = ? AND target_id = ? ORDER BY timestamp ASC",
        (target_type, target_id),
    ).fetchall()
    return [_row_to_entry(row) for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/server && pytest tests/db/test_audit_repository.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/server/src/research_authoring/db/audit_repository.py poc/server/tests/db/test_audit_repository.py
git commit -m "feat: add append-only audit log repository"
```

---

### Task 7: Claim extraction (stub — no LLM calls)

**Files:**
- Create: `poc/server/src/research_authoring/eval/__init__.py`
- Create: `poc/server/src/research_authoring/eval/claim_extractor.py`
- Test: `poc/server/tests/eval/test_claim_extractor.py`

**Interfaces:**
- Produces: `extract_claims(*, generated_text: str, source_excerpt: str) -> list[dict]` (each dict has `text`, `source_excerpt` keys). Task 10 (`synthesize_artefact`) consumes this.
- **This is a deliberate non-AI stub.** Per project decision, this POC makes no real LLM calls in this phase — claim decomposition is a simple deterministic sentence split, with every claim mapped to the *entire* source excerpt (since identifying which specific substring supports which claim requires the AI step this task is explicitly deferring). Wiring in a real LLM-based extractor (as originally designed) is future work once the architecture/integration is proven; the function signature is written so that swap can happen later without changing any caller.

- [ ] **Step 1: Create `poc/server/src/research_authoring/eval/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test**

```python
# poc/server/tests/eval/test_claim_extractor.py
from research_authoring.eval.claim_extractor import extract_claims


def test_splits_multi_sentence_text_into_one_claim_per_sentence():
    claims = extract_claims(
        generated_text="Revenue grew 12% YoY. Gross margin was 41%.",
        source_excerpt="Revenue increased 12% year-over-year on a gross margin of 41%.",
    )

    assert claims == [
        {
            "text": "Revenue grew 12% YoY.",
            "source_excerpt": "Revenue increased 12% year-over-year on a gross margin of 41%.",
        },
        {
            "text": "Gross margin was 41%.",
            "source_excerpt": "Revenue increased 12% year-over-year on a gross margin of 41%.",
        },
    ]


def test_single_sentence_text_produces_a_single_claim():
    claims = extract_claims(
        generated_text="Consensus FY26 EPS is $7.42.",
        source_excerpt="FY26 EPS estimate: 7.42",
    )

    assert claims == [{"text": "Consensus FY26 EPS is $7.42.", "source_excerpt": "FY26 EPS estimate: 7.42"}]


def test_ignores_blank_segments_from_trailing_punctuation_or_whitespace():
    claims = extract_claims(generated_text="One claim only.   ", source_excerpt="src")
    assert claims == [{"text": "One claim only.", "source_excerpt": "src"}]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/eval/test_claim_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.eval.claim_extractor'`

- [ ] **Step 4: Implement `poc/server/src/research_authoring/eval/claim_extractor.py`**

```python
import re


def extract_claims(*, generated_text: str, source_excerpt: str) -> list[dict]:
    """Deterministic, non-AI claim decomposition (POC stub).

    Splits on sentence-ending punctuation and maps every resulting claim to
    the full source excerpt, since identifying the specific supporting
    substring per claim is deferred to a future real (LLM-based) extractor.
    """
    segments = re.split(r"(?<=[.!?])\s+", generated_text.strip())
    return [
        {"text": segment.strip(), "source_excerpt": source_excerpt}
        for segment in segments
        if segment.strip()
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/eval/test_claim_extractor.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/server/src/research_authoring/eval/__init__.py poc/server/src/research_authoring/eval/claim_extractor.py poc/server/tests/eval/test_claim_extractor.py
git commit -m "feat: add deterministic (non-LLM) claim extraction stub"
```

---

### Task 8: Groundedness eval (stub — no LLM calls)

**Files:**
- Create: `poc/server/src/research_authoring/eval/groundedness_eval.py`
- Test: `poc/server/tests/eval/test_groundedness_eval.py`

**Interfaces:**
- Produces: `evaluate_claim_groundedness(*, claim_text: str, source_excerpt: str) -> dict` with keys `status` (always `'grounded'` in this stub), `score` (float, always `1.0`), `rationale` (str). Task 11 (`run_eval`) consumes this.
- **This is a deliberate non-AI stub.** Per project decision, no LLM-as-judge call is made in this phase. The function always returns a provisional "grounded" verdict with a rationale that says so explicitly — this proves the eval-gate *sequencing* (every claim gets scored, results are persisted, an eval_run_id ties them together, the artefact transitions state based on the results) without yet making any real correctness judgment. Swapping in a real LLM-judge implementation (as originally designed) is future work; the signature is unchanged from the eventual real version so no caller will need to change.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/eval/test_groundedness_eval.py
from research_authoring.eval.groundedness_eval import evaluate_claim_groundedness


def test_always_returns_a_provisional_grounded_verdict():
    result = evaluate_claim_groundedness(
        claim_text="Consensus FY26 EPS is $7.42", source_excerpt="FY26 EPS estimate: 7.42"
    )
    assert result["status"] == "grounded"
    assert result["score"] == 1.0
    assert "not yet implemented" in result["rationale"].lower() or "stub" in result["rationale"].lower()


def test_returns_the_same_stub_shape_regardless_of_input():
    result_a = evaluate_claim_groundedness(claim_text="Anything", source_excerpt="Unrelated excerpt")
    result_b = evaluate_claim_groundedness(claim_text="Something else entirely", source_excerpt="")
    assert result_a == result_b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/eval/test_groundedness_eval.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.eval.groundedness_eval'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/eval/groundedness_eval.py`**

```python
_STUB_RATIONALE = (
    "Stub evaluation: automated groundedness checking is not yet implemented "
    "in this POC. Claim is provisionally marked grounded pending manual "
    "review before approval."
)


def evaluate_claim_groundedness(*, claim_text: str, source_excerpt: str) -> dict:
    """Deterministic, non-AI groundedness stub (POC).

    Always returns a provisional 'grounded' verdict — this proves the
    eval-gate sequencing (every claim scored, results persisted, artefact
    transitioned) without making any real correctness judgment. A future
    real (LLM-as-judge) implementation will replace this with the same
    signature.
    """
    return {"status": "grounded", "score": 1.0, "rationale": _STUB_RATIONALE}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/eval/test_groundedness_eval.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add poc/server/src/research_authoring/eval/groundedness_eval.py poc/server/tests/eval/test_groundedness_eval.py
git commit -m "feat: add deterministic (non-LLM) groundedness eval stub"
```

---

### Task 9: Tools — `ingest_document` and `ingest_connector_result`

**Files:**
- Create: `poc/server/src/research_authoring/tools/__init__.py`
- Create: `poc/server/src/research_authoring/tools/ingest_document.py`
- Create: `poc/server/src/research_authoring/tools/ingest_connector_result.py`
- Test: `poc/server/tests/tools/test_ingest_tools.py`

**Interfaces:**
- Consumes: `create_source` (Task 3), `write_audit_entry` (Task 6).
- Produces: `ingest_document(db, *, retrieved_by, context, raw_content_ref, external_url=None) -> Source` (`type="upload"`); `ingest_connector_result(db, *, retrieved_by, connector_name, context, raw_content_ref) -> Source` (`type=f"connector:{connector_name}"`). Task 10 (`synthesize_artefact`) consumes `Source` objects these produce.
- **Architecture note:** this POC does **not** call FactSet's (or any) API directly. FactSet data is fetched entirely by FactSet's *own* MCP connector, configured directly in ChatGPT alongside our app — our server never sees FactSet's API. `ingest_connector_result` is how content that a ChatGPT-native connector (FactSet, and later others like LSEG) already retrieved gets captured into our governed `Source`/provenance model, tagged with which connector it came from. This mirrors how native ChatGPT web search results are captured via `ingest_document` — in both cases, ChatGPT already did the fetching; our tool's job is only to register the result with provenance before anything downstream (synthesis, eval, citations) is allowed to use it.

- [ ] **Step 1: Create `poc/server/src/research_authoring/tools/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test**

```python
# poc/server/tests/tools/test_ingest_tools.py
from research_authoring.db.connection import create_db
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.ingest_document import ingest_document
from research_authoring.tools.ingest_connector_result import ingest_connector_result


def test_ingest_document_creates_an_upload_source_and_an_audit_entry(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    source = ingest_document(
        db,
        retrieved_by="analyst-1",
        context="Q2 10-Q upload",
        raw_content_ref="blob://uploads/q2-10q.pdf",
    )
    assert source.type == "upload"

    trail = get_audit_trail_for_target(db, "source", source.id)
    assert len(trail) == 1
    assert trail[0].action == "ingest_document"


def test_ingest_connector_result_tags_the_source_with_the_connector_name_and_writes_an_audit_entry(tmp_path):
    db = create_db(str(tmp_path / "test.db"))

    source = ingest_connector_result(
        db,
        retrieved_by="analyst-1",
        connector_name="factset",
        context="FactSet fundamentals for AAPL, fetched via ChatGPT's FactSet connector",
        raw_content_ref='{"epsEstimateFY26": 7.42}',
    )

    assert source.type == "connector:factset"
    assert "AAPL" in source.context

    trail = get_audit_trail_for_target(db, "source", source.id)
    assert len(trail) == 1
    assert trail[0].action == "ingest_connector_result"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_ingest_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.tools.ingest_document'`

- [ ] **Step 4: Implement `poc/server/src/research_authoring/tools/ingest_document.py`**

```python
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from research_authoring.db.source_repository import create_source
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Source


def ingest_document(
    db: sqlite3.Connection,
    *,
    retrieved_by: str,
    context: str,
    raw_content_ref: str,
    external_url: Optional[str] = None,
) -> Source:
    source = create_source(
        db,
        type="upload",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        retrieved_by=retrieved_by,
        context=context,
        raw_content_ref=raw_content_ref,
        external_url=external_url,
    )

    write_audit_entry(
        db,
        actor=retrieved_by,
        action="ingest_document",
        target_type="source",
        target_id=source.id,
        target_version=None,
        eval_run_id=None,
        diff=None,
    )

    return source
```

- [ ] **Step 5: Implement `poc/server/src/research_authoring/tools/ingest_connector_result.py`**

```python
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_ingest_tools.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add poc/server/src/research_authoring/tools/__init__.py poc/server/src/research_authoring/tools/ingest_document.py poc/server/src/research_authoring/tools/ingest_connector_result.py poc/server/tests/tools/test_ingest_tools.py
git commit -m "feat: add ingest_document and ingest_connector_result tools"
```

---

### Task 10: Tool — `synthesize_artefact`

**Files:**
- Create: `poc/server/src/research_authoring/tools/synthesize_artefact.py`
- Test: `poc/server/tests/tools/test_synthesize_artefact.py`

**Interfaces:**
- Consumes: `extract_claims` (Task 7, stub — no LLM), `create_claim` (Task 3), `create_artefact` (Task 4), `write_audit_entry` (Task 6), `Source` (Task 3).
- Produces: `synthesize_artefact(db, *, actor, type, generated_text, source) -> Artefact`. Task 11 (`run_eval`) consumes the returned `Artefact`.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/tools/test_synthesize_artefact.py
import json
from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.synthesize_artefact import synthesize_artefact


def test_extracts_claims_persists_them_linked_to_the_source_and_creates_a_draft_artefact(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    source = create_source(
        db,
        type="connector:factset",
        retrieved_at="2026-07-24T12:00:00Z",
        retrieved_by="analyst-1",
        context="FactSet fundamentals for AAPL",
        raw_content_ref=json.dumps({"epsEstimateFY26": 7.42}),
        external_url=None,
    )

    artefact = synthesize_artefact(
        db,
        actor="analyst-1",
        type="data_extract",
        generated_text="Consensus FY26 EPS is $7.42.",
        source=source,
    )

    assert artefact.status == "draft"
    assert artefact.version == 1
    assert len(artefact.claim_ids) == 1

    trail = get_audit_trail_for_target(db, "artefact", artefact.id)
    assert len(trail) == 1
    assert trail[0].action == "synthesize_artefact"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_synthesize_artefact.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.tools.synthesize_artefact'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/tools/synthesize_artefact.py`**

```python
import sqlite3
from research_authoring.eval.claim_extractor import extract_claims
from research_authoring.db.claim_repository import create_claim
from research_authoring.db.artefact_repository import create_artefact
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Artefact, Source


def synthesize_artefact(
    db: sqlite3.Connection,
    *,
    actor: str,
    type: str,
    generated_text: str,
    source: Source,
) -> Artefact:
    extracted = extract_claims(generated_text=generated_text, source_excerpt=source.raw_content_ref)

    claims = [
        create_claim(
            db,
            text=c["text"],
            source_id=source.id,
            source_excerpt=c["source_excerpt"],
            eval_status="pending",
            eval_score=None,
            eval_run_id=None,
        )
        for c in extracted
    ]

    artefact = create_artefact(
        db,
        type=type,
        content=generated_text,
        claim_ids=[c.id for c in claims],
        status="draft",
        approved_by=None,
        approved_at=None,
    )

    write_audit_entry(
        db,
        actor=actor,
        action="synthesize_artefact",
        target_type="artefact",
        target_id=artefact.id,
        target_version=artefact.version,
        eval_run_id=None,
        diff=None,
    )

    return artefact
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_synthesize_artefact.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/server/src/research_authoring/tools/synthesize_artefact.py poc/server/tests/tools/test_synthesize_artefact.py
git commit -m "feat: add synthesize_artefact tool (uses stub claim extractor)"
```

---

### Task 11: Tool — `run_eval`

**Files:**
- Create: `poc/server/src/research_authoring/tools/run_eval.py`
- Test: `poc/server/tests/tools/test_run_eval.py`

**Interfaces:**
- Consumes: `evaluate_claim_groundedness` (Task 8, stub — no LLM), `get_claim`/`update_claim_eval` (Task 3), `get_latest_artefact`/`create_artefact_version` (Task 4), `write_audit_entry` (Task 6).
- Produces: `run_eval(db, *, actor, artefact_id) -> tuple[Artefact, str]` (artefact, eval_run_id) — evaluates every claim on the artefact's latest version, moves the artefact to `pending_approval` if all claims are grounded, or leaves it `draft` (with claims flagged) if any are unsupported/conflicting. Since Task 8's eval is currently a stub that always returns "grounded", every artefact will currently transition to `pending_approval` — this task proves the *sequencing* (per-claim scoring, eval_run_id tracking, state transition, audit trail), not real correctness judgment. Task 12 (`approve_artefact`) consumes the returned `Artefact`.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/tools/test_run_eval.py
from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source
from research_authoring.db.claim_repository import create_claim, get_claim
from research_authoring.db.artefact_repository import create_artefact
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.run_eval import run_eval


def test_moves_the_artefact_to_pending_approval_after_evaluating_every_claim(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    source = create_source(
        db, type="connector:factset", retrieved_at="2026-07-24T12:00:00Z",
        retrieved_by="analyst-1", context="FactSet fundamentals for AAPL",
        raw_content_ref="epsEstimateFY26: 7.42", external_url=None,
    )
    claim = create_claim(
        db, text="Consensus FY26 EPS is $7.42", source_id=source.id,
        source_excerpt="epsEstimateFY26: 7.42", eval_status="pending",
        eval_score=None, eval_run_id=None,
    )
    artefact = create_artefact(
        db, type="data_extract", content=claim.text, claim_ids=[claim.id],
        status="draft", approved_by=None, approved_at=None,
    )

    updated_artefact, eval_run_id = run_eval(db, actor="analyst-1", artefact_id=artefact.id)

    assert updated_artefact.status == "pending_approval"
    assert updated_artefact.version == 2
    updated_claim = get_claim(db, claim.id)
    assert updated_claim.eval_status == "grounded"
    assert updated_claim.eval_run_id == eval_run_id

    trail = get_audit_trail_for_target(db, "artefact", artefact.id)
    assert any(e.action == "run_eval" and e.eval_run_id == eval_run_id for e in trail)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_run_eval.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.tools.run_eval'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/tools/run_eval.py`**

```python
import json
import sqlite3
import uuid
from research_authoring.eval.groundedness_eval import evaluate_claim_groundedness
from research_authoring.db.claim_repository import get_claim, update_claim_eval
from research_authoring.db.artefact_repository import get_latest_artefact, create_artefact_version
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Artefact


def run_eval(db: sqlite3.Connection, *, actor: str, artefact_id: str) -> tuple[Artefact, str]:
    artefact = get_latest_artefact(db, artefact_id)
    if artefact is None:
        raise ValueError(f"Artefact {artefact_id} not found")

    eval_run_id = str(uuid.uuid4())
    all_grounded = True

    for claim_id in artefact.claim_ids:
        claim = get_claim(db, claim_id)
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")

        verdict = evaluate_claim_groundedness(claim_text=claim.text, source_excerpt=claim.source_excerpt)
        update_claim_eval(db, claim.id, verdict["status"], verdict["score"], eval_run_id)
        if verdict["status"] != "grounded":
            all_grounded = False

    updated_artefact = create_artefact_version(
        db, artefact.id, status="pending_approval" if all_grounded else "draft"
    )

    write_audit_entry(
        db,
        actor=actor,
        action="run_eval",
        target_type="artefact",
        target_id=updated_artefact.id,
        target_version=updated_artefact.version,
        eval_run_id=eval_run_id,
        diff=json.dumps({"status": {"from": artefact.status, "to": updated_artefact.status}}),
    )

    return updated_artefact, eval_run_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_run_eval.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/server/src/research_authoring/tools/run_eval.py poc/server/tests/tools/test_run_eval.py
git commit -m "feat: add run_eval tool (uses stub groundedness eval)"
```

---

### Task 12: Tool — `approve_artefact`

**Files:**
- Create: `poc/server/src/research_authoring/tools/approve_artefact.py`
- Test: `poc/server/tests/tools/test_approve_artefact.py`

**Interfaces:**
- Consumes: `get_latest_artefact`/`create_artefact_version` (Task 4), `write_audit_entry` (Task 6).
- Produces: `approve_artefact(db, *, actor, artefact_id, decision) -> Artefact` — `decision` is `'approve'` or `'reject'`; raises `ValueError` if the artefact is not `pending_approval`. Task 13 (`draft_section`) consumes only `approved` artefacts.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/tools/test_approve_artefact.py
import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import create_artefact, create_artefact_version
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.approve_artefact import approve_artefact


def _make_pending_artefact(db):
    draft = create_artefact(
        db, type="thesis_point", content="x", claim_ids=[], status="draft",
        approved_by=None, approved_at=None,
    )
    return create_artefact_version(db, draft.id, status="pending_approval")


def test_approves_a_pending_approval_artefact_and_records_who_when(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    pending = _make_pending_artefact(db)

    approved = approve_artefact(db, actor="analyst-1", artefact_id=pending.id, decision="approve")

    assert approved.status == "approved"
    assert approved.approved_by == "analyst-1"
    assert approved.approved_at

    trail = get_audit_trail_for_target(db, "artefact", pending.id)
    assert any(e.action == "approve_artefact" for e in trail)


def test_rejects_the_artefact_when_decision_is_reject(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    pending = _make_pending_artefact(db)

    rejected = approve_artefact(db, actor="analyst-1", artefact_id=pending.id, decision="reject")
    assert rejected.status == "rejected"


def test_raises_if_the_artefact_is_not_pending_approval(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    draft = create_artefact(
        db, type="thesis_point", content="x", claim_ids=[], status="draft",
        approved_by=None, approved_at=None,
    )
    with pytest.raises(ValueError, match="Artefact is not pending approval"):
        approve_artefact(db, actor="analyst-1", artefact_id=draft.id, decision="approve")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_approve_artefact.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.tools.approve_artefact'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/tools/approve_artefact.py`**

```python
import sqlite3
import json
from datetime import datetime, timezone
from research_authoring.db.artefact_repository import get_latest_artefact, create_artefact_version
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Artefact


def approve_artefact(
    db: sqlite3.Connection, *, actor: str, artefact_id: str, decision: str
) -> Artefact:
    current = get_latest_artefact(db, artefact_id)
    if current is None:
        raise ValueError(f"Artefact {artefact_id} not found")
    if current.status != "pending_approval":
        raise ValueError("Artefact is not pending approval")

    now = datetime.now(timezone.utc).isoformat()
    updated = create_artefact_version(
        db,
        current.id,
        status="approved" if decision == "approve" else "rejected",
        approved_by=actor,
        approved_at=now,
    )

    write_audit_entry(
        db,
        actor=actor,
        action="approve_artefact",
        target_type="artefact",
        target_id=updated.id,
        target_version=updated.version,
        eval_run_id=None,
        diff=json.dumps({"status": {"from": current.status, "to": updated.status}}),
    )

    return updated
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_approve_artefact.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add poc/server/src/research_authoring/tools/approve_artefact.py poc/server/tests/tools/test_approve_artefact.py
git commit -m "feat: add approve_artefact human-in-the-loop tool"
```

---

### Task 13: Tools — `draft_section` and `commit_section`

**Files:**
- Create: `poc/server/src/research_authoring/tools/draft_section.py`
- Create: `poc/server/src/research_authoring/tools/commit_section.py`
- Test: `poc/server/tests/tools/test_draft_and_commit_section.py`

**Interfaces:**
- Consumes: `get_latest_artefact` (Task 4), `create_report_section`/`get_latest_report_section`/`create_report_section_version` (Task 5), `get_latest_report`/`create_report_version` (Task 5), `write_audit_entry` (Task 6).
- Produces: `draft_section(*, report_id, section_type, approved_artefacts) -> dict` (keys `section_type`, `draft_content`, `claim_ids`; a pure text-assembly helper, no DB write — represents the in-chat draft before commit); `commit_section(db, *, actor, report_id, section_type, content, claim_ids, existing_section_id=None) -> ReportSection` (creates or versions a `ReportSection` and appends its id to the `Report`'s `section_ids` if new). Task 14 (`assemble_report`) consumes the `Report`/`ReportSection` state this produces.

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/tools/test_draft_and_commit_section.py
from research_authoring.db.connection import create_db
from research_authoring.db.artefact_repository import create_artefact
from research_authoring.db.report_repository import (
    create_report,
    get_latest_report,
    get_latest_report_section,
)
from research_authoring.db.audit_repository import get_audit_trail_for_target
from research_authoring.tools.draft_section import draft_section
from research_authoring.tools.commit_section import commit_section


def test_draft_section_assembles_draft_content_and_claim_ids_from_approved_artefacts(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    artefact = create_artefact(
        db,
        type="thesis_point",
        content="Margin expansion driven by pricing power.",
        claim_ids=["claim-1"],
        status="approved",
        approved_by="analyst-1",
        approved_at="2026-07-24T12:00:00Z",
    )

    draft = draft_section(
        report_id="report-1", section_type="investment_thesis", approved_artefacts=[artefact]
    )

    assert draft["section_type"] == "investment_thesis"
    assert "Margin expansion driven by pricing power." in draft["draft_content"]
    assert draft["claim_ids"] == ["claim-1"]


def test_commit_section_creates_a_new_section_and_appends_it_to_the_report_on_first_commit(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")

    section = commit_section(
        db,
        actor="analyst-1",
        report_id=report.id,
        section_type="investment_thesis",
        content="Margin expansion driven by pricing power.",
        claim_ids=["claim-1"],
    )

    assert section.status == "committed"
    assert section.version == 1

    updated_report = get_latest_report(db, report.id)
    assert updated_report.section_ids == [section.id]

    trail = get_audit_trail_for_target(db, "report_section", section.id)
    assert any(e.action == "commit_section" for e in trail)


def test_commit_section_versions_an_existing_section_without_duplicating_the_report_section_list(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report = create_report(db, "equity-initiation-v1")
    first = commit_section(
        db, actor="analyst-1", report_id=report.id, section_type="investment_thesis",
        content="v1 text", claim_ids=["claim-1"],
    )

    second = commit_section(
        db, actor="analyst-1", report_id=report.id, section_type="investment_thesis",
        content="v2 text, refined", claim_ids=["claim-1", "claim-2"],
        existing_section_id=first.id,
    )

    assert second.id == first.id
    assert second.version == 2

    updated_report = get_latest_report(db, report.id)
    assert updated_report.section_ids == [first.id]
    assert get_latest_report_section(db, first.id).content == "v2 text, refined"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_draft_and_commit_section.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.tools.draft_section'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/tools/draft_section.py`**

```python
from research_authoring.db.types import Artefact


def draft_section(*, report_id: str, section_type: str, approved_artefacts: list[Artefact]) -> dict:
    draft_content = "\n\n".join(a.content for a in approved_artefacts)
    claim_ids = [claim_id for a in approved_artefacts for claim_id in a.claim_ids]
    return {"section_type": section_type, "draft_content": draft_content, "claim_ids": claim_ids}
```

- [ ] **Step 4: Implement `poc/server/src/research_authoring/tools/commit_section.py`**

```python
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from research_authoring.db.report_repository import (
    create_report_section,
    create_report_section_version,
    get_latest_report,
    create_report_version,
)
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import ReportSection


def commit_section(
    db: sqlite3.Connection,
    *,
    actor: str,
    report_id: str,
    section_type: str,
    content: str,
    claim_ids: list[str],
    existing_section_id: Optional[str] = None,
) -> ReportSection:
    now = datetime.now(timezone.utc).isoformat()

    if existing_section_id:
        section = create_report_section_version(
            db,
            existing_section_id,
            content=content,
            claim_ids=claim_ids,
            status="committed",
            committed_by=actor,
            committed_at=now,
        )
    else:
        section = create_report_section(
            db,
            report_id=report_id,
            section_type=section_type,
            content=content,
            claim_ids=claim_ids,
            status="committed",
            committed_by=actor,
            committed_at=now,
        )
        report = get_latest_report(db, report_id)
        if report is None:
            raise ValueError(f"Report {report_id} not found")
        create_report_version(db, report_id, section_ids=[*report.section_ids, section.id])

    write_audit_entry(
        db,
        actor=actor,
        action="commit_section",
        target_type="report_section",
        target_id=section.id,
        target_version=section.version,
        eval_run_id=None,
        diff=None,
    )

    return section
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_draft_and_commit_section.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/server/src/research_authoring/tools/draft_section.py poc/server/src/research_authoring/tools/commit_section.py poc/server/tests/tools/test_draft_and_commit_section.py
git commit -m "feat: add draft_section and commit_section tools"
```

---

### Task 14: Tools — `assemble_report` and `export_report` (Markdown)

**Files:**
- Create: `poc/server/src/research_authoring/tools/assemble_report.py`
- Create: `poc/server/src/research_authoring/tools/export_report.py`
- Test: `poc/server/tests/tools/test_assemble_and_export_report.py`

**Interfaces:**
- Consumes: `get_latest_report`/`create_report_version` (Task 5), `get_latest_report_section` (Task 5), `get_claim` (Task 3), `write_audit_entry` (Task 6).
- Produces: `assemble_report(db, *, actor, report_id, section_order) -> Report` (validates every section referenced is `committed`, reorders `section_ids`, sets status `ready_for_export`); `export_report_to_markdown(db, *, actor, report_id, template_title) -> tuple[str, Report]` (renders sections in order with footnote-style citations resolved from claims, sets status `exported`).

- [ ] **Step 1: Write the failing test**

```python
# poc/server/tests/tools/test_assemble_and_export_report.py
import pytest
from research_authoring.db.connection import create_db
from research_authoring.db.source_repository import create_source
from research_authoring.db.claim_repository import create_claim
from research_authoring.db.report_repository import (
    create_report,
    create_report_section,
    create_report_version,
    get_latest_report,
)
from research_authoring.tools.assemble_report import assemble_report
from research_authoring.tools.export_report import export_report_to_markdown


def _setup_two_section_report(db):
    source = create_source(
        db, type="connector:factset", retrieved_at="2026-07-24T12:00:00Z",
        retrieved_by="analyst-1", context="FactSet fundamentals for AAPL",
        raw_content_ref="epsEstimateFY26: 7.42", external_url=None,
    )
    claim = create_claim(
        db, text="Consensus FY26 EPS is $7.42", source_id=source.id,
        source_excerpt="epsEstimateFY26: 7.42", eval_status="grounded",
        eval_score=1.0, eval_run_id="eval-run-1",
    )

    report = create_report(db, "equity-initiation-v1")
    thesis_section = create_report_section(
        db, report_id=report.id, section_type="investment_thesis",
        content="Margin expansion driven by pricing power.", claim_ids=[],
        status="committed", committed_by="analyst-1", committed_at="2026-07-24T12:05:00Z",
    )
    valuation_section = create_report_section(
        db, report_id=report.id, section_type="valuation",
        content="Consensus FY26 EPS is $7.42.", claim_ids=[claim.id],
        status="committed", committed_by="analyst-1", committed_at="2026-07-24T12:10:00Z",
    )
    create_report_version(db, report.id, section_ids=[thesis_section.id, valuation_section.id])

    return report, thesis_section, valuation_section, source, claim


def test_assemble_report_marks_ready_for_export_when_all_referenced_sections_are_committed(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report, thesis_section, valuation_section, _source, _claim = _setup_two_section_report(db)

    assembled = assemble_report(
        db, actor="analyst-1", report_id=report.id,
        section_order=[thesis_section.id, valuation_section.id],
    )

    assert assembled.status == "ready_for_export"
    assert assembled.section_ids == [thesis_section.id, valuation_section.id]


def test_assemble_report_raises_if_a_referenced_section_is_not_committed(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report, thesis_section, _valuation_section, _source, _claim = _setup_two_section_report(db)

    with pytest.raises(ValueError, match="is not committed"):
        assemble_report(
            db, actor="analyst-1", report_id=report.id,
            section_order=[thesis_section.id, "missing-section"],
        )


def test_export_report_to_markdown_renders_sections_in_order_with_a_footnote_citation(tmp_path):
    db = create_db(str(tmp_path / "test.db"))
    report, thesis_section, valuation_section, _source, _claim = _setup_two_section_report(db)
    assemble_report(
        db, actor="analyst-1", report_id=report.id,
        section_order=[thesis_section.id, valuation_section.id],
    )

    markdown, exported = export_report_to_markdown(
        db, actor="analyst-1", report_id=report.id, template_title="AAPL — Initiation of Coverage"
    )

    assert "# AAPL — Initiation of Coverage" in markdown
    assert "## Investment Thesis" in markdown
    assert "Margin expansion driven by pricing power." in markdown
    assert "## Valuation" in markdown
    assert "Consensus FY26 EPS is $7.42. [1]" in markdown
    assert "[1]: epsEstimateFY26: 7.42" in markdown
    assert exported.status == "exported"
    assert get_latest_report(db, report.id).status == "exported"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_assemble_and_export_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research_authoring.tools.assemble_report'`

- [ ] **Step 3: Implement `poc/server/src/research_authoring/tools/assemble_report.py`**

```python
import sqlite3
from research_authoring.db.report_repository import (
    get_latest_report,
    get_latest_report_section,
    create_report_version,
)
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Report


def assemble_report(
    db: sqlite3.Connection, *, actor: str, report_id: str, section_order: list[str]
) -> Report:
    report = get_latest_report(db, report_id)
    if report is None:
        raise ValueError(f"Report {report_id} not found")

    for section_id in section_order:
        section = get_latest_report_section(db, section_id)
        if section is None or section.status != "committed":
            raise ValueError(f"Section {section_id} is not committed and cannot be assembled")

    updated = create_report_version(db, report_id, section_ids=section_order, status="ready_for_export")

    write_audit_entry(
        db,
        actor=actor,
        action="assemble_report",
        target_type="report",
        target_id=updated.id,
        target_version=updated.version,
        eval_run_id=None,
        diff=None,
    )

    return updated
```

- [ ] **Step 4: Implement `poc/server/src/research_authoring/tools/export_report.py`**

```python
import sqlite3
from datetime import datetime, timezone
from research_authoring.db.report_repository import (
    get_latest_report,
    get_latest_report_section,
    create_report_version,
)
from research_authoring.db.claim_repository import get_claim
from research_authoring.db.audit_repository import write_audit_entry
from research_authoring.db.types import Report

_SECTION_TITLES = {
    "investment_thesis": "Investment Thesis",
    "valuation": "Valuation",
    "risks": "Risks",
}


def export_report_to_markdown(
    db: sqlite3.Connection, *, actor: str, report_id: str, template_title: str
) -> tuple[str, Report]:
    report = get_latest_report(db, report_id)
    if report is None:
        raise ValueError(f"Report {report_id} not found")
    if report.status != "ready_for_export":
        raise ValueError("Report must be ready_for_export before exporting")

    lines = [f"# {template_title}", ""]
    footnotes = []
    footnote_index = 1

    for section_id in report.section_ids:
        section = get_latest_report_section(db, section_id)
        if section is None:
            raise ValueError(f"Section {section_id} not found")

        lines.append(f"## {_SECTION_TITLES.get(section.section_type, section.section_type)}")
        lines.append("")

        content = section.content
        for claim_id in section.claim_ids:
            claim = get_claim(db, claim_id)
            if claim is None:
                continue
            content += f" [{footnote_index}]"
            footnotes.append(f"[{footnote_index}]: {claim.source_excerpt}")
            footnote_index += 1
        lines.append(content)
        lines.append("")

    if footnotes:
        lines.append("---")
        lines.extend(footnotes)

    markdown = "\n".join(lines)

    exported = create_report_version(
        db, report_id, status="exported",
        exported_at=datetime.now(timezone.utc).isoformat(),
        export_ref=f"markdown:{report_id}",
    )

    write_audit_entry(
        db,
        actor=actor,
        action="export_report",
        target_type="report",
        target_id=exported.id,
        target_version=exported.version,
        eval_run_id=None,
        diff=None,
    )

    return markdown, exported
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc/server && .venv/bin/pytest tests/tools/test_assemble_and_export_report.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/server/src/research_authoring/tools/assemble_report.py poc/server/src/research_authoring/tools/export_report.py poc/server/tests/tools/test_assemble_and_export_report.py
git commit -m "feat: add assemble_report and export_report (Markdown) tools"
```

---

### Task 15: MCP server — register all tools

**Files:**
- Create: `poc/server/src/research_authoring/tools/register_tools.py`
- Create: `poc/server/src/research_authoring/server.py`

**Interfaces:**
- Consumes: every tool function from Tasks 9–14, `create_db` (Task 2).
- Produces: a running MCP server (streamable HTTP transport, via `FastMCP`) with all nine tools registered. Task 16 (widget resource + static hosting) and Task 17 (Skill + manual e2e) consume this running server.
- **No OpenAI or FactSet client is constructed here** — this server makes no LLM calls (Tasks 7–8 are deterministic stubs) and never talks to FactSet's API directly (FactSet access happens entirely via FactSet's own ChatGPT connector, captured through `ingest_connector_result_tool`).

This task is registration/wiring rather than new business logic, so it's verified by manual inspection rather than a unit test — the logic underneath is already covered by Tasks 3–14. **Note:** the exact decorator/annotation API of the `mcp` package's `FastMCP` may have moved since this plan was written — check https://github.com/modelcontextprotocol/python-sdk for the current API if the code below doesn't match what's installed.

- [ ] **Step 1: Implement `poc/server/src/research_authoring/tools/register_tools.py`**

```python
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
        existing_section_id: Optional[str] = None,
    ) -> str:
        section = commit_section(
            db, actor=actor, report_id=report_id, section_type=section_type, content=content,
            claim_ids=claim_ids, existing_section_id=existing_section_id,
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
```

- [ ] **Step 2: Implement `poc/server/src/research_authoring/server.py`**

```python
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from research_authoring.db.connection import create_db
from research_authoring.tools.register_tools import register_tools

load_dotenv()

os.makedirs(os.path.dirname(os.environ.get("DB_PATH", "./data/poc.db")) or ".", exist_ok=True)
db = create_db(os.environ.get("DB_PATH", "./data/poc.db"))

mcp = FastMCP("research-authoring-poc")
register_tools(mcp, db)

if __name__ == "__main__":
    # Bind host/port explicitly rather than relying on FastMCP defaults: Render
    # (and most PaaS hosts) require binding 0.0.0.0 and the port they inject via
    # the PORT env var, not localhost/a hardcoded port. See Task 18 for the full
    # Render deployment configuration.
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
```

- [ ] **Step 3: Verify the server starts and lists tools**

Run: `cd poc/server && PORT=8000 .venv/bin/python -m research_authoring.server`
Expected console output confirming the MCP server is listening on `0.0.0.0:8000` (exact log line depends on the installed `mcp` version). **Note:** check that the installed `mcp` version's `FastMCP.run(...)` actually accepts `host`/`port` keyword arguments for the `streamable-http` transport — if it doesn't, use the underlying ASGI app (`mcp.streamable_http_app()`) with `uvicorn.run(app, host="0.0.0.0", port=...)` instead, per the current `mcp` SDK docs at https://github.com/modelcontextprotocol/python-sdk.

In a second terminal, use the MCP inspector to confirm all nine tools are registered:
Run: `npx @modelcontextprotocol/inspector`, then point it at the running server's URL.
Expected: inspector UI lists `ingest_document_tool`, `ingest_connector_result_tool`, `synthesize_artefact_tool`, `run_eval_tool`, `approve_artefact_tool`, `draft_section_tool`, `commit_section_tool`, `assemble_report_tool`, `export_report_tool`.

- [ ] **Step 4: Commit**

```bash
git add poc/server/src/research_authoring/tools/register_tools.py poc/server/src/research_authoring/server.py
git commit -m "feat: wire FastMCP server with all nine tools (no LLM/FactSet clients)"
```

---

### Task 16: Apps SDK widget — report workspace (React)

**Files:**
- Create: `poc/widget/package.json`
- Create: `poc/widget/tsconfig.json`
- Create: `poc/widget/src/openaiBridge.ts`
- Create: `poc/widget/src/ReportWorkspace.tsx`
- Create: `poc/widget/src/entry.tsx`
- Create: `poc/widget/index.html`
- Create: `poc/widget/build.mjs`
- Modify: `poc/server/src/research_authoring/server.py` — serve the built widget bundle as static files and register it as an MCP resource

**Interfaces:**
- Consumes: the nine MCP tools registered in Task 15 (called via the widget bridge's `callTool`).
- Produces: a fullscreen widget the ChatGPT client renders, exercised manually against ChatGPT Developer Mode in Task 17.

This widget is the one part of the stack that must be TypeScript/React rather than Python — Apps SDK widgets render as browser content inside ChatGPT's iframe, and the MCP server (Python) only serves the built bundle and registers its resource URI. This is UI wiring against a host (ChatGPT) that can't be unit-tested outside it, so verification here is a manual smoke test, not an automated test.

- [ ] **Step 1: Create `poc/widget/package.json`**

```json
{
  "name": "research-authoring-poc-widget",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node build.mjs"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "esbuild": "^0.23.1",
    "typescript": "^5.5.4"
  }
}
```

- [ ] **Step 2: Create `poc/widget/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Implement `poc/widget/src/openaiBridge.ts`**

```typescript
export interface OpenAiBridge {
  callTool(name: string, args: Record<string, unknown>): Promise<unknown>;
  widgetState: Record<string, unknown>;
  setWidgetState(state: Record<string, unknown>): void;
}

declare global {
  interface Window {
    openai?: OpenAiBridge;
  }
}

export function getOpenAiBridge(): OpenAiBridge {
  if (!window.openai) {
    throw new Error('window.openai bridge is not present — this widget must run inside ChatGPT');
  }
  return window.openai;
}
```

- [ ] **Step 4: Implement `poc/widget/src/ReportWorkspace.tsx`**

```typescript
import { useEffect, useState } from 'react';
import { getOpenAiBridge } from './openaiBridge.js';

interface ArtefactSummary {
  id: string;
  type: string;
  status: string;
  content: string;
  claim_ids: string[];
}

export function ReportWorkspace({ initialArtefacts }: { initialArtefacts: ArtefactSummary[] }) {
  const [artefacts, setArtefacts] = useState(initialArtefacts);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);

  useEffect(() => {
    const bridge = getOpenAiBridge();
    bridge.setWidgetState({ ...bridge.widgetState, screen: 'report_workspace' });
  }, []);

  async function approve(artefactId: string) {
    const bridge = getOpenAiBridge();
    const result = await bridge.callTool('approve_artefact_tool', {
      actor: 'analyst-1',
      artefact_id: artefactId,
      decision: 'approve'
    });
    const parsed = JSON.parse(result as string);
    setArtefacts((prev) =>
      prev.map((a) => (a.id === artefactId ? { ...a, status: parsed.status } : a))
    );
  }

  return (
    <div>
      <h2>Pending Artefacts</h2>
      <ul>
        {artefacts
          .filter((a) => a.status === 'pending_approval')
          .map((artefact) => (
            <li key={artefact.id}>
              <p>{artefact.content}</p>
              {artefact.claim_ids.map((claimId, i) => (
                <button key={claimId} onClick={() => setSelectedClaimId(claimId)}>
                  [{i + 1}]
                </button>
              ))}
              <button onClick={() => approve(artefact.id)}>Approve</button>
            </li>
          ))}
      </ul>
      {selectedClaimId && <div data-testid="citation-panel">Citation: {selectedClaimId}</div>}
    </div>
  );
}
```

- [ ] **Step 5: Implement `poc/widget/src/entry.tsx`**

```typescript
import { createRoot } from 'react-dom/client';
import { ReportWorkspace } from './ReportWorkspace.js';
import { getOpenAiBridge } from './openaiBridge.js';

const bridge = getOpenAiBridge();
const initialArtefacts = (bridge.widgetState.artefacts as any[]) ?? [];

const root = createRoot(document.getElementById('root')!);
root.render(<ReportWorkspace initialArtefacts={initialArtefacts} />);
```

- [ ] **Step 6: Implement `poc/widget/index.html`**

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Research Authoring Workspace</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="./bundle.js"></script>
  </body>
</html>
```

- [ ] **Step 7: Implement `poc/widget/build.mjs`**

```javascript
import { build } from 'esbuild';
import { writeFileSync, mkdirSync } from 'node:fs';

mkdirSync('dist', { recursive: true });

await build({
  entryPoints: ['src/entry.tsx'],
  bundle: true,
  outfile: 'dist/bundle.js',
  format: 'esm',
  jsx: 'automatic'
});

writeFileSync(
  'dist/index.html',
  `<!doctype html><html><head><meta charset="utf-8"><title>Research Authoring Workspace</title></head><body><div id="root"></div><script type="module" src="./bundle.js"></script></body></html>`
);

console.log('Widget bundle built at dist/bundle.js');
```

- [ ] **Step 8: Build the widget bundle**

Run: `cd poc/widget && npm install && npm run build`
Expected: `Widget bundle built at dist/bundle.js`, and `poc/widget/dist/bundle.js` + `poc/widget/dist/index.html` exist.

- [ ] **Step 9: Serve the widget and register it as an MCP resource from the Python server**

Modify `poc/server/src/research_authoring/server.py` — add before the `if __name__ == "__main__":` block:

```python
_WIDGET_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "..", "widget", "dist")


@mcp.resource("ui://widget/report-workspace.html")
def report_workspace_widget() -> str:
    with open(os.path.join(_WIDGET_DIST, "index.html")) as f:
        return f.read()
```

**Note:** `FastMCP`'s exact API for serving a widget's supporting static assets (e.g. `bundle.js`) alongside its HTML resource, and for setting the `text/html+skybridge` MIME type and `_meta`/`openai/outputTemplate` tool metadata pointing `run_eval_tool` and `approve_artefact_tool` at this resource, depends on the installed `mcp` package version — check https://developers.openai.com/apps-sdk/build/chatgpt-ui for the current pattern and adjust this registration accordingly before Task 17's live ChatGPT test.

- [ ] **Step 10: Manual smoke test**

Run: `cd poc/widget && npx serve dist` (or any static file server), then open the served URL in a browser.
Expected: page loads without a JS error in the console other than the expected `window.openai bridge is not present` message (confirms the bridge check works outside ChatGPT; full interactive verification happens inside ChatGPT in Task 17).

- [ ] **Step 11: Commit**

```bash
git add poc/widget poc/server/src/research_authoring/server.py
git commit -m "feat: add Apps SDK fullscreen widget for artefact review and approval"
```

---

### Task 17: ChatGPT Skill + end-to-end manual verification

**Files:**
- Create: `poc/skill/report-authoring-skill.md`

**Interfaces:**
- Consumes: the nine tool names from Task 15 (must match exactly: `ingest_document_tool`, `ingest_connector_result_tool`, `synthesize_artefact_tool`, `run_eval_tool`, `approve_artefact_tool`, `draft_section_tool`, `commit_section_tool`, `assemble_report_tool`, `export_report_tool`).
- Also assumes FactSet's own MCP connector is separately enabled in the same ChatGPT workspace as this app.
- Produces: a documented Skill definition plus a recorded manual end-to-end pass — the acceptance test for the whole POC.

- [ ] **Step 1: Write the Skill definition `poc/skill/report-authoring-skill.md`**

```markdown
# Skill: Draft an Equity Research Report Section

**When to use:** The analyst asks to research a company, build an investment thesis,
or draft/refine a section of a sell-side equity research report.

**Steps to follow, in order:**
1. If the analyst hasn't supplied source material yet, ask whether to use an uploaded
   document, a ChatGPT-native connector (e.g. FactSet), or web search.
   - For an uploaded document: call `ingest_document_tool`.
   - For a connector (e.g. FactSet): first call the connector's own tool(s) to fetch
     the data, then IMMEDIATELY call `ingest_connector_result_tool` with
     `connector_name` set to that connector (e.g. `"factset"`) and the connector's
     output as `raw_content_ref`/`context`. Never treat a connector's raw output as
     part of the governed report until it has been ingested this way.
2. Call `synthesize_artefact_tool` to turn source material into a cited artefact
   (`thesis_point`, `data_extract`, or `comparison_table`) — never draft analysis
   directly into chat without going through this tool first.
3. Call `run_eval_tool` on the resulting artefact before presenting it to the analyst.
   (Note: this POC's eval is a provisional stub that always marks claims "grounded" —
   treat its output as a placeholder, not a real correctness guarantee, and rely on
   the analyst's own review in the next step.)
4. Show the analyst the artefact and its claims for review. Only call
   `approve_artefact_tool` after the analyst has explicitly approved or rejected it —
   never assume approval.
5. Once artefacts relevant to a section are approved, call `draft_section_tool` to
   assemble a starting draft, then refine the prose conversationally with the analyst
   as needed.
6. When the analyst is satisfied with a section's wording, call `commit_section_tool` —
   do not consider a section part of the report until this has been called.
7. Once all intended sections are committed, call `assemble_report_tool` with the
   desired section order, then `export_report_tool` to produce the Markdown deliverable.

**Never:** call `approve_artefact_tool` or `assemble_report_tool` without an explicit
analyst instruction to do so — these are approval gates, not automatic steps.
```

- [ ] **Step 2: Configure the Skill in the ChatGPT workspace admin panel**

Follow the current instructions at https://help.openai.com/en/articles/20001066-skills-in-chatgpt to upload `poc/skill/report-authoring-skill.md` as a workspace Skill, scoped to the test user/role used for this POC.

- [ ] **Step 3: Register the POC app in ChatGPT Developer Mode, alongside FactSet's connector**

Point ChatGPT Developer Mode at the running Python MCP server's URL (per current instructions at https://developers.openai.com/apps-sdk/build/chatgpt-ui). Confirm all nine tools and the `report-workspace-widget` resource appear. Separately, ensure FactSet's own ChatGPT connector is enabled in the same workspace (per your existing FactSet/ChatGPT connector access) — this app and FactSet's connector run side by side; this app never calls FactSet's API itself.

- [ ] **Step 4: Run the full end-to-end scenario manually**

In a ChatGPT conversation with the POC app, the Skill, and FactSet's connector all enabled:
1. Ask ChatGPT to use the FactSet connector to fetch fundamentals for a real ticker you have access to.
2. Confirm the Skill directs the model to call `ingest_connector_result_tool` with the FactSet connector's output before doing anything else with it.
3. Ask it to synthesize a `data_extract` artefact from that ingested source.
4. Confirm `run_eval_tool` runs automatically (per the Skill) and the widget renders the artefact with a citation marker.
5. Click the citation marker in the widget and confirm it shows the source excerpt.
6. Approve the artefact from the widget; confirm its status updates to `approved`.
7. Ask ChatGPT to draft a second section (e.g. `investment_thesis`) from an uploaded document, repeating ingest → synthesize → eval → approve.
8. Commit both sections, then assemble and export the report; confirm the Markdown output contains both sections in order with resolved footnote citations.
9. Query the SQLite `audit_log` table directly (`sqlite3 poc/server/data/poc.db "SELECT actor, action, target_type, target_id, timestamp FROM audit_log ORDER BY timestamp;"`) and confirm every step above produced an entry.

**Do this in one continuous session** (see Task 18): on Render's free tier the SQLite file is wiped on redeploy/restart/spin-down-wake, so pausing long enough for the instance to idle out mid-walkthrough will lose earlier state.

Expected: all nine tool calls succeed, the widget renders and updates correctly inside ChatGPT, the exported Markdown is well-formed with real FactSet-derived content (fetched via ChatGPT's connector, not our server) and citations, and the audit log has one entry per state transition performed.

- [ ] **Step 5: Commit**

```bash
git add poc/skill/report-authoring-skill.md
git commit -m "docs: add report-authoring Skill definition and record e2e POC verification"
```
### Task 18: Render.com free-tier deployment configuration

**Files:**
- Create: `render.yaml`
- Create: `poc/server/build.sh`
- Modify: `poc/server/src/research_authoring/server.py` — already binds `0.0.0.0:$PORT` (Task 15); no further change needed here beyond verification
- Modify: `poc/widget/build.mjs` — no code change; documented as part of the build step Render runs

**Interfaces:**
- Consumes: the Python server from Task 15 and the widget bundle from Task 16.
- Produces: a deployable configuration Render can build and run on the free plan, serving both the MCP endpoint and the widget's static assets from the one free web service.

This task is deployment configuration, not application logic, so it's verified by an actual Render deploy rather than a unit test.

- [ ] **Step 1: Create `poc/server/build.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Build the widget bundle first so the Python server can serve it as static files.
cd "$(dirname "$0")/../../widget"
npm install
npm run build

# Install the Python server package.
cd "$(dirname "$0")"
pip install -e ".[dev]"
```

- [ ] **Step 2: Make the build script executable**

Run: `chmod +x poc/server/build.sh`

- [ ] **Step 3: Create `render.yaml` at the repository root**

```yaml
services:
  - type: web
    name: research-authoring-poc
    runtime: python
    plan: free
    rootDir: poc/server
    buildCommand: bash build.sh
    startCommand: python -m research_authoring.server
    envVars:
      - key: DB_PATH
        value: ./data/poc.db
```

No secrets are needed: this POC makes no LLM calls and never talks to FactSet's API directly (FactSet access is entirely via FactSet's own ChatGPT connector, separate from this deployment).

- [ ] **Step 4: Ensure the data directory exists at boot**

Already handled in Task 15's `server.py` (`os.makedirs(...)` runs before `create_db(...)`) — needed because Render's ephemeral filesystem starts empty on every wake/redeploy, unlike local dev.

- [ ] **Step 5: Deploy and verify**

Push the repository to a Git provider Render can access, create the service from `render.yaml` (Render dashboard → New → Blueprint).

Run (after deploy finishes): `curl -i https://<your-service>.onrender.com/` (or whatever health path the installed `mcp`/`FastMCP` version exposes)
Expected: an HTTP response (not a connection error) confirming the service is reachable. Note the first request after idle may take up to ~50 seconds (free-tier cold start) — this is expected, not a bug; if ChatGPT's Developer Mode connection attempt times out on a cold instance, retry once the service has woken up.

- [ ] **Step 6: Commit**

```bash
git add render.yaml poc/server/build.sh
git commit -m "chore: add Render.com free-tier deployment configuration"
```

---

## Self-Review

**Spec coverage:**
- Custom widget (inline/fullscreen), React as required by the Apps SDK host — Task 16. ✓
- MCP tool layer (all nine tools), Python via FastMCP — Tasks 9–15. ✓
- Data model (Source/Claim/Artefact/ReportSection/Report/AuditLogEntry, versioning) — Tasks 2–6. ✓
- Claim-level citations resolved in widget and export — Tasks 10, 14, 16. ✓
- Approval-gated human-in-the-loop — Task 12, wired into MCP registration in Task 15. ✓
- Groundedness eval gate before approval — Tasks 8, 11 (both deliberately non-AI stubs per project decision — no LLM calls in this POC phase; sequencing is proven, real judgment is deferred). ✓
- FactSet access via ChatGPT's own connector (not a direct integration owned by this server) — Task 9 (`ingest_connector_result`), exercised live in Task 17. ✓
- Multi-section report template — Tasks 13, 14, 17 (two distinct section types). ✓
- Markdown export — Task 14. ✓
- Skill wrapping the workflow, including connector-then-ingest sequencing — Task 17. ✓
- Audit logging on every transition — Task 6, wired into Tasks 9–14. ✓
- Render.com free-tier deployment (0.0.0.0/$PORT binding, ephemeral-storage handling, build/start commands) — Tasks 15, 18. ✓
- No LLM calls anywhere in this POC — Tasks 7, 8 are deterministic stubs; no `openai` dependency or API key is present anywhere in `poc/server`. ✓
- Prompt-injection containment (ingested content treated as inert data, not instructions) — reflected in Task 9's design (raw content stored as `raw_content_ref`/`context`, never re-injected as system/instruction text) and reiterated as a "never" rule in the Task 17 Skill definition.

**Placeholder scan:** no TBD/TODO markers; the genuinely uncertain external dependency — the exact `mcp`/`FastMCP` widget-resource and tool-annotation API (Tasks 15, 16) — is called out explicitly as a verification step with working default code provided, not left vague. The eval/claim-extraction stubs (Tasks 7, 8) are not placeholders in the forbidden sense: they're fully implemented, tested, deterministic functions — just not AI-based ones, by explicit project decision, with their non-AI nature documented in both the code and this plan.

**Type consistency:** `Source`, `Claim`, `Artefact`, `ReportSection`, `Report`, `AuditLogEntry` dataclasses defined once in Task 2's `types.py` and referenced identically (same field names) by every later task; tool function names registered in Task 15 (`*_tool` suffix) match what Task 16's widget and Task 17's Skill call exactly.
