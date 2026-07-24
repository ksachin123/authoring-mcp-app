import { createRoot } from 'react-dom/client';
import { ReportWorkspace } from './ReportWorkspace.js';
import { getOpenAiBridge } from './openaiBridge.js';

const bridge = getOpenAiBridge();
const initialArtefacts = (bridge.widgetState.artefacts as any[]) ?? [];

const root = createRoot(document.getElementById('root')!);
root.render(<ReportWorkspace initialArtefacts={initialArtefacts} />);
