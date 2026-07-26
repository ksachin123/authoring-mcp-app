import { useEffect, useRef, useState } from 'react';
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
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const bridge = getOpenAiBridge();
    bridge.setWidgetState({ ...bridge.widgetState, screen: 'report_workspace' });
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Without this, the host apparently guesses the iframe's height instead
    // of using the widget's actual content size, producing overlapping/
    // clipped rendering (confirmed live).
    const report = () => {
      const bridge = getOpenAiBridge();
      bridge.notifyIntrinsicHeight?.(el.scrollHeight);
      bridge.notifyIntrinsicWidth?.(el.scrollWidth);
    };

    report();
    const observer = new ResizeObserver(report);
    observer.observe(el);
    return () => observer.disconnect();
  }, [artefacts, selectedClaimId]);

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
    <div ref={containerRef}>
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
