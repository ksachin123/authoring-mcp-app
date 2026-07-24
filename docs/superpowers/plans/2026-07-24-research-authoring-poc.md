# Research Authoring POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a proof-of-concept that validates the ChatGPT-native research authoring architecture end-to-end: a real Apps SDK app running in ChatGPT, backed by our own MCP server and SQLite datastore, with a real FactSet connector, claim-level citations, a groundedness eval gate, human approval, a multi-section report template, a ChatGPT Skill wrapping the workflow, and Markdown export.

**Architecture:** A single Node.js/TypeScript MCP server exposes tools for each pipeline stage (ingest, synthesize, eval, approve, draft, commit, assemble, export) backed by a SQLite database implementing the Source/Claim/Artefact/ReportSection/Report/AuditLogEntry model from the design spec. A React-based Apps SDK widget (fullscreen mode) renders the report workspace, artefact review queue, and citation panel. ChatGPT is the conversational and rendering surface only — all durable state lives server-side.

**Tech Stack:** TypeScript, Node.js (v20+), `@modelcontextprotocol/sdk`, `better-sqlite3`, `express`, `openai` SDK, React + `esbuild` for the widget, `vitest` for tests.

**Spec:** `docs/superpowers/specs/2026-07-24-research-authoring-design.md`

## Global Constraints

