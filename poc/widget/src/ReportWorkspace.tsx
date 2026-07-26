import { useEffect, useRef, useState } from 'react';
import { getOpenAiBridge } from './openaiBridge.js';

interface ArtefactSummary {
  id: string;
  type: string;
  status: string;
  content: string;
  claim_ids: string[];
}

const TYPE_LABELS: Record<string, string> = {
  thesis_point: 'Thesis Point',
  data_extract: 'Data Extract',
  comparison_table: 'Comparison Table',
};

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
    // window.openai.callTool() hands back structuredContent as a real
    // object, not a JSON string -- approve_artefact_tool's structuredContent
    // is {artefact: {...}} (see _widget_result in register_tools.py), so no
    // JSON.parse here (same class of bug as entry.tsx's list fetch: calling
    // JSON.parse on an already-parsed object fails).
    const result = (await bridge.callTool('approve_artefact_tool', {
      actor: 'analyst-1',
      artefact_id: artefactId,
      decision: 'approve'
    })) as { artefact: { status: string } };
    setArtefacts((prev) =>
      prev.map((a) => (a.id === artefactId ? { ...a, status: result.artefact.status } : a))
    );
  }

  const pending = artefacts.filter((a) => a.status === 'pending_approval');

  return (
    <div ref={containerRef}>
      <div className="workspace-header">
        <h2>Pending Artefacts</h2>
        <span className="count-badge">{pending.length}</span>
      </div>

      {pending.length === 0 ? (
        <div className="empty-state">No artefacts are waiting for review right now.</div>
      ) : (
        <ul className="artefact-list">
          {pending.map((artefact) => (
            <li key={artefact.id} className="artefact-card">
              <span className="artefact-type-badge">
                {TYPE_LABELS[artefact.type] ?? artefact.type}
              </span>
              <p className="artefact-content">{artefact.content}</p>
              <div className="artefact-actions">
                {artefact.claim_ids.map((claimId, i) => (
                  <button
                    key={claimId}
                    className={`citation-chip${selectedClaimId === claimId ? ' is-selected' : ''}`}
                    onClick={() => setSelectedClaimId(claimId)}
                  >
                    {i + 1}
                  </button>
                ))}
                <button className="approve-button" onClick={() => approve(artefact.id)}>
                  Approve
                </button>
              </div>
              {selectedClaimId && artefact.claim_ids.includes(selectedClaimId) && (
                <div className="citation-panel" data-testid="citation-panel">
                  Citation: {selectedClaimId}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
