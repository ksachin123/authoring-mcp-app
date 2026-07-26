import { createRoot } from 'react-dom/client';
import { ReportWorkspace } from './ReportWorkspace.js';
import { waitForOpenAiBridge } from './openaiBridge.js';

const rootEl = document.getElementById('root')!;
const root = createRoot(rootEl);

function showDiagnostic(text: string) {
  rootEl.textContent = text;
}

// There's no browser console access to this iframe (ChatGPT's own host, not
// a normal browser tab). A prior version relied solely on the promise chain
// below to catch failures, but a live run showed list_pending_artefacts_tool
// succeeding (confirmed in server logs) followed by a blank widget with NO
// error text at all -- meaning something failed silently outside that
// chain (e.g. during React's render, or in an effect after mount). Catch
// everything globally and make it visible in the DOM, since a screenshot is
// the only diagnostic tool available here.
window.addEventListener('error', (e) => {
  showDiagnostic(`Uncaught error: ${e.message}`);
});
window.addEventListener('unhandledrejection', (e) => {
  showDiagnostic(`Unhandled rejection: ${String((e as PromiseRejectionEvent).reason)}`);
});

waitForOpenAiBridge()
  .then(async (bridge) => {
    showDiagnostic('Bridge ready. Fetching pending artefacts...');

    // Fetch fresh from the server rather than seeding from widgetState --
    // nothing ever populates widgetState.artefacts (confirmed live: widget
    // rendered correctly but reported "0 pending artefacts" every time).
    // run_eval_tool/approve_artefact_tool each only return the single
    // artefact they just acted on, never the full pending set, so the
    // widget calls its own dedicated tool on mount instead.
    const result = await bridge.callTool('list_pending_artefacts_tool', {});

    // Diagnostic dump of the raw shape, shown only until render succeeds --
    // window.openai.callTool() hands back the tool's structuredContent as a
    // real object, not a JSON string. list_pending_artefacts_tool returns
    // list[dict] directly server-side, so this is expected to be
    // {result: [...]} already (confirmed via a direct local call), but if
    // that assumption is wrong, this text says exactly what came back
    // instead of the page going silently blank.
    showDiagnostic(`Got callTool result: ${JSON.stringify(result).slice(0, 800)}`);

    const initialArtefacts = (result as { result?: unknown[] })?.result ?? [];
    root.render(<ReportWorkspace initialArtefacts={initialArtefacts as any[]} />);
  })
  .catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    showDiagnostic(`Widget failed to initialize: ${message}`);
  });
