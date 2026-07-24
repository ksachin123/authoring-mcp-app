import { createRoot } from 'react-dom/client';
import { ReportWorkspace } from './ReportWorkspace.js';
import { getOpenAiBridge } from './openaiBridge.js';

const bridge = getOpenAiBridge();
// POC shortcut: per design, content should be fetched fresh from the server,
// not seeded from widgetState.
const initialArtefacts = (bridge.widgetState.artefacts as any[]) ?? [];

const root = createRoot(document.getElementById('root')!);
root.render(<ReportWorkspace initialArtefacts={initialArtefacts} />);