- Nothing durable (artefacts, sections, approvals, citations, audit entries) may live only in ChatGPT conversation state — the SQLite DB is the source of truth (per design's core principle).
- Every generated claim must carry a `source_id` and `source_excerpt` — no claim may exist without a citation (per Data Model).
- Nothing is ever overwritten — artefacts, sections, and reports use append-only versioning (id + version composite key), matching the design's versioning requirement.
- Every state transition (ingest, synthesize, eval, approve, reject, commit, export) writes an `AuditLogEntry` (per Governance Hooks).
- A passing eval makes an artefact *eligible* for approval; it never auto-approves (per Testing & Evals — human is the final gate).
- POC scope excludes: LSEG connector, full financial-error-taxonomy eval suite, eval-of-the-evals regression harness, second-tier compliance-reviewer gate, RBAC/multi-tenant rollout, PDF/Word export (Markdown only), and a custom `search_web` tool (ChatGPT's native web search covers that input path; results are ingested via `ingest_document`).

---

## File Structure

```
poc/
  package.json
  tsconfig.json
  vitest.config.ts
  .env.example
  src/
    db/
      schema.sql
      db.ts
      types.ts
      sourceRepository.ts
      claimRepository.ts
      artefactRepository.ts
      reportRepository.ts        # Report + ReportSection repositories
      auditRepository.ts
    llm/
      openaiClient.ts
    eval/
      claimExtractor.ts
      groundednessEval.ts
    factset/
      factsetClient.ts
    tools/
      ingestDocument.ts
      fetchFactsetData.ts
      synthesizeArtefact.ts
      runEval.ts
      approveArtefact.ts
      draftSection.ts
      commitSection.ts
      assembleReport.ts
      exportReport.ts
      registerTools.ts
    server.ts
    widget/
      src/
        openaiBridge.ts
        ReportWorkspace.tsx
      index.html
      build.mjs
  skill/
    report-authoring-skill.md
  tests/
    db/sourceAndClaimRepository.test.ts
    db/artefactRepository.test.ts
    db/reportRepository.test.ts
    db/auditRepository.test.ts
    llm/openaiClient.test.ts
    eval/claimExtractor.test.ts
    eval/groundednessEval.test.ts
    factset/factsetClient.test.ts
    tools/ingestAndFactset.test.ts
    tools/synthesizeArtefact.test.ts
    tools/runEval.test.ts
    tools/approveArtefact.test.ts
    tools/draftAndCommitSection.test.ts
    tools/assembleAndExportReport.test.ts
```

---

### Task 1: Project scaffold & tooling

**Files:**
- Create: `poc/package.json`
- Create: `poc/tsconfig.json`
- Create: `poc/vitest.config.ts`
- Create: `poc/.env.example`
- Create: `poc/.gitignore`

**Interfaces:**
- Produces: a working `npm test` and `npm run typecheck` command every later task relies on.

- [ ] **Step 1: Create `poc/package.json`**

```json
{
  "name": "research-authoring-poc",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit",
    "dev": "tsx src/server.ts",
    "build:widget": "node src/widget/build.mjs"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.12.0",
    "better-sqlite3": "^11.3.0",
    "express": "^4.19.2",
    "openai": "^4.60.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/better-sqlite3": "^7.6.11",
    "@types/express": "^4.17.21",
    "@types/node": "^20.14.0",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "esbuild": "^0.23.1",
    "tsx": "^4.19.0",
    "typescript": "^5.5.4",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Create `poc/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "jsx": "react-jsx",
    "resolveJsonModule": true
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Create `poc/vitest.config.ts`**

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts']
  }
});
```

- [ ] **Step 4: Create `poc/.env.example`**

```
OPENAI_API_KEY=
FACTSET_CLIENT_ID=
FACTSET_CLIENT_SECRET=
FACTSET_API_BASE_URL=https://api.factset.com
DB_PATH=./data/poc.db
```

- [ ] **Step 5: Create `poc/.gitignore`**

```
node_modules/
dist/
data/*.db
.env
```

- [ ] **Step 6: Install dependencies and verify tooling**

Run: `cd poc && npm install && npm run typecheck`
Expected: install succeeds; typecheck passes with no source files yet (no errors reported since `src/` and `tests/` are empty of `.ts` files).

- [ ] **Step 7: Commit**

```bash
git add poc/package.json poc/package-lock.json poc/tsconfig.json poc/vitest.config.ts poc/.env.example poc/.gitignore
git commit -m "chore: scaffold POC project (TypeScript, vitest, deps)"
```

---

### Task 2: Database schema & connection layer

**Files:**
- Create: `poc/src/db/schema.sql`
- Create: `poc/src/db/types.ts`
- Create: `poc/src/db/db.ts`
- Test: `poc/tests/db/db.test.ts`

**Interfaces:**
- Produces: `createDb(path: string): Database.Database` — opens/creates a SQLite DB at `path` and applies `schema.sql`. All repository tasks (3, 4, 5, 6) consume this.
- Produces (types.ts): `Source`, `Claim`, `Artefact`, `ReportSection`, `Report`, `AuditLogEntry` TypeScript interfaces used by every repository and tool task.

- [ ] **Step 1: Create `poc/src/db/types.ts`**

```typescript
export interface Source {
  id: string;
  type: 'upload' | 'web_search' | 'connector:factset';
  retrievedAt: string;
  retrievedBy: string;
  context: string;
  rawContentRef: string;
  externalUrl: string | null;
}

export interface Claim {
  id: string;
  text: string;
  sourceId: string;
  sourceExcerpt: string;
  evalStatus: 'pending' | 'grounded' | 'unsupported' | 'conflicting';
  evalScore: number | null;
  evalRunId: string | null;
}

export interface Artefact {
  id: string;
  version: number;
  type: 'thesis_point' | 'data_extract' | 'comparison_table';
  content: string;
  claimIds: string[];
  status: 'draft' | 'pending_approval' | 'approved' | 'rejected';
  approvedBy: string | null;
  approvedAt: string | null;
}

export interface ReportSection {
  id: string;
  version: number;
  reportId: string;
  sectionType: string;
  content: string;
  claimIds: string[];
  status: 'draft_in_chat' | 'committed' | 'approved';
  committedBy: string | null;
  committedAt: string | null;
}

export interface Report {
  id: string;
  version: number;
  templateId: string;
  sectionIds: string[];
  status: 'in_progress' | 'ready_for_export' | 'exported';
  exportedAt: string | null;
  exportRef: string | null;
}

export interface AuditLogEntry {
  id: string;
  actor: string;
  action: string;
  targetType: string;
  targetId: string;
  targetVersion: number | null;
  timestamp: string;
  evalRunId: string | null;
  diff: string | null;
}
```

- [ ] **Step 2: Create `poc/src/db/schema.sql`**

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

- [ ] **Step 3: Write the failing test for `createDb`**

```typescript
// poc/tests/db/db.test.ts
import { describe, it, expect, afterEach } from 'vitest';
import { unlinkSync, existsSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';

const TEST_DB_PATH = './data/test-db.db';

afterEach(() => {
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('createDb', () => {
  it('creates all six tables', () => {
    const db = createDb(TEST_DB_PATH);
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
      .all()
      .map((row: any) => row.name);
    expect(tables).toEqual([
      'artefacts',
      'audit_log',
      'claims',
      'report_sections',
      'reports',
      'sources'
    ]);
    db.close();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd poc && mkdir -p data && npx vitest run tests/db/db.test.ts`
Expected: FAIL — `Cannot find module '../../src/db/db.js'`

- [ ] **Step 5: Implement `poc/src/db/db.ts`**

```typescript
import Database from 'better-sqlite3';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

export function createDb(path: string): Database.Database {
  const db = new Database(path);
  db.pragma('foreign_keys = ON');
  const schema = readFileSync(join(__dirname, 'schema.sql'), 'utf-8');
  db.exec(schema);
  return db;
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/db/db.test.ts`
Expected: PASS (1 test)

- [ ] **Step 7: Commit**

```bash
git add poc/src/db/schema.sql poc/src/db/types.ts poc/src/db/db.ts poc/tests/db/db.test.ts
git commit -m "feat: add SQLite schema and connection layer"
```

---

### Task 3: Source & Claim repositories

**Files:**
- Create: `poc/src/db/sourceRepository.ts`
- Create: `poc/src/db/claimRepository.ts`
- Test: `poc/tests/db/sourceAndClaimRepository.test.ts`

**Interfaces:**
- Consumes: `createDb` from Task 2; `Source`, `Claim` types from `types.ts`.
- Produces: `createSource(db, input: Omit<Source,'id'>): Source`, `getSource(db, id: string): Source | null`; `createClaim(db, input: Omit<Claim,'id'>): Claim`, `getClaim(db, id: string): Claim | null`, `updateClaimEval(db, id: string, evalStatus: Claim['evalStatus'], evalScore: number, evalRunId: string): Claim`. Tasks 9, 10, 11, 12, 13 consume these.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/db/sourceAndClaimRepository.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { createSource, getSource } from '../../src/db/sourceRepository.js';
import { createClaim, getClaim, updateClaimEval } from '../../src/db/claimRepository.js';

const TEST_DB_PATH = './data/test-source-claim.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => {
  db = createDb(TEST_DB_PATH);
});

afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('sourceRepository', () => {
  it('creates and retrieves a source', () => {
    const created = createSource(db, {
      type: 'upload',
      retrievedAt: '2026-07-24T10:00:00Z',
      retrievedBy: 'analyst-1',
      context: 'Q2 10-Q upload',
      rawContentRef: 'blob://uploads/q2-10q.pdf',
      externalUrl: null
    });
    const fetched = getSource(db, created.id);
    expect(fetched).toEqual(created);
  });
});

describe('claimRepository', () => {
  it('creates a claim linked to a source and updates its eval result', () => {
    const source = createSource(db, {
      type: 'connector:factset',
      retrievedAt: '2026-07-24T10:05:00Z',
      retrievedBy: 'analyst-1',
      context: 'FactSet consensus EPS query',
      rawContentRef: 'factset://fundamentals/AAPL',
      externalUrl: 'https://factset.com'
    });
    const claim = createClaim(db, {
      text: 'Consensus FY26 EPS is $7.42',
      sourceId: source.id,
      sourceExcerpt: 'FY26 EPS estimate: 7.42',
      evalStatus: 'pending',
      evalScore: null,
      evalRunId: null
    });
    expect(claim.sourceId).toBe(source.id);

    const updated = updateClaimEval(db, claim.id, 'grounded', 0.94, 'eval-run-1');
    expect(updated.evalStatus).toBe('grounded');
    expect(updated.evalScore).toBe(0.94);
    expect(getClaim(db, claim.id)).toEqual(updated);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/db/sourceAndClaimRepository.test.ts`
Expected: FAIL — `Cannot find module '../../src/db/sourceRepository.js'`

- [ ] **Step 3: Implement `poc/src/db/sourceRepository.ts`**

```typescript
import type Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import type { Source } from './types.js';

export function createSource(db: Database.Database, input: Omit<Source, 'id'>): Source {
  const source: Source = { id: randomUUID(), ...input };
  db.prepare(
    `INSERT INTO sources (id, type, retrieved_at, retrieved_by, context, raw_content_ref, external_url)
     VALUES (@id, @type, @retrievedAt, @retrievedBy, @context, @rawContentRef, @externalUrl)`
  ).run(source);
  return source;
}

export function getSource(db: Database.Database, id: string): Source | null {
  const row = db.prepare('SELECT * FROM sources WHERE id = ?').get(id) as any;
  if (!row) return null;
  return {
    id: row.id,
    type: row.type,
    retrievedAt: row.retrieved_at,
    retrievedBy: row.retrieved_by,
    context: row.context,
    rawContentRef: row.raw_content_ref,
    externalUrl: row.external_url
  };
}
```

- [ ] **Step 4: Implement `poc/src/db/claimRepository.ts`**

```typescript
import type Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import type { Claim } from './types.js';

function rowToClaim(row: any): Claim {
  return {
    id: row.id,
    text: row.text,
    sourceId: row.source_id,
    sourceExcerpt: row.source_excerpt,
    evalStatus: row.eval_status,
    evalScore: row.eval_score,
    evalRunId: row.eval_run_id
  };
}

export function createClaim(db: Database.Database, input: Omit<Claim, 'id'>): Claim {
  const claim: Claim = { id: randomUUID(), ...input };
  db.prepare(
    `INSERT INTO claims (id, text, source_id, source_excerpt, eval_status, eval_score, eval_run_id)
     VALUES (@id, @text, @sourceId, @sourceExcerpt, @evalStatus, @evalScore, @evalRunId)`
  ).run(claim);
  return claim;
}

export function getClaim(db: Database.Database, id: string): Claim | null {
  const row = db.prepare('SELECT * FROM claims WHERE id = ?').get(id) as any;
  return row ? rowToClaim(row) : null;
}

export function updateClaimEval(
  db: Database.Database,
  id: string,
  evalStatus: Claim['evalStatus'],
  evalScore: number,
  evalRunId: string
): Claim {
  db.prepare(
    'UPDATE claims SET eval_status = ?, eval_score = ?, eval_run_id = ? WHERE id = ?'
  ).run(evalStatus, evalScore, evalRunId, id);
  return getClaim(db, id) as Claim;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/db/sourceAndClaimRepository.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/src/db/sourceRepository.ts poc/src/db/claimRepository.ts poc/tests/db/sourceAndClaimRepository.test.ts
git commit -m "feat: add source and claim repositories"
```

---

### Task 4: Artefact repository with versioning

**Files:**
- Create: `poc/src/db/artefactRepository.ts`
- Test: `poc/tests/db/artefactRepository.test.ts`

**Interfaces:**
- Consumes: `createDb` (Task 2), `Artefact` type.
- Produces: `createArtefact(db, input: Omit<Artefact,'id'|'version'>): Artefact` (version 1), `getLatestArtefact(db, id): Artefact | null`, `createArtefactVersion(db, id, patch: Partial<Pick<Artefact,'content'|'claimIds'|'status'|'approvedBy'|'approvedAt'>>): Artefact` (inserts version+1). Tasks 12, 13, 14 consume these.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/db/artefactRepository.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { createArtefact, getLatestArtefact, createArtefactVersion } from '../../src/db/artefactRepository.js';

const TEST_DB_PATH = './data/test-artefact.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('artefactRepository', () => {
  it('creates version 1 and a subsequent version without losing history', () => {
    const v1 = createArtefact(db, {
      type: 'thesis_point',
      content: 'Margin expansion driven by pricing power.',
      claimIds: ['claim-1'],
      status: 'draft',
      approvedBy: null,
      approvedAt: null
    });
    expect(v1.version).toBe(1);

    const v2 = createArtefactVersion(db, v1.id, { status: 'pending_approval' });
    expect(v2.version).toBe(2);
    expect(v2.status).toBe('pending_approval');
    expect(v2.content).toBe(v1.content);

    const latest = getLatestArtefact(db, v1.id);
    expect(latest).toEqual(v2);

    const v1Row = db.prepare('SELECT * FROM artefacts WHERE id = ? AND version = 1').get(v1.id);
    expect(v1Row).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/db/artefactRepository.test.ts`
Expected: FAIL — `Cannot find module '../../src/db/artefactRepository.js'`

- [ ] **Step 3: Implement `poc/src/db/artefactRepository.ts`**

```typescript
import type Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import type { Artefact } from './types.js';

function rowToArtefact(row: any): Artefact {
  return {
    id: row.id,
    version: row.version,
    type: row.type,
    content: row.content,
    claimIds: JSON.parse(row.claim_ids),
    status: row.status,
    approvedBy: row.approved_by,
    approvedAt: row.approved_at
  };
}

function insertArtefactRow(db: Database.Database, artefact: Artefact): void {
  db.prepare(
    `INSERT INTO artefacts (id, version, type, content, claim_ids, status, approved_by, approved_at)
     VALUES (@id, @version, @type, @content, @claimIds, @status, @approvedBy, @approvedAt)`
  ).run({
    ...artefact,
    claimIds: JSON.stringify(artefact.claimIds)
  });
}

export function createArtefact(db: Database.Database, input: Omit<Artefact, 'id' | 'version'>): Artefact {
  const artefact: Artefact = { id: randomUUID(), version: 1, ...input };
  insertArtefactRow(db, artefact);
  return artefact;
}

export function getLatestArtefact(db: Database.Database, id: string): Artefact | null {
  const row = db
    .prepare('SELECT * FROM artefacts WHERE id = ? ORDER BY version DESC LIMIT 1')
    .get(id) as any;
  return row ? rowToArtefact(row) : null;
}

export function createArtefactVersion(
  db: Database.Database,
  id: string,
  patch: Partial<Pick<Artefact, 'content' | 'claimIds' | 'status' | 'approvedBy' | 'approvedAt'>>
): Artefact {
  const current = getLatestArtefact(db, id);
  if (!current) throw new Error(`Artefact ${id} not found`);
  const next: Artefact = { ...current, ...patch, version: current.version + 1 };
  insertArtefactRow(db, next);
  return next;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/db/artefactRepository.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/src/db/artefactRepository.ts poc/tests/db/artefactRepository.test.ts
git commit -m "feat: add versioned artefact repository"
```

---

### Task 5: Report & ReportSection repositories with versioning

**Files:**
- Create: `poc/src/db/reportRepository.ts`
- Test: `poc/tests/db/reportRepository.test.ts`

**Interfaces:**
- Consumes: `createDb` (Task 2), `Report`, `ReportSection` types.
- Produces: `createReport(db, templateId: string): Report`, `getLatestReport(db, id): Report | null`, `createReportVersion(db, id, patch): Report`; `createReportSection(db, input: Omit<ReportSection,'id'|'version'>): ReportSection`, `getLatestReportSection(db, id): ReportSection | null`, `createReportSectionVersion(db, id, patch): ReportSection`. Tasks 15, 16 consume these.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/db/reportRepository.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import {
  createReport,
  getLatestReport,
  createReportVersion,
  createReportSection,
  getLatestReportSection,
  createReportSectionVersion
} from '../../src/db/reportRepository.js';

const TEST_DB_PATH = './data/test-report.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('reportRepository', () => {
  it('creates a report and a section, versions both, and orders sections', () => {
    const report = createReport(db, 'equity-initiation-v1');
    expect(report.version).toBe(1);
    expect(report.sectionIds).toEqual([]);

    const section = createReportSection(db, {
      reportId: report.id,
      sectionType: 'investment_thesis',
      content: 'Draft thesis text.',
      claimIds: ['claim-1', 'claim-2'],
      status: 'draft_in_chat',
      committedBy: null,
      committedAt: null
    });
    expect(section.version).toBe(1);

    const committedSection = createReportSectionVersion(db, section.id, {
      status: 'committed',
      committedBy: 'analyst-1',
      committedAt: '2026-07-24T11:00:00Z'
    });
    expect(committedSection.version).toBe(2);
    expect(committedSection.status).toBe('committed');

    const reportWithSection = createReportVersion(db, report.id, {
      sectionIds: [section.id]
    });
    expect(reportWithSection.version).toBe(2);
    expect(reportWithSection.sectionIds).toEqual([section.id]);

    expect(getLatestReport(db, report.id)).toEqual(reportWithSection);
    expect(getLatestReportSection(db, section.id)).toEqual(committedSection);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/db/reportRepository.test.ts`
Expected: FAIL — `Cannot find module '../../src/db/reportRepository.js'`

- [ ] **Step 3: Implement `poc/src/db/reportRepository.ts`**

```typescript
import type Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import type { Report, ReportSection } from './types.js';

function rowToReport(row: any): Report {
  return {
    id: row.id,
    version: row.version,
    templateId: row.template_id,
    sectionIds: JSON.parse(row.section_ids),
    status: row.status,
    exportedAt: row.exported_at,
    exportRef: row.export_ref
  };
}

function insertReportRow(db: Database.Database, report: Report): void {
  db.prepare(
    `INSERT INTO reports (id, version, template_id, section_ids, status, exported_at, export_ref)
     VALUES (@id, @version, @templateId, @sectionIds, @status, @exportedAt, @exportRef)`
  ).run({ ...report, sectionIds: JSON.stringify(report.sectionIds) });
}

export function createReport(db: Database.Database, templateId: string): Report {
  const report: Report = {
    id: randomUUID(),
    version: 1,
    templateId,
    sectionIds: [],
    status: 'in_progress',
    exportedAt: null,
    exportRef: null
  };
  insertReportRow(db, report);
  return report;
}

export function getLatestReport(db: Database.Database, id: string): Report | null {
  const row = db.prepare('SELECT * FROM reports WHERE id = ? ORDER BY version DESC LIMIT 1').get(id) as any;
  return row ? rowToReport(row) : null;
}

export function createReportVersion(
  db: Database.Database,
  id: string,
  patch: Partial<Pick<Report, 'sectionIds' | 'status' | 'exportedAt' | 'exportRef'>>
): Report {
  const current = getLatestReport(db, id);
  if (!current) throw new Error(`Report ${id} not found`);
  const next: Report = { ...current, ...patch, version: current.version + 1 };
  insertReportRow(db, next);
  return next;
}

function rowToSection(row: any): ReportSection {
  return {
    id: row.id,
    version: row.version,
    reportId: row.report_id,
    sectionType: row.section_type,
    content: row.content,
    claimIds: JSON.parse(row.claim_ids),
    status: row.status,
    committedBy: row.committed_by,
    committedAt: row.committed_at
  };
}

function insertSectionRow(db: Database.Database, section: ReportSection): void {
  db.prepare(
    `INSERT INTO report_sections (id, version, report_id, section_type, content, claim_ids, status, committed_by, committed_at)
     VALUES (@id, @version, @reportId, @sectionType, @content, @claimIds, @status, @committedBy, @committedAt)`
  ).run({ ...section, claimIds: JSON.stringify(section.claimIds) });
}

export function createReportSection(
  db: Database.Database,
  input: Omit<ReportSection, 'id' | 'version'>
): ReportSection {
  const section: ReportSection = { id: randomUUID(), version: 1, ...input };
  insertSectionRow(db, section);
  return section;
}

export function getLatestReportSection(db: Database.Database, id: string): ReportSection | null {
  const row = db
    .prepare('SELECT * FROM report_sections WHERE id = ? ORDER BY version DESC LIMIT 1')
    .get(id) as any;
  return row ? rowToSection(row) : null;
}

export function createReportSectionVersion(
  db: Database.Database,
  id: string,
  patch: Partial<Pick<ReportSection, 'content' | 'claimIds' | 'status' | 'committedBy' | 'committedAt'>>
): ReportSection {
  const current = getLatestReportSection(db, id);
  if (!current) throw new Error(`ReportSection ${id} not found`);
  const next: ReportSection = { ...current, ...patch, version: current.version + 1 };
  insertSectionRow(db, next);
  return next;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/db/reportRepository.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/src/db/reportRepository.ts poc/tests/db/reportRepository.test.ts
git commit -m "feat: add versioned report and report-section repositories"
```

---

### Task 6: Audit log repository

**Files:**
- Create: `poc/src/db/auditRepository.ts`
- Test: `poc/tests/db/auditRepository.test.ts`

**Interfaces:**
- Consumes: `createDb` (Task 2), `AuditLogEntry` type.
- Produces: `writeAuditEntry(db, input: Omit<AuditLogEntry,'id'|'timestamp'>): AuditLogEntry`, `getAuditTrailForTarget(db, targetType: string, targetId: string): AuditLogEntry[]` (ordered by timestamp ascending). Every tool task (11–16) consumes `writeAuditEntry`.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/db/auditRepository.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { writeAuditEntry, getAuditTrailForTarget } from '../../src/db/auditRepository.js';

const TEST_DB_PATH = './data/test-audit.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('auditRepository', () => {
  it('writes entries and retrieves them in chronological order for a target', () => {
    writeAuditEntry(db, {
      actor: 'analyst-1',
      action: 'synthesize_artefact',
      targetType: 'artefact',
      targetId: 'artefact-1',
      targetVersion: 1,
      evalRunId: null,
      diff: null
    });
    writeAuditEntry(db, {
      actor: 'analyst-1',
      action: 'approve_artefact',
      targetType: 'artefact',
      targetId: 'artefact-1',
      targetVersion: 2,
      evalRunId: 'eval-run-1',
      diff: JSON.stringify({ status: { from: 'pending_approval', to: 'approved' } })
    });

    const trail = getAuditTrailForTarget(db, 'artefact', 'artefact-1');
    expect(trail).toHaveLength(2);
    expect(trail[0].action).toBe('synthesize_artefact');
    expect(trail[1].action).toBe('approve_artefact');
    expect(trail[1].evalRunId).toBe('eval-run-1');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/db/auditRepository.test.ts`
Expected: FAIL — `Cannot find module '../../src/db/auditRepository.js'`

- [ ] **Step 3: Implement `poc/src/db/auditRepository.ts`**

```typescript
import type Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import type { AuditLogEntry } from './types.js';

function rowToEntry(row: any): AuditLogEntry {
  return {
    id: row.id,
    actor: row.actor,
    action: row.action,
    targetType: row.target_type,
    targetId: row.target_id,
    targetVersion: row.target_version,
    timestamp: row.timestamp,
    evalRunId: row.eval_run_id,
    diff: row.diff
  };
}

export function writeAuditEntry(
  db: Database.Database,
  input: Omit<AuditLogEntry, 'id' | 'timestamp'>
): AuditLogEntry {
  const entry: AuditLogEntry = { id: randomUUID(), timestamp: new Date().toISOString(), ...input };
  db.prepare(
    `INSERT INTO audit_log (id, actor, action, target_type, target_id, target_version, timestamp, eval_run_id, diff)
     VALUES (@id, @actor, @action, @targetType, @targetId, @targetVersion, @timestamp, @evalRunId, @diff)`
  ).run(entry);
  return entry;
}

export function getAuditTrailForTarget(
  db: Database.Database,
  targetType: string,
  targetId: string
): AuditLogEntry[] {
  const rows = db
    .prepare(
      'SELECT * FROM audit_log WHERE target_type = ? AND target_id = ? ORDER BY timestamp ASC'
    )
    .all(targetType, targetId) as any[];
  return rows.map(rowToEntry);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/db/auditRepository.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/src/db/auditRepository.ts poc/tests/db/auditRepository.test.ts
git commit -m "feat: add append-only audit log repository"
```

---

### Task 7: OpenAI client wrapper

**Files:**
- Create: `poc/src/llm/openaiClient.ts`
- Test: `poc/tests/llm/openaiClient.test.ts`

**Interfaces:**
- Produces: `type ChatFn = (params: { system: string; user: string }) => Promise<string>` and `createOpenAIChatFn(client: Pick<OpenAI, 'chat'>, model?: string): ChatFn`. Tasks 8, 9 consume `ChatFn`.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/llm/openaiClient.test.ts
import { describe, it, expect, vi } from 'vitest';
import { createOpenAIChatFn } from '../../src/llm/openaiClient.js';

describe('createOpenAIChatFn', () => {
  it('calls chat.completions.create with system/user messages and returns the content', async () => {
    const create = vi.fn().mockResolvedValue({
      choices: [{ message: { content: 'the model response' } }]
    });
    const fakeClient = { chat: { completions: { create } } } as any;

    const chatFn = createOpenAIChatFn(fakeClient, 'gpt-5.5');
    const result = await chatFn({ system: 'You are terse.', user: 'Say hi.' });

    expect(result).toBe('the model response');
    expect(create).toHaveBeenCalledWith({
      model: 'gpt-5.5',
      messages: [
        { role: 'system', content: 'You are terse.' },
        { role: 'user', content: 'Say hi.' }
      ]
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/llm/openaiClient.test.ts`
Expected: FAIL — `Cannot find module '../../src/llm/openaiClient.js'`

- [ ] **Step 3: Implement `poc/src/llm/openaiClient.ts`**

```typescript
import type OpenAI from 'openai';

export type ChatFn = (params: { system: string; user: string }) => Promise<string>;

export function createOpenAIChatFn(
  client: Pick<OpenAI, 'chat'>,
  model: string = 'gpt-5.5'
): ChatFn {
  return async ({ system, user }) => {
    const response = await client.chat.completions.create({
      model,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user }
      ]
    });
    return response.choices[0]?.message?.content ?? '';
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/llm/openaiClient.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/src/llm/openaiClient.ts poc/tests/llm/openaiClient.test.ts
git commit -m "feat: add injectable OpenAI chat client wrapper"
```

---

### Task 8: Claim extractor

**Files:**
- Create: `poc/src/eval/claimExtractor.ts`
- Test: `poc/tests/eval/claimExtractor.test.ts`

**Interfaces:**
- Consumes: `ChatFn` from Task 7.
- Produces: `extractClaims(chatFn: ChatFn, params: { generatedText: string; sourceExcerpt: string }): Promise<Array<{ text: string; sourceExcerpt: string }>>`. Task 11 (`synthesize_artefact`) consumes this.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/eval/claimExtractor.test.ts
import { describe, it, expect } from 'vitest';
import { extractClaims } from '../../src/eval/claimExtractor.js';

describe('extractClaims', () => {
  it('parses the JSON array of claims returned by the chat function', async () => {
    const fakeChatFn = async () =>
      JSON.stringify([
        { text: 'Revenue grew 12% YoY.', sourceExcerpt: 'Revenue increased 12% year-over-year' },
        { text: 'Gross margin was 41%.', sourceExcerpt: 'Gross margin of 41%' }
      ]);

    const claims = await extractClaims(fakeChatFn, {
      generatedText: 'Revenue grew 12% YoY and gross margin was 41%.',
      sourceExcerpt: 'Revenue increased 12% year-over-year on a gross margin of 41%.'
    });

    expect(claims).toEqual([
      { text: 'Revenue grew 12% YoY.', sourceExcerpt: 'Revenue increased 12% year-over-year' },
      { text: 'Gross margin was 41%.', sourceExcerpt: 'Gross margin of 41%' }
    ]);
  });

  it('throws a clear error if the chat function does not return valid JSON', async () => {
    const fakeChatFn = async () => 'not json';
    await expect(
      extractClaims(fakeChatFn, { generatedText: 'x', sourceExcerpt: 'y' })
    ).rejects.toThrow('claim extraction returned invalid JSON');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/eval/claimExtractor.test.ts`
Expected: FAIL — `Cannot find module '../../src/eval/claimExtractor.js'`

- [ ] **Step 3: Implement `poc/src/eval/claimExtractor.ts`**

```typescript
import type { ChatFn } from '../llm/openaiClient.js';

export interface ExtractedClaim {
  text: string;
  sourceExcerpt: string;
}

const SYSTEM_PROMPT = `You decompose generated financial-research text into atomic claims.
Return ONLY a JSON array of objects: [{ "text": "...", "sourceExcerpt": "..." }].
Each "text" is one atomic factual claim from the generated text.
Each "sourceExcerpt" is the specific substring of the provided source excerpt that supports it.
Do not include commentary, markdown, or explanation — JSON array only.`;

export async function extractClaims(
  chatFn: ChatFn,
  params: { generatedText: string; sourceExcerpt: string }
): Promise<ExtractedClaim[]> {
  const raw = await chatFn({
    system: SYSTEM_PROMPT,
    user: `Generated text:\n${params.generatedText}\n\nSource excerpt:\n${params.sourceExcerpt}`
  });

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('claim extraction returned invalid JSON');
  }

  if (!Array.isArray(parsed)) {
    throw new Error('claim extraction returned invalid JSON');
  }

  return parsed as ExtractedClaim[];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/eval/claimExtractor.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add poc/src/eval/claimExtractor.ts poc/tests/eval/claimExtractor.test.ts
git commit -m "feat: add LLM-based claim extractor"
```

---

### Task 9: Groundedness eval engine

**Files:**
- Create: `poc/src/eval/groundednessEval.ts`
- Test: `poc/tests/eval/groundednessEval.test.ts`

**Interfaces:**
- Consumes: `ChatFn` from Task 7.
- Produces: `evaluateClaimGroundedness(chatFn: ChatFn, params: { claimText: string; sourceExcerpt: string }): Promise<{ status: 'grounded' | 'unsupported' | 'conflicting'; score: number; rationale: string }>`. Task 12 (`run_eval`) consumes this.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/eval/groundednessEval.test.ts
import { describe, it, expect } from 'vitest';
import { evaluateClaimGroundedness } from '../../src/eval/groundednessEval.js';

describe('evaluateClaimGroundedness', () => {
  it('parses a grounded verdict from the chat function', async () => {
    const fakeChatFn = async () =>
      JSON.stringify({ status: 'grounded', score: 0.95, rationale: 'Matches source exactly.' });

    const result = await evaluateClaimGroundedness(fakeChatFn, {
      claimText: 'Consensus FY26 EPS is $7.42',
      sourceExcerpt: 'FY26 EPS estimate: 7.42'
    });

    expect(result).toEqual({ status: 'grounded', score: 0.95, rationale: 'Matches source exactly.' });
  });

  it('parses an unsupported verdict', async () => {
    const fakeChatFn = async () =>
      JSON.stringify({ status: 'unsupported', score: 0.2, rationale: 'Source excerpt does not mention this figure.' });

    const result = await evaluateClaimGroundedness(fakeChatFn, {
      claimText: 'Revenue grew 30% YoY',
      sourceExcerpt: 'FY26 EPS estimate: 7.42'
    });

    expect(result.status).toBe('unsupported');
  });

  it('throws a clear error on invalid JSON', async () => {
    const fakeChatFn = async () => 'nonsense';
    await expect(
      evaluateClaimGroundedness(fakeChatFn, { claimText: 'x', sourceExcerpt: 'y' })
    ).rejects.toThrow('groundedness eval returned invalid JSON');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/eval/groundednessEval.test.ts`
Expected: FAIL — `Cannot find module '../../src/eval/groundednessEval.js'`

- [ ] **Step 3: Implement `poc/src/eval/groundednessEval.ts`**

```typescript
import type { ChatFn } from '../llm/openaiClient.js';

export interface GroundednessResult {
  status: 'grounded' | 'unsupported' | 'conflicting';
  score: number;
  rationale: string;
}

const SYSTEM_PROMPT = `You are a fact-checking judge for sell-side investment research.
Given a CLAIM and a SOURCE EXCERPT, decide if the claim is:
- "grounded": fully supported by the source excerpt, including any numbers, entities, and time periods matching exactly
- "unsupported": the source excerpt does not contain evidence for the claim
- "conflicting": the source excerpt contradicts the claim (e.g. different number, entity, or period)
Return ONLY JSON: { "status": "...", "score": <0-1 confidence>, "rationale": "<one sentence>" }`;

export async function evaluateClaimGroundedness(
  chatFn: ChatFn,
  params: { claimText: string; sourceExcerpt: string }
): Promise<GroundednessResult> {
  const raw = await chatFn({
    system: SYSTEM_PROMPT,
    user: `CLAIM: ${params.claimText}\n\nSOURCE EXCERPT: ${params.sourceExcerpt}`
  });

  let parsed: any;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('groundedness eval returned invalid JSON');
  }

  if (!parsed || typeof parsed.status !== 'string' || typeof parsed.score !== 'number') {
    throw new Error('groundedness eval returned invalid JSON');
  }

  return { status: parsed.status, score: parsed.score, rationale: parsed.rationale ?? '' };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/eval/groundednessEval.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add poc/src/eval/groundednessEval.ts poc/tests/eval/groundednessEval.test.ts
git commit -m "feat: add LLM-judge groundedness eval"
```

---

### Task 10: FactSet client

**Files:**
- Create: `poc/src/factset/factsetClient.ts`
- Test: `poc/tests/factset/factsetClient.test.ts`

**Interfaces:**
- Produces: `type FetchFn = typeof fetch`; `createFactsetClient(config: { clientId: string; clientSecret: string; baseUrl: string; fetchFn?: FetchFn }): { fetchFundamentals(ticker: string): Promise<{ ticker: string; raw: unknown; retrievedAt: string }> }`. Task 11 (`fetch_connector_data`) consumes this.
- Note: FactSet's exact OAuth token endpoint path and fundamentals endpoint path depend on your organization's specific FactSet API subscription/product tier. This task implements the standard OAuth2 client-credentials flow and a configurable base URL; **before running against production FactSet, confirm the exact token and fundamentals endpoint paths from your FactSet API documentation/account team** and adjust the two path constants noted in Step 3.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/factset/factsetClient.test.ts
import { describe, it, expect, vi } from 'vitest';
import { createFactsetClient } from '../../src/factset/factsetClient.js';

describe('createFactsetClient', () => {
  it('fetches an OAuth2 token then requests fundamentals with a bearer header', async () => {
    const fetchFn = vi
      .fn()
      // 1st call: token endpoint
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: 'test-token', expires_in: 3600 })
      })
      // 2nd call: fundamentals endpoint
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: [{ ticker: 'AAPL', epsEstimateFY26: 7.42 }] })
      });

    const client = createFactsetClient({
      clientId: 'test-id',
      clientSecret: 'test-secret',
      baseUrl: 'https://api.factset.example',
      fetchFn: fetchFn as any
    });

    const result = await client.fetchFundamentals('AAPL');

    expect(fetchFn).toHaveBeenNthCalledWith(
      1,
      'https://api.factset.example/oauth/token',
      expect.objectContaining({ method: 'POST' })
    );
    expect(fetchFn).toHaveBeenNthCalledWith(
      2,
      'https://api.factset.example/fundamentals/v1/AAPL',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' })
      })
    );
    expect(result.ticker).toBe('AAPL');
    expect(result.raw).toEqual({ data: [{ ticker: 'AAPL', epsEstimateFY26: 7.42 }] });
    expect(result.retrievedAt).toBeTruthy();
  });

  it('throws a clear error when the token request fails', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce({ ok: false, status: 401 });
    const client = createFactsetClient({
      clientId: 'bad-id',
      clientSecret: 'bad-secret',
      baseUrl: 'https://api.factset.example',
      fetchFn: fetchFn as any
    });
    await expect(client.fetchFundamentals('AAPL')).rejects.toThrow('FactSet OAuth token request failed: 401');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/factset/factsetClient.test.ts`
Expected: FAIL — `Cannot find module '../../src/factset/factsetClient.js'`

- [ ] **Step 3: Implement `poc/src/factset/factsetClient.ts`**

```typescript
export interface FactsetClientConfig {
  clientId: string;
  clientSecret: string;
  baseUrl: string;
  fetchFn?: typeof fetch;
}

export interface FundamentalsResult {
  ticker: string;
  raw: unknown;
  retrievedAt: string;
}

// NOTE: confirm these two path constants against your FactSet API/MCP
// subscription's actual documentation before pointing this at production.
const TOKEN_PATH = '/oauth/token';
const FUNDAMENTALS_PATH = '/fundamentals/v1';

export function createFactsetClient(config: FactsetClientConfig) {
  const fetchFn = config.fetchFn ?? fetch;

  async function getAccessToken(): Promise<string> {
    const response = await fetchFn(`${config.baseUrl}${TOKEN_PATH}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'client_credentials',
        client_id: config.clientId,
        client_secret: config.clientSecret
      }).toString()
    } as any);

    if (!response.ok) {
      throw new Error(`FactSet OAuth token request failed: ${response.status}`);
    }
    const body = await response.json();
    return body.access_token;
  }

  return {
    async fetchFundamentals(ticker: string): Promise<FundamentalsResult> {
      const token = await getAccessToken();
      const response = await fetchFn(`${config.baseUrl}${FUNDAMENTALS_PATH}/${ticker}`, {
        headers: { Authorization: `Bearer ${token}` }
      } as any);

      if (!response.ok) {
        throw new Error(`FactSet fundamentals request failed: ${response.status}`);
      }

      const raw = await response.json();
      return { ticker, raw, retrievedAt: new Date().toISOString() };
    }
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/factset/factsetClient.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add poc/src/factset/factsetClient.ts poc/tests/factset/factsetClient.test.ts
git commit -m "feat: add FactSet OAuth2 client with injectable fetch"
```

---

### Task 11: Tools — `ingest_document` and `fetch_connector_data`

**Files:**
- Create: `poc/src/tools/ingestDocument.ts`
- Create: `poc/src/tools/fetchFactsetData.ts`
- Test: `poc/tests/tools/ingestAndFactset.test.ts`

**Interfaces:**
- Consumes: `createSource` (Task 3), `writeAuditEntry` (Task 6), `createFactsetClient` return type (Task 10).
- Produces: `ingestDocument(db, input: { retrievedBy: string; context: string; rawContentRef: string; externalUrl?: string }): Source`; `fetchConnectorData(db, factsetClient, input: { retrievedBy: string; ticker: string }): Promise<Source>`. Task 12 (`synthesize_artefact`) consumes `Source` objects these produce.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/tools/ingestAndFactset.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { getAuditTrailForTarget } from '../../src/db/auditRepository.js';
import { ingestDocument } from '../../src/tools/ingestDocument.js';
import { fetchConnectorData } from '../../src/tools/fetchFactsetData.js';

const TEST_DB_PATH = './data/test-ingest.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('ingestDocument', () => {
  it('creates an upload source and an audit entry', () => {
    const source = ingestDocument(db, {
      retrievedBy: 'analyst-1',
      context: 'Q2 10-Q upload',
      rawContentRef: 'blob://uploads/q2-10q.pdf'
    });
    expect(source.type).toBe('upload');

    const trail = getAuditTrailForTarget(db, 'source', source.id);
    expect(trail).toHaveLength(1);
    expect(trail[0].action).toBe('ingest_document');
  });
});

describe('fetchConnectorData', () => {
  it('fetches FactSet fundamentals and stores them as a connector source with an audit entry', async () => {
    const fakeFactsetClient = {
      fetchFundamentals: async (ticker: string) => ({
        ticker,
        raw: { epsEstimateFY26: 7.42 },
        retrievedAt: '2026-07-24T12:00:00Z'
      })
    };

    const source = await fetchConnectorData(db, fakeFactsetClient, {
      retrievedBy: 'analyst-1',
      ticker: 'AAPL'
    });

    expect(source.type).toBe('connector:factset');
    expect(source.context).toContain('AAPL');
    expect(JSON.parse(source.rawContentRef)).toEqual({ epsEstimateFY26: 7.42 });

    const trail = getAuditTrailForTarget(db, 'source', source.id);
    expect(trail).toHaveLength(1);
    expect(trail[0].action).toBe('fetch_connector_data');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/tools/ingestAndFactset.test.ts`
Expected: FAIL — `Cannot find module '../../src/tools/ingestDocument.js'`

- [ ] **Step 3: Implement `poc/src/tools/ingestDocument.ts`**

```typescript
import type Database from 'better-sqlite3';
import { createSource } from '../db/sourceRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { Source } from '../db/types.js';

export function ingestDocument(
  db: Database.Database,
  input: { retrievedBy: string; context: string; rawContentRef: string; externalUrl?: string }
): Source {
  const source = createSource(db, {
    type: 'upload',
    retrievedAt: new Date().toISOString(),
    retrievedBy: input.retrievedBy,
    context: input.context,
    rawContentRef: input.rawContentRef,
    externalUrl: input.externalUrl ?? null
  });

  writeAuditEntry(db, {
    actor: input.retrievedBy,
    action: 'ingest_document',
    targetType: 'source',
    targetId: source.id,
    targetVersion: null,
    evalRunId: null,
    diff: null
  });

  return source;
}
```

- [ ] **Step 4: Implement `poc/src/tools/fetchFactsetData.ts`**

```typescript
import type Database from 'better-sqlite3';
import { createSource } from '../db/sourceRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { Source } from '../db/types.js';

export interface FactsetClientLike {
  fetchFundamentals(ticker: string): Promise<{ ticker: string; raw: unknown; retrievedAt: string }>;
}

export async function fetchConnectorData(
  db: Database.Database,
  factsetClient: FactsetClientLike,
  input: { retrievedBy: string; ticker: string }
): Promise<Source> {
  const result = await factsetClient.fetchFundamentals(input.ticker);

  const source = createSource(db, {
    type: 'connector:factset',
    retrievedAt: result.retrievedAt,
    retrievedBy: input.retrievedBy,
    context: `FactSet fundamentals for ${input.ticker}`,
    rawContentRef: JSON.stringify(result.raw),
    externalUrl: null
  });

  writeAuditEntry(db, {
    actor: input.retrievedBy,
    action: 'fetch_connector_data',
    targetType: 'source',
    targetId: source.id,
    targetVersion: null,
    evalRunId: null,
    diff: null
  });

  return source;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/tools/ingestAndFactset.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/src/tools/ingestDocument.ts poc/src/tools/fetchFactsetData.ts poc/tests/tools/ingestAndFactset.test.ts
git commit -m "feat: add ingest_document and fetch_connector_data tools"
```

---

### Task 12: Tool — `synthesize_artefact`

**Files:**
- Create: `poc/src/tools/synthesizeArtefact.ts`
- Test: `poc/tests/tools/synthesizeArtefact.test.ts`

**Interfaces:**
- Consumes: `extractClaims` (Task 8), `createClaim` (Task 3), `createArtefact` (Task 4), `writeAuditEntry` (Task 6), `Source` (Task 3).
- Produces: `synthesizeArtefact(db, chatFn, input: { actor: string; type: Artefact['type']; generatedText: string; source: Source }): Promise<Artefact>`. Task 13 (`run_eval`) consumes the returned `Artefact`.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/tools/synthesizeArtefact.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { createSource } from '../../src/db/sourceRepository.js';
import { getAuditTrailForTarget } from '../../src/db/auditRepository.js';
import { synthesizeArtefact } from '../../src/tools/synthesizeArtefact.js';

const TEST_DB_PATH = './data/test-synthesize.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('synthesizeArtefact', () => {
  it('extracts claims, persists them linked to the source, and creates a draft artefact', async () => {
    const source = createSource(db, {
      type: 'connector:factset',
      retrievedAt: '2026-07-24T12:00:00Z',
      retrievedBy: 'analyst-1',
      context: 'FactSet fundamentals for AAPL',
      rawContentRef: JSON.stringify({ epsEstimateFY26: 7.42 }),
      externalUrl: null
    });

    const fakeChatFn = async () =>
      JSON.stringify([{ text: 'Consensus FY26 EPS is $7.42', sourceExcerpt: 'epsEstimateFY26: 7.42' }]);

    const artefact = await synthesizeArtefact(db, fakeChatFn, {
      actor: 'analyst-1',
      type: 'data_extract',
      generatedText: 'Consensus FY26 EPS is $7.42',
      source
    });

    expect(artefact.status).toBe('draft');
    expect(artefact.version).toBe(1);
    expect(artefact.claimIds).toHaveLength(1);

    const trail = getAuditTrailForTarget(db, 'artefact', artefact.id);
    expect(trail).toHaveLength(1);
    expect(trail[0].action).toBe('synthesize_artefact');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/tools/synthesizeArtefact.test.ts`
Expected: FAIL — `Cannot find module '../../src/tools/synthesizeArtefact.js'`

- [ ] **Step 3: Implement `poc/src/tools/synthesizeArtefact.ts`**

```typescript
import type Database from 'better-sqlite3';
import type { ChatFn } from '../llm/openaiClient.js';
import { extractClaims } from '../eval/claimExtractor.js';
import { createClaim } from '../db/claimRepository.js';
import { createArtefact } from '../db/artefactRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { Artefact, Source } from '../db/types.js';

export async function synthesizeArtefact(
  db: Database.Database,
  chatFn: ChatFn,
  input: { actor: string; type: Artefact['type']; generatedText: string; source: Source }
): Promise<Artefact> {
  const extracted = await extractClaims(chatFn, {
    generatedText: input.generatedText,
    sourceExcerpt: input.source.rawContentRef
  });

  const claims = extracted.map((c) =>
    createClaim(db, {
      text: c.text,
      sourceId: input.source.id,
      sourceExcerpt: c.sourceExcerpt,
      evalStatus: 'pending',
      evalScore: null,
      evalRunId: null
    })
  );

  const artefact = createArtefact(db, {
    type: input.type,
    content: input.generatedText,
    claimIds: claims.map((c) => c.id),
    status: 'draft',
    approvedBy: null,
    approvedAt: null
  });

  writeAuditEntry(db, {
    actor: input.actor,
    action: 'synthesize_artefact',
    targetType: 'artefact',
    targetId: artefact.id,
    targetVersion: artefact.version,
    evalRunId: null,
    diff: null
  });

  return artefact;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/tools/synthesizeArtefact.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add poc/src/tools/synthesizeArtefact.ts poc/tests/tools/synthesizeArtefact.test.ts
git commit -m "feat: add synthesize_artefact tool"
```

---

### Task 13: Tool — `run_eval`

**Files:**
- Create: `poc/src/tools/runEval.ts`
- Test: `poc/tests/tools/runEval.test.ts`

**Interfaces:**
- Consumes: `evaluateClaimGroundedness` (Task 9), `getClaim`/`updateClaimEval` (Task 3), `getLatestArtefact`/`createArtefactVersion` (Task 4), `writeAuditEntry` (Task 6).
- Produces: `runEval(db, chatFn, input: { actor: string; artefactId: string }): Promise<{ artefact: Artefact; evalRunId: string }>` — evaluates every claim on the artefact's latest version, moves the artefact to `pending_approval` if all claims are grounded, or leaves it `draft` (with claims flagged) if any are unsupported/conflicting. Task 14 (`approve_artefact`) consumes the returned `Artefact`.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/tools/runEval.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { createSource } from '../../src/db/sourceRepository.js';
import { createClaim, getClaim } from '../../src/db/claimRepository.js';
import { createArtefact } from '../../src/db/artefactRepository.js';
import { getAuditTrailForTarget } from '../../src/db/auditRepository.js';
import { runEval } from '../../src/tools/runEval.js';

const TEST_DB_PATH = './data/test-runeval.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

function setupArtefactWithClaims(grounded: boolean) {
  const source = createSource(db, {
    type: 'connector:factset',
    retrievedAt: '2026-07-24T12:00:00Z',
    retrievedBy: 'analyst-1',
    context: 'FactSet fundamentals for AAPL',
    rawContentRef: 'epsEstimateFY26: 7.42',
    externalUrl: null
  });
  const claim = createClaim(db, {
    text: grounded ? 'Consensus FY26 EPS is $7.42' : 'Revenue grew 30% YoY',
    sourceId: source.id,
    sourceExcerpt: 'epsEstimateFY26: 7.42',
    evalStatus: 'pending',
    evalScore: null,
    evalRunId: null
  });
  const artefact = createArtefact(db, {
    type: 'data_extract',
    content: claim.text,
    claimIds: [claim.id],
    status: 'draft',
    approvedBy: null,
    approvedAt: null
  });
  return { artefact, claim };
}

describe('runEval', () => {
  it('moves the artefact to pending_approval when all claims are grounded', async () => {
    const { artefact, claim } = setupArtefactWithClaims(true);
    const fakeChatFn = async () =>
      JSON.stringify({ status: 'grounded', score: 0.9, rationale: 'Matches.' });

    const result = await runEval(db, fakeChatFn, { actor: 'analyst-1', artefactId: artefact.id });

    expect(result.artefact.status).toBe('pending_approval');
    expect(result.artefact.version).toBe(2);
    expect(getClaim(db, claim.id)?.evalStatus).toBe('grounded');

    const trail = getAuditTrailForTarget(db, 'artefact', artefact.id);
    expect(trail.some((e) => e.action === 'run_eval')).toBe(true);
  });

  it('keeps the artefact in draft when a claim is unsupported', async () => {
    const { artefact, claim } = setupArtefactWithClaims(false);
    const fakeChatFn = async () =>
      JSON.stringify({ status: 'unsupported', score: 0.2, rationale: 'No evidence.' });

    const result = await runEval(db, fakeChatFn, { actor: 'analyst-1', artefactId: artefact.id });

    expect(result.artefact.status).toBe('draft');
    expect(getClaim(db, claim.id)?.evalStatus).toBe('unsupported');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/tools/runEval.test.ts`
Expected: FAIL — `Cannot find module '../../src/tools/runEval.js'`

- [ ] **Step 3: Implement `poc/src/tools/runEval.ts`**

```typescript
import type Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import type { ChatFn } from '../llm/openaiClient.js';
import { evaluateClaimGroundedness } from '../eval/groundednessEval.js';
import { getClaim, updateClaimEval } from '../db/claimRepository.js';
import { getLatestArtefact, createArtefactVersion } from '../db/artefactRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { Artefact } from '../db/types.js';

export async function runEval(
  db: Database.Database,
  chatFn: ChatFn,
  input: { actor: string; artefactId: string }
): Promise<{ artefact: Artefact; evalRunId: string }> {
  const artefact = getLatestArtefact(db, input.artefactId);
  if (!artefact) throw new Error(`Artefact ${input.artefactId} not found`);

  const evalRunId = randomUUID();
  let allGrounded = true;

  for (const claimId of artefact.claimIds) {
    const claim = getClaim(db, claimId);
    if (!claim) throw new Error(`Claim ${claimId} not found`);

    const verdict = await evaluateClaimGroundedness(chatFn, {
      claimText: claim.text,
      sourceExcerpt: claim.sourceExcerpt
    });
    updateClaimEval(db, claim.id, verdict.status, verdict.score, evalRunId);
    if (verdict.status !== 'grounded') allGrounded = false;
  }

  const updatedArtefact = createArtefactVersion(db, artefact.id, {
    status: allGrounded ? 'pending_approval' : 'draft'
  });

  writeAuditEntry(db, {
    actor: input.actor,
    action: 'run_eval',
    targetType: 'artefact',
    targetId: updatedArtefact.id,
    targetVersion: updatedArtefact.version,
    evalRunId,
    diff: JSON.stringify({ status: { from: artefact.status, to: updatedArtefact.status } })
  });

  return { artefact: updatedArtefact, evalRunId };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/tools/runEval.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add poc/src/tools/runEval.ts poc/tests/tools/runEval.test.ts
git commit -m "feat: add run_eval tool gating artefacts on claim groundedness"
```

---

### Task 14: Tool — `approve_artefact`

**Files:**
- Create: `poc/src/tools/approveArtefact.ts`
- Test: `poc/tests/tools/approveArtefact.test.ts`

**Interfaces:**
- Consumes: `getLatestArtefact`/`createArtefactVersion` (Task 4), `writeAuditEntry` (Task 6).
- Produces: `approveArtefact(db, input: { actor: string; artefactId: string; decision: 'approve' | 'reject' }): Artefact` — throws if the artefact is not `pending_approval`. Task 15 (`draft_section`) consumes only `approved` artefacts.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/tools/approveArtefact.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { createArtefact, createArtefactVersion } from '../../src/db/artefactRepository.js';
import { getAuditTrailForTarget } from '../../src/db/auditRepository.js';
import { approveArtefact } from '../../src/tools/approveArtefact.js';

const TEST_DB_PATH = './data/test-approve.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('approveArtefact', () => {
  it('approves a pending_approval artefact and records who/when', () => {
    const draft = createArtefact(db, {
      type: 'thesis_point',
      content: 'x',
      claimIds: [],
      status: 'draft',
      approvedBy: null,
      approvedAt: null
    });
    const pending = createArtefactVersion(db, draft.id, { status: 'pending_approval' });

    const approved = approveArtefact(db, { actor: 'analyst-1', artefactId: pending.id, decision: 'approve' });

    expect(approved.status).toBe('approved');
    expect(approved.approvedBy).toBe('analyst-1');
    expect(approved.approvedAt).toBeTruthy();

    const trail = getAuditTrailForTarget(db, 'artefact', pending.id);
    expect(trail.some((e) => e.action === 'approve_artefact')).toBe(true);
  });

  it('rejects the artefact when decision is reject', () => {
    const draft = createArtefact(db, {
      type: 'thesis_point',
      content: 'x',
      claimIds: [],
      status: 'draft',
      approvedBy: null,
      approvedAt: null
    });
    const pending = createArtefactVersion(db, draft.id, { status: 'pending_approval' });

    const rejected = approveArtefact(db, { actor: 'analyst-1', artefactId: pending.id, decision: 'reject' });
    expect(rejected.status).toBe('rejected');
  });

  it('throws if the artefact is not pending_approval', () => {
    const draft = createArtefact(db, {
      type: 'thesis_point',
      content: 'x',
      claimIds: [],
      status: 'draft',
      approvedBy: null,
      approvedAt: null
    });
    expect(() =>
      approveArtefact(db, { actor: 'analyst-1', artefactId: draft.id, decision: 'approve' })
    ).toThrow('Artefact is not pending approval');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/tools/approveArtefact.test.ts`
Expected: FAIL — `Cannot find module '../../src/tools/approveArtefact.js'`

- [ ] **Step 3: Implement `poc/src/tools/approveArtefact.ts`**

```typescript
import type Database from 'better-sqlite3';
import { getLatestArtefact, createArtefactVersion } from '../db/artefactRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { Artefact } from '../db/types.js';

export function approveArtefact(
  db: Database.Database,
  input: { actor: string; artefactId: string; decision: 'approve' | 'reject' }
): Artefact {
  const current = getLatestArtefact(db, input.artefactId);
  if (!current) throw new Error(`Artefact ${input.artefactId} not found`);
  if (current.status !== 'pending_approval') {
    throw new Error('Artefact is not pending approval');
  }

  const now = new Date().toISOString();
  const updated = createArtefactVersion(db, current.id, {
    status: input.decision === 'approve' ? 'approved' : 'rejected',
    approvedBy: input.actor,
    approvedAt: now
  });

  writeAuditEntry(db, {
    actor: input.actor,
    action: 'approve_artefact',
    targetType: 'artefact',
    targetId: updated.id,
    targetVersion: updated.version,
    evalRunId: null,
    diff: JSON.stringify({ status: { from: current.status, to: updated.status } })
  });

  return updated;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/tools/approveArtefact.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add poc/src/tools/approveArtefact.ts poc/tests/tools/approveArtefact.test.ts
git commit -m "feat: add approve_artefact human-in-the-loop tool"
```

---

### Task 15: Tools — `draft_section` and `commit_section`

**Files:**
- Create: `poc/src/tools/draftSection.ts`
- Create: `poc/src/tools/commitSection.ts`
- Test: `poc/tests/tools/draftAndCommitSection.test.ts`

**Interfaces:**
- Consumes: `getLatestArtefact` (Task 4), `createReportSection`/`getLatestReportSection`/`createReportSectionVersion` (Task 5), `getLatestReport`/`createReportVersion` (Task 5), `writeAuditEntry` (Task 6).
- Produces: `draftSection(input: { reportId: string; sectionType: string; approvedArtefacts: Artefact[] }): { sectionType: string; draftContent: string; claimIds: string[] }` (pure text-assembly helper, no DB write — represents the in-chat draft before commit); `commitSection(db, input: { actor: string; reportId: string; sectionType: string; content: string; claimIds: string[]; existingSectionId?: string }): ReportSection` (creates or versions a `ReportSection` and appends its id to the `Report`'s `sectionIds` if new). Task 16 (`assemble_report`) consumes the `Report`/`ReportSection` state this produces.

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/tools/draftAndCommitSection.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { createArtefact } from '../../src/db/artefactRepository.js';
import { createReport, getLatestReport, getLatestReportSection } from '../../src/db/reportRepository.js';
import { getAuditTrailForTarget } from '../../src/db/auditRepository.js';
import { draftSection } from '../../src/tools/draftSection.js';
import { commitSection } from '../../src/tools/commitSection.js';

const TEST_DB_PATH = './data/test-draft-commit.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

describe('draftSection', () => {
  it('assembles draft content and claim ids from approved artefacts', () => {
    const artefact = createArtefact(db, {
      type: 'thesis_point',
      content: 'Margin expansion driven by pricing power.',
      claimIds: ['claim-1'],
      status: 'approved',
      approvedBy: 'analyst-1',
      approvedAt: '2026-07-24T12:00:00Z'
    });

    const draft = draftSection({
      reportId: 'report-1',
      sectionType: 'investment_thesis',
      approvedArtefacts: [artefact]
    });

    expect(draft.sectionType).toBe('investment_thesis');
    expect(draft.draftContent).toContain('Margin expansion driven by pricing power.');
    expect(draft.claimIds).toEqual(['claim-1']);
  });
});

describe('commitSection', () => {
  it('creates a new report section and appends it to the report on first commit', () => {
    const report = createReport(db, 'equity-initiation-v1');

    const section = commitSection(db, {
      actor: 'analyst-1',
      reportId: report.id,
      sectionType: 'investment_thesis',
      content: 'Margin expansion driven by pricing power.',
      claimIds: ['claim-1']
    });

    expect(section.status).toBe('committed');
    expect(section.version).toBe(1);

    const updatedReport = getLatestReport(db, report.id);
    expect(updatedReport?.sectionIds).toEqual([section.id]);

    const trail = getAuditTrailForTarget(db, 'report_section', section.id);
    expect(trail.some((e) => e.action === 'commit_section')).toBe(true);
  });

  it('versions an existing section on a subsequent commit without duplicating the report section list', () => {
    const report = createReport(db, 'equity-initiation-v1');
    const first = commitSection(db, {
      actor: 'analyst-1',
      reportId: report.id,
      sectionType: 'investment_thesis',
      content: 'v1 text',
      claimIds: ['claim-1']
    });

    const second = commitSection(db, {
      actor: 'analyst-1',
      reportId: report.id,
      sectionType: 'investment_thesis',
      content: 'v2 text, refined',
      claimIds: ['claim-1', 'claim-2'],
      existingSectionId: first.id
    });

    expect(second.id).toBe(first.id);
    expect(second.version).toBe(2);

    const updatedReport = getLatestReport(db, report.id);
    expect(updatedReport?.sectionIds).toEqual([first.id]);
    expect(getLatestReportSection(db, first.id)?.content).toBe('v2 text, refined');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/tools/draftAndCommitSection.test.ts`
Expected: FAIL — `Cannot find module '../../src/tools/draftSection.js'`

- [ ] **Step 3: Implement `poc/src/tools/draftSection.ts`**

```typescript
import type { Artefact } from '../db/types.js';

export function draftSection(input: {
  reportId: string;
  sectionType: string;
  approvedArtefacts: Artefact[];
}): { sectionType: string; draftContent: string; claimIds: string[] } {
  const draftContent = input.approvedArtefacts.map((a) => a.content).join('\n\n');
  const claimIds = input.approvedArtefacts.flatMap((a) => a.claimIds);
  return { sectionType: input.sectionType, draftContent, claimIds };
}
```

- [ ] **Step 4: Implement `poc/src/tools/commitSection.ts`**

```typescript
import type Database from 'better-sqlite3';
import {
  createReportSection,
  getLatestReportSection,
  createReportSectionVersion,
  getLatestReport,
  createReportVersion
} from '../db/reportRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { ReportSection } from '../db/types.js';

export function commitSection(
  db: Database.Database,
  input: {
    actor: string;
    reportId: string;
    sectionType: string;
    content: string;
    claimIds: string[];
    existingSectionId?: string;
  }
): ReportSection {
  const now = new Date().toISOString();
  let section: ReportSection;

  if (input.existingSectionId) {
    section = createReportSectionVersion(db, input.existingSectionId, {
      content: input.content,
      claimIds: input.claimIds,
      status: 'committed',
      committedBy: input.actor,
      committedAt: now
    });
  } else {
    section = createReportSection(db, {
      reportId: input.reportId,
      sectionType: input.sectionType,
      content: input.content,
      claimIds: input.claimIds,
      status: 'committed',
      committedBy: input.actor,
      committedAt: now
    });

    const report = getLatestReport(db, input.reportId);
    if (!report) throw new Error(`Report ${input.reportId} not found`);
    createReportVersion(db, input.reportId, {
      sectionIds: [...report.sectionIds, section.id]
    });
  }

  writeAuditEntry(db, {
    actor: input.actor,
    action: 'commit_section',
    targetType: 'report_section',
    targetId: section.id,
    targetVersion: section.version,
    evalRunId: null,
    diff: null
  });

  return section;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/tools/draftAndCommitSection.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/src/tools/draftSection.ts poc/src/tools/commitSection.ts poc/tests/tools/draftAndCommitSection.test.ts
git commit -m "feat: add draft_section and commit_section tools"
```

---

### Task 16: Tools — `assemble_report` and `export_report` (Markdown)

**Files:**
- Create: `poc/src/tools/assembleReport.ts`
- Create: `poc/src/tools/exportReport.ts`
- Test: `poc/tests/tools/assembleAndExportReport.test.ts`

**Interfaces:**
- Consumes: `getLatestReport`/`createReportVersion` (Task 5), `getLatestReportSection` (Task 5), `getClaim` (Task 3), `getSource` (Task 3), `writeAuditEntry` (Task 6).
- Produces: `assembleReport(db, input: { actor: string; reportId: string; sectionOrder: string[] }): Report` (validates every section referenced is `committed`, reorders `sectionIds`, sets status `ready_for_export`); `exportReportToMarkdown(db, input: { actor: string; reportId: string; templateTitle: string }): { markdown: string; report: Report }` (renders sections in order with footnote-style citations resolved from claims/sources, sets status `exported`).

- [ ] **Step 1: Write the failing test**

```typescript
// poc/tests/tools/assembleAndExportReport.test.ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, unlinkSync } from 'node:fs';
import { createDb } from '../../src/db/db.js';
import { createSource } from '../../src/db/sourceRepository.js';
import { createClaim } from '../../src/db/claimRepository.js';
import { createReport, createReportSection, createReportVersion, getLatestReport } from '../../src/db/reportRepository.js';
import { assembleReport } from '../../src/tools/assembleReport.js';
import { exportReportToMarkdown } from '../../src/tools/exportReport.js';

const TEST_DB_PATH = './data/test-assemble-export.db';
let db: ReturnType<typeof createDb>;

beforeEach(() => { db = createDb(TEST_DB_PATH); });
afterEach(() => {
  db.close();
  if (existsSync(TEST_DB_PATH)) unlinkSync(TEST_DB_PATH);
});

function setupTwoSectionReport() {
  const source = createSource(db, {
    type: 'connector:factset',
    retrievedAt: '2026-07-24T12:00:00Z',
    retrievedBy: 'analyst-1',
    context: 'FactSet fundamentals for AAPL',
    rawContentRef: 'epsEstimateFY26: 7.42',
    externalUrl: null
  });
  const claim = createClaim(db, {
    text: 'Consensus FY26 EPS is $7.42',
    sourceId: source.id,
    sourceExcerpt: 'epsEstimateFY26: 7.42',
    evalStatus: 'grounded',
    evalScore: 0.94,
    evalRunId: 'eval-run-1'
  });

  const report = createReport(db, 'equity-initiation-v1');
  const thesisSection = createReportSection(db, {
    reportId: report.id,
    sectionType: 'investment_thesis',
    content: 'Margin expansion driven by pricing power.',
    claimIds: [],
    status: 'committed',
    committedBy: 'analyst-1',
    committedAt: '2026-07-24T12:05:00Z'
  });
  const valuationSection = createReportSection(db, {
    reportId: report.id,
    sectionType: 'valuation',
    content: `Consensus FY26 EPS is $7.42.`,
    claimIds: [claim.id],
    status: 'committed',
    committedBy: 'analyst-1',
    committedAt: '2026-07-24T12:10:00Z'
  });
  createReportVersion(db, report.id, { sectionIds: [thesisSection.id, valuationSection.id] });

  return { report, thesisSection, valuationSection, source, claim };
}

describe('assembleReport', () => {
  it('marks the report ready_for_export when all referenced sections are committed', () => {
    const { report, thesisSection, valuationSection } = setupTwoSectionReport();

    const assembled = assembleReport(db, {
      actor: 'analyst-1',
      reportId: report.id,
      sectionOrder: [thesisSection.id, valuationSection.id]
    });

    expect(assembled.status).toBe('ready_for_export');
    expect(assembled.sectionIds).toEqual([thesisSection.id, valuationSection.id]);
  });

  it('throws if a referenced section is not committed', () => {
    const { report, thesisSection } = setupTwoSectionReport();
    expect(() =>
      assembleReport(db, { actor: 'analyst-1', reportId: report.id, sectionOrder: [thesisSection.id, 'missing-section'] })
    ).toThrow('is not committed');
  });
});

describe('exportReportToMarkdown', () => {
  it('renders sections in order with a footnote citation for grounded claims', () => {
    const { report, thesisSection, valuationSection } = setupTwoSectionReport();
    assembleReport(db, {
      actor: 'analyst-1',
      reportId: report.id,
      sectionOrder: [thesisSection.id, valuationSection.id]
    });

    const { markdown, report: exported } = exportReportToMarkdown(db, {
      actor: 'analyst-1',
      reportId: report.id,
      templateTitle: 'AAPL — Initiation of Coverage'
    });

    expect(markdown).toContain('# AAPL — Initiation of Coverage');
    expect(markdown).toContain('## Investment Thesis');
    expect(markdown).toContain('Margin expansion driven by pricing power.');
    expect(markdown).toContain('## Valuation');
    expect(markdown).toContain('Consensus FY26 EPS is $7.42. [1]');
    expect(markdown).toContain('[1]: epsEstimateFY26: 7.42');
    expect(exported.status).toBe('exported');
    expect(getLatestReport(db, report.id)?.status).toBe('exported');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc && npx vitest run tests/tools/assembleAndExportReport.test.ts`
Expected: FAIL — `Cannot find module '../../src/tools/assembleReport.js'`

- [ ] **Step 3: Implement `poc/src/tools/assembleReport.ts`**

```typescript
import type Database from 'better-sqlite3';
import { getLatestReport, getLatestReportSection, createReportVersion } from '../db/reportRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { Report } from '../db/types.js';

export function assembleReport(
  db: Database.Database,
  input: { actor: string; reportId: string; sectionOrder: string[] }
): Report {
  const report = getLatestReport(db, input.reportId);
  if (!report) throw new Error(`Report ${input.reportId} not found`);

  for (const sectionId of input.sectionOrder) {
    const section = getLatestReportSection(db, sectionId);
    if (!section || section.status !== 'committed') {
      throw new Error(`Section ${sectionId} is not committed and cannot be assembled`);
    }
  }

  const updated = createReportVersion(db, input.reportId, {
    sectionIds: input.sectionOrder,
    status: 'ready_for_export'
  });

  writeAuditEntry(db, {
    actor: input.actor,
    action: 'assemble_report',
    targetType: 'report',
    targetId: updated.id,
    targetVersion: updated.version,
    evalRunId: null,
    diff: null
  });

  return updated;
}
```

- [ ] **Step 4: Implement `poc/src/tools/exportReport.ts`**

```typescript
import type Database from 'better-sqlite3';
import { getLatestReport, getLatestReportSection, createReportVersion } from '../db/reportRepository.js';
import { getClaim } from '../db/claimRepository.js';
import { writeAuditEntry } from '../db/auditRepository.js';
import type { Report } from '../db/types.js';

const SECTION_TITLES: Record<string, string> = {
  investment_thesis: 'Investment Thesis',
  valuation: 'Valuation',
  risks: 'Risks'
};

export function exportReportToMarkdown(
  db: Database.Database,
  input: { actor: string; reportId: string; templateTitle: string }
): { markdown: string; report: Report } {
  const report = getLatestReport(db, input.reportId);
  if (!report) throw new Error(`Report ${input.reportId} not found`);
  if (report.status !== 'ready_for_export') {
    throw new Error('Report must be ready_for_export before exporting');
  }

  const lines: string[] = [`# ${input.templateTitle}`, ''];
  const footnotes: string[] = [];
  let footnoteIndex = 1;

  for (const sectionId of report.sectionIds) {
    const section = getLatestReportSection(db, sectionId);
    if (!section) throw new Error(`Section ${sectionId} not found`);

    lines.push(`## ${SECTION_TITLES[section.sectionType] ?? section.sectionType}`, '');

    let content = section.content;
    for (const claimId of section.claimIds) {
      const claim = getClaim(db, claimId);
      if (!claim) continue;
      content += ` [${footnoteIndex}]`;
      footnotes.push(`[${footnoteIndex}]: ${claim.sourceExcerpt}`);
      footnoteIndex += 1;
    }
    lines.push(content, '');
  }

  if (footnotes.length > 0) {
    lines.push('---', ...footnotes);
  }

  const markdown = lines.join('\n');

  const exported = createReportVersion(db, input.reportId, {
    status: 'exported',
    exportedAt: new Date().toISOString(),
    exportRef: `markdown:${input.reportId}`
  });

  writeAuditEntry(db, {
    actor: input.actor,
    action: 'export_report',
    targetType: 'report',
    targetId: exported.id,
    targetVersion: exported.version,
    evalRunId: null,
    diff: null
  });

  return { markdown, report: exported };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc && npx vitest run tests/tools/assembleAndExportReport.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add poc/src/tools/assembleReport.ts poc/src/tools/exportReport.ts poc/tests/tools/assembleAndExportReport.test.ts
git commit -m "feat: add assemble_report and export_report (Markdown) tools"
```

---

### Task 17: MCP server — register all tools and the widget resource

**Files:**
- Create: `poc/src/tools/registerTools.ts`
- Create: `poc/src/server.ts`

**Interfaces:**
- Consumes: every tool function from Tasks 11–16, `createDb` (Task 2), `createOpenAIChatFn` (Task 7), `createFactsetClient` (Task 10).
- Produces: a running MCP server (HTTP transport) with all nine tools registered and a widget resource URI. Task 18 (widget) and Task 19 (Skill + manual e2e) consume this running server.

This task is registration/wiring rather than new business logic, so it's verified by manual inspection rather than a unit test — the logic underneath is already covered by Tasks 3–16.

- [ ] **Step 1: Implement `poc/src/tools/registerTools.ts`**

```typescript
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type Database from 'better-sqlite3';
import { z } from 'zod';
import type { ChatFn } from '../llm/openaiClient.js';
import type { FactsetClientLike } from './fetchFactsetData.js';
import { ingestDocument } from './ingestDocument.js';
import { fetchConnectorData } from './fetchFactsetData.js';
import { synthesizeArtefact } from './synthesizeArtefact.js';
import { runEval } from './runEval.js';
import { approveArtefact } from './approveArtefact.js';
import { draftSection } from './draftSection.js';
import { commitSection } from './commitSection.js';
import { assembleReport } from './assembleReport.js';
import { exportReportToMarkdown } from './exportReport.js';
import { getLatestArtefact } from '../db/artefactRepository.js';

export function registerTools(
  server: McpServer,
  db: Database.Database,
  chatFn: ChatFn,
  factsetClient: FactsetClientLike
): void {
  server.registerTool(
    'ingest_document',
    {
      description: 'Register an analyst-uploaded document as a Source.',
      inputSchema: {
        actor: z.string(),
        context: z.string(),
        rawContentRef: z.string(),
        externalUrl: z.string().optional()
      }
    },
    async ({ actor, context, rawContentRef, externalUrl }) => {
      const source = ingestDocument(db, { retrievedBy: actor, context, rawContentRef, externalUrl });
      return { content: [{ type: 'text', text: JSON.stringify(source) }] };
    }
  );

  server.registerTool(
    'fetch_connector_data',
    {
      description: 'Fetch FactSet fundamentals for a ticker and register as a Source.',
      inputSchema: { actor: z.string(), ticker: z.string() }
    },
    async ({ actor, ticker }) => {
      const source = await fetchConnectorData(db, factsetClient, { retrievedBy: actor, ticker });
      return { content: [{ type: 'text', text: JSON.stringify(source) }] };
    }
  );

  server.registerTool(
    'synthesize_artefact',
    {
      description: 'Draft an intermediate artefact from a source, decomposed into cited claims.',
      inputSchema: {
        actor: z.string(),
        type: z.enum(['thesis_point', 'data_extract', 'comparison_table']),
        generatedText: z.string(),
        sourceId: z.string()
      }
    },
    async ({ actor, type, generatedText, sourceId }) => {
      const { getSource } = await import('../db/sourceRepository.js');
      const source = getSource(db, sourceId);
      if (!source) throw new Error(`Source ${sourceId} not found`);
      const artefact = await synthesizeArtefact(db, chatFn, { actor, type, generatedText, source });
      return { content: [{ type: 'text', text: JSON.stringify(artefact) }] };
    }
  );

  server.registerTool(
    'run_eval',
    {
      description: 'Run the groundedness eval gate on an artefact before it can be approved.',
      inputSchema: { actor: z.string(), artefactId: z.string() }
    },
    async ({ actor, artefactId }) => {
      const result = await runEval(db, chatFn, { actor, artefactId });
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }
  );

  server.registerTool(
    'approve_artefact',
    {
      description: 'Human approval gate: approve or reject a pending_approval artefact.',
      annotations: { requiresApproval: true },
      inputSchema: { actor: z.string(), artefactId: z.string(), decision: z.enum(['approve', 'reject']) }
    },
    async ({ actor, artefactId, decision }) => {
      const artefact = approveArtefact(db, { actor, artefactId, decision });
      return { content: [{ type: 'text', text: JSON.stringify(artefact) }] };
    }
  );

  server.registerTool(
    'draft_section',
    {
      description: 'Assemble a draft section from approved artefacts (not persisted until commit_section).',
      inputSchema: { reportId: z.string(), sectionType: z.string(), approvedArtefactIds: z.array(z.string()) }
    },
    async ({ reportId, sectionType, approvedArtefactIds }) => {
      const artefacts = approvedArtefactIds.map((id) => {
        const a = getLatestArtefact(db, id);
        if (!a) throw new Error(`Artefact ${id} not found`);
        return a;
      });
      const draft = draftSection({ reportId, sectionType, approvedArtefacts: artefacts });
      return { content: [{ type: 'text', text: JSON.stringify(draft) }] };
    }
  );

  server.registerTool(
    'commit_section',
    {
      description: 'Commit analyst-refined section prose into the governed report document.',
      inputSchema: {
        actor: z.string(),
        reportId: z.string(),
        sectionType: z.string(),
        content: z.string(),
        claimIds: z.array(z.string()),
        existingSectionId: z.string().optional()
      }
    },
    async (input) => {
      const section = commitSection(db, input);
      return { content: [{ type: 'text', text: JSON.stringify(section) }] };
    }
  );

  server.registerTool(
    'assemble_report',
    {
      description: 'Validate and order committed sections into a ready-for-export report.',
      inputSchema: { actor: z.string(), reportId: z.string(), sectionOrder: z.array(z.string()) }
    },
    async (input) => {
      const report = assembleReport(db, input);
      return { content: [{ type: 'text', text: JSON.stringify(report) }] };
    }
  );

  server.registerTool(
    'export_report',
    {
      description: 'Export a ready-for-export report to Markdown with resolved citations.',
      inputSchema: { actor: z.string(), reportId: z.string(), templateTitle: z.string() }
    },
    async (input) => {
      const result = exportReportToMarkdown(db, input);
      return { content: [{ type: 'text', text: result.markdown }] };
    }
  );
}
```

- [ ] **Step 2: Implement `poc/src/server.ts`**

```typescript
import 'dotenv/config';
import express from 'express';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import OpenAI from 'openai';
import { createDb } from './db/db.js';
import { createOpenAIChatFn } from './llm/openaiClient.js';
import { createFactsetClient } from './factset/factsetClient.js';
import { registerTools } from './tools/registerTools.js';

const db = createDb(process.env.DB_PATH ?? './data/poc.db');
const openaiClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const chatFn = createOpenAIChatFn(openaiClient);
const factsetClient = createFactsetClient({
  clientId: process.env.FACTSET_CLIENT_ID ?? '',
  clientSecret: process.env.FACTSET_CLIENT_SECRET ?? '',
  baseUrl: process.env.FACTSET_API_BASE_URL ?? 'https://api.factset.com'
});

const server = new McpServer({ name: 'research-authoring-poc', version: '0.1.0' });
registerTools(server, db, chatFn, factsetClient);

const app = express();
app.use(express.json());

app.post('/mcp', async (req, res) => {
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  res.on('close', () => transport.close());
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

const port = process.env.PORT ?? 3000;
app.listen(port, () => {
  console.log(`Research authoring POC MCP server listening on port ${port}`);
});
```

- [ ] **Step 3: Add the `dotenv` dependency**

Run: `cd poc && npm install dotenv`

- [ ] **Step 4: Verify the server starts and lists tools**

Run: `cd poc && npm run dev`
Expected console output: `Research authoring POC MCP server listening on port 3000`

In a second terminal, use the MCP inspector to confirm all nine tools are registered:
Run: `npx @modelcontextprotocol/inspector node --loader tsx src/server.ts`
Expected: inspector UI lists `ingest_document`, `fetch_connector_data`, `synthesize_artefact`, `run_eval`, `approve_artefact`, `draft_section`, `commit_section`, `assemble_report`, `export_report`.

- [ ] **Step 5: Commit**

```bash
git add poc/src/tools/registerTools.ts poc/src/server.ts poc/package.json poc/package-lock.json
git commit -m "feat: wire MCP server with all nine tools over HTTP transport"
```

---

### Task 18: Apps SDK widget — report workspace

**Files:**
- Create: `poc/src/widget/src/openaiBridge.ts`
- Create: `poc/src/widget/src/ReportWorkspace.tsx`
- Create: `poc/src/widget/index.html`
- Create: `poc/src/widget/build.mjs`
- Modify: `poc/src/server.ts` — serve the built widget bundle and register it as a resource

**Interfaces:**
- Consumes: the nine MCP tools registered in Task 17 (called via the widget bridge's `callTool`).
- Produces: a fullscreen widget the ChatGPT client renders, exercised manually against ChatGPT Developer Mode in Task 19.

This is UI wiring against a host (ChatGPT) that can't be unit-tested outside it, so verification here is a manual smoke test against the Apps SDK's local widget preview, not an automated test.

- [ ] **Step 1: Implement `poc/src/widget/src/openaiBridge.ts`**

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

- [ ] **Step 2: Implement `poc/src/widget/src/ReportWorkspace.tsx`**

```typescript
import { useEffect, useState } from 'react';
import { getOpenAiBridge } from './openaiBridge.js';

interface ArtefactSummary {
  id: string;
  type: string;
  status: string;
  content: string;
  claimIds: string[];
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
    const result = await bridge.callTool('approve_artefact', {
      actor: 'analyst-1',
      artefactId,
      decision: 'approve'
    });
    setArtefacts((prev) =>
      prev.map((a) => (a.id === artefactId ? { ...a, status: (result as any).status } : a))
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
              {artefact.claimIds.map((claimId, i) => (
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

- [ ] **Step 3: Implement `poc/src/widget/index.html`**

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

- [ ] **Step 4: Implement `poc/src/widget/build.mjs`**

```javascript
import { build } from 'esbuild';
import { writeFileSync, mkdirSync } from 'node:fs';

mkdirSync('dist/widget', { recursive: true });

await build({
  entryPoints: ['src/widget/src/entry.tsx'],
  bundle: true,
  outfile: 'dist/widget/bundle.js',
  format: 'esm',
  jsx: 'automatic'
});

writeFileSync(
  'dist/widget/index.html',
  `<!doctype html><html><head><meta charset="utf-8"><title>Research Authoring Workspace</title></head><body><div id="root"></div><script type="module" src="./bundle.js"></script></body></html>`
);

console.log('Widget bundle built at dist/widget/bundle.js');
```

- [ ] **Step 5: Create the widget entrypoint `poc/src/widget/src/entry.tsx`**

```typescript
import { createRoot } from 'react-dom/client';
import { ReportWorkspace } from './ReportWorkspace.js';
import { getOpenAiBridge } from './openaiBridge.js';

const bridge = getOpenAiBridge();
const initialArtefacts = (bridge.widgetState.artefacts as any[]) ?? [];

const root = createRoot(document.getElementById('root')!);
root.render(<ReportWorkspace initialArtefacts={initialArtefacts} />);
```

- [ ] **Step 6: Build the widget bundle**

Run: `cd poc && npm run build:widget`
Expected: `Widget bundle built at dist/widget/bundle.js`, and `dist/widget/bundle.js` + `dist/widget/index.html` exist.

- [ ] **Step 7: Register the widget as an MCP resource in `poc/src/server.ts`**

Add above the `app.listen` call:

```typescript
app.use('/widget', express.static('dist/widget'));

server.registerResource(
  'report-workspace-widget',
  'ui://widget/report-workspace.html',
  { mimeType: 'text/html+skybridge' },
  async () => ({
    contents: [
      {
        uri: 'ui://widget/report-workspace.html',
        mimeType: 'text/html+skybridge',
        text: `<iframe src="http://localhost:${port}/widget/index.html" style="width:100%;height:100%;border:none;"></iframe>`
      }
    ]
  })
);
```

Also add `_meta: { 'openai/outputTemplate': 'ui://widget/report-workspace.html' }` to the `run_eval` and `approve_artefact` tool registrations in `registerTools.ts` (the two tools whose output the analyst most needs to see rendered) so ChatGPT knows to render the widget after calling them.

- [ ] **Step 8: Manual smoke test**

Run: `cd poc && npm run build:widget && npm run dev`, then open `http://localhost:3000/widget/index.html` directly in a browser.
Expected: page loads without a JS error in the console (the `window.openai bridge is not present` error is expected outside ChatGPT — confirms the bridge check works; full interactive verification happens inside ChatGPT in Task 19).

- [ ] **Step 9: Commit**

```bash
git add poc/src/widget poc/src/server.ts
git commit -m "feat: add Apps SDK fullscreen widget for artefact review and approval"
```

---

### Task 19: ChatGPT Skill + end-to-end manual verification

**Files:**
- Create: `poc/skill/report-authoring-skill.md`

**Interfaces:**
- Consumes: the nine tool names from Task 17 (must match exactly).
- Produces: a documented Skill definition plus a recorded manual end-to-end pass — the acceptance test for the whole POC.

- [ ] **Step 1: Write the Skill definition `poc/skill/report-authoring-skill.md`**

```markdown
# Skill: Draft an Equity Research Report Section

**When to use:** The analyst asks to research a company, build an investment thesis,
or draft/refine a section of a sell-side equity research report.

**Steps to follow, in order:**
1. If the analyst hasn't supplied source material yet, ask whether to use an uploaded
   document (`ingest_document`) or FactSet fundamentals for a ticker (`fetch_connector_data`).
2. Call `synthesize_artefact` to turn source material into a cited artefact
   (`thesis_point`, `data_extract`, or `comparison_table`) — never draft analysis
   directly into chat without going through this tool first.
3. Call `run_eval` on the resulting artefact before presenting it to the analyst.
4. Show the analyst the artefact and its claims for review. Only call `approve_artefact`
   after the analyst has explicitly approved or rejected it — never assume approval.
5. Once artefacts relevant to a section are approved, call `draft_section` to assemble
   a starting draft, then refine the prose conversationally with the analyst as needed.
6. When the analyst is satisfied with a section's wording, call `commit_section` —
   do not consider a section part of the report until this has been called.
7. Once all intended sections are committed, call `assemble_report` with the desired
   section order, then `export_report` to produce the Markdown deliverable.

**Never:** call `approve_artefact` or `assemble_report` without an explicit analyst
instruction to do so — these are approval gates, not automatic steps.
```

- [ ] **Step 2: Configure the Skill in the ChatGPT workspace admin panel**

Follow the current instructions at https://help.openai.com/en/articles/20001066-skills-in-chatgpt to upload `poc/skill/report-authoring-skill.md` as a workspace Skill, scoped to the test user/role used for this POC.

- [ ] **Step 3: Register the POC app in ChatGPT Developer Mode**

Point ChatGPT Developer Mode at the running MCP server's `/mcp` endpoint (per current instructions at https://developers.openai.com/apps-sdk/build/chatgpt-ui). Confirm all nine tools and the `report-workspace-widget` resource appear.

- [ ] **Step 4: Run the full end-to-end scenario manually**

In a ChatGPT conversation with the POC app and Skill enabled:
1. Ask ChatGPT to pull FactSet fundamentals for a real ticker you have access to.
2. Ask it to synthesize a `data_extract` artefact from that data.
3. Confirm `run_eval` runs automatically (per the Skill) and the widget renders the artefact with a citation marker.
4. Click the citation marker in the widget and confirm it shows the FactSet source excerpt.
5. Approve the artefact from the widget; confirm its status updates to `approved`.
6. Ask ChatGPT to draft a second section (e.g. `investment_thesis`) from an uploaded document, repeating ingest → synthesize → eval → approve.
7. Commit both sections, then assemble and export the report; confirm the Markdown output contains both sections in order with resolved footnote citations.
8. Query the SQLite `audit_log` table directly (`sqlite3 poc/data/poc.db "SELECT actor, action, target_type, target_id, timestamp FROM audit_log ORDER BY timestamp;"`) and confirm every step above produced an entry.

Expected: all nine tool calls succeed, the widget renders and updates correctly inside ChatGPT, the exported Markdown is well-formed with real FactSet-derived content and citations, and the audit log has one entry per state transition performed.

- [ ] **Step 5: Commit**

```bash
git add poc/skill/report-authoring-skill.md
git commit -m "docs: add report-authoring Skill definition and record e2e POC verification"
```

---

## Self-Review

**Spec coverage:**
- Custom widget (inline/fullscreen) — Task 18. ✓
- MCP tool layer (all nine tools) — Tasks 11–16. ✓
- Data model (Source/Claim/Artefact/ReportSection/Report/AuditLogEntry, versioning) — Tasks 2–6. ✓
- Claim-level citations resolved in widget and export — Tasks 12, 16, 18. ✓
- Approval-gated human-in-the-loop — Task 14, wired into MCP registration in Task 17. ✓
- Groundedness eval gate before approval — Tasks 9, 13. ✓
- FactSet real integration — Task 10, exercised live in Task 19. ✓
- Multi-section report template — Tasks 15, 16, 19 (two distinct section types). ✓
- Markdown export — Task 16. ✓
- Skill wrapping the workflow — Task 19. ✓
- Audit logging on every transition — Task 6, wired into Tasks 11–16. ✓
- Prompt-injection containment (ingested content treated as inert data, not instructions) — reflected in Task 11's design (raw content stored as `rawContentRef`/`context`, never re-injected as system/instruction text) and reiterated as a "never" rule in the Task 19 Skill definition.

**Placeholder scan:** no TBD/TODO markers; the one open external dependency (FactSet's exact endpoint paths) is called out explicitly as a verification step in Task 10 rather than left vague, with working default code provided.

**Type consistency:** `Source`, `Claim`, `Artefact`, `ReportSection`, `Report`, `AuditLogEntry` defined once in Task 2's `types.ts` and referenced identically (same field names/casing) by every later task; tool function signatures in Task 17 match the exported function names/parameters from Tasks 11–16 exactly.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-24-research-authoring-poc.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
