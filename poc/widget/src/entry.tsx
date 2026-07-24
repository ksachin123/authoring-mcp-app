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
  .then((bridge) => {
    // POC shortcut: per design, content should be fetched fresh from the
    // server, not seeded from widgetState.
    const initialArtefacts = (bridge.widgetState?.artefacts as any[]) ?? [];
    root.render(<ReportWorkspace initialArtefacts={initialArtefacts} />);
  })
  .catch((err: Error) => {
    rootEl.textContent = `Widget failed to initialize: ${err.message}`;
  });
