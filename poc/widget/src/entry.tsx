import { createRoot } from 'react-dom/client';
import { ReportWorkspace } from './ReportWorkspace.js';
import { waitForOpenAiBridge } from './openaiBridge.js';

const rootEl = document.getElementById('root')!;
const root = createRoot(rootEl);

// Rendering nothing but a bare <div id="root"> on failure is indistinguishable
// from "still loading" when we have no browser console access to this iframe
// (ChatGPT's own host, not a normal browser tab) -- render failures as visible
// text instead, so a screenshot alone is enough to diagnose what broke.
waitForOpenAiBridge()
  .then(async (bridge) => {
    // Fetch fresh from the server rather than seeding from widgetState --
    // nothing ever populates widgetState.artefacts (confirmed live: widget
    // rendered correctly but reported "0 pending artefacts" every time).
    // run_eval_tool/approve_artefact_tool each only return the single
    // artefact they just acted on, never the full pending set, so the
    // widget calls its own dedicated tool on mount instead.
    // window.openai.callTool() hands back the tool's structuredContent as a
    // real object, not a JSON string -- list_pending_artefacts_tool returns
    // list[dict] directly server-side so this is {result: [...]} already, no
    // JSON.parse needed (confirmed live: JSON.parse on this object produced
    // `"[object Object]" is not valid JSON`, since the object stringifies to
    // that before parsing).
    const result = (await bridge.callTool('list_pending_artefacts_tool', {})) as { result: unknown };
    root.render(<ReportWorkspace initialArtefacts={(result.result as any[]) ?? []} />);
  })
  .catch((err: Error) => {
    rootEl.textContent = `Widget failed to initialize: ${err.message}`;
  });
