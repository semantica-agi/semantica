/**
 * src/workspaces/VocabularyWorkspace/VocabularyWorkspace.tsx
 *
 * Main Vocabulary workspace — composes the Sidebar (scheme list + tree + import)
 * and the PropertyPanel (concept details) into a responsive two-column layout.
 *
 * All data fetching is handled by TanStack Query hooks in `queries.ts`.
 */
import { useState } from 'react';
import { Sidebar } from './Sidebar';
import { PropertyPanel } from './PropertyPanel';
import type { ConceptNode } from './types';

const THEME_CSS = `
  .vocab-workspace {
    display: flex;
    width: 100%;
    height: 100%;
    background: #0d1117;
    overflow: hidden;
  }
  .vocab-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
  }
  .vocab-main-content {
    flex: 1;
    overflow-y: auto;
  }
  .vocab-detail-glass {
    background: linear-gradient(135deg, rgba(13,17,23,0.75), rgba(22,27,34,0.6));
    backdrop-filter: blur(16px) saturate(1.2);
    -webkit-backdrop-filter: blur(16px) saturate(1.2);
    border: 1px solid rgba(88,166,255,0.15);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5), inset 1px 1px 0 rgba(255,255,255,0.04);
    border-radius: 14px;
    height: 100%;
  }
`;

export function VocabularyWorkspace() {
  const [selectedConcept, setSelectedConcept] = useState<ConceptNode | null>(null);

  return (
    <div className="vocab-workspace">
      <style>{THEME_CSS}</style>

      {/* Left: Sidebar with scheme list + concept tree + import */}
      <Sidebar onSelectConcept={setSelectedConcept} />

      {/* Right: Concept detail panel */}
      <div className="vocab-main">
        {/* Decorative background gradient */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(ellipse at top right, rgba(210,168,255,0.04), transparent 60%)',
        }} />

        <div className="vocab-main-content" style={{ padding: 32 }}>
          <div className="vocab-detail-glass">
            <PropertyPanel concept={selectedConcept} />
          </div>
        </div>
      </div>
    </div>
  );
}