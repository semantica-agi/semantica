/**
 * src/workspaces/VocabularyWorkspace/Sidebar.tsx
 *
 * Left sidebar for the Vocabulary workspace.
 * - Lists available SKOS ConceptSchemes
 * - Shows the concept hierarchy tree for the active scheme
 * - Includes the import dropzone
 */
import { useState } from 'react';
import { useVocabularies, useConceptHierarchy } from './queries';
import { ConceptTree } from './ConceptTree';
import { ImportDropzone } from './ImportDropzone';
import type { ConceptNode, VocabularyScheme } from './types';

interface SidebarProps {
  onSelectConcept: (concept: ConceptNode) => void;
}

export function Sidebar({ onSelectConcept }: SidebarProps) {
  const { data: schemes = [], isLoading: schemesLoading } = useVocabularies();
  const [activeScheme, setActiveScheme] = useState<string | undefined>();

  // Auto-select first scheme
  const selectedSchemeUri = activeScheme ?? schemes[0]?.uri;

  const {
    data: hierarchy = [],
    isLoading: treeLoading,
  } = useConceptHierarchy(selectedSchemeUri);

  return (
    <div style={{
      width: 340, display: 'flex', flexDirection: 'column',
      borderRight: '1px solid rgba(88,166,255,0.15)',
      backgroundColor: '#010409', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '20px 20px 16px',
        borderBottom: '1px solid rgba(88,166,255,0.15)',
      }}>
        <h2 style={{ fontSize: 18, color: '#c9d1d9', margin: '0 0 4px 0', fontWeight: 600 }}>
          Ontology & Vocabulary
        </h2>
        <p style={{ color: '#8b949e', fontSize: 13, margin: 0 }}>
          {schemes.length
            ? `${schemes.length} vocabulary scheme${schemes.length > 1 ? 's' : ''}`
            : 'No vocabularies loaded'}
        </p>
      </div>

      {/* Scheme selector */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(88,166,255,0.1)' }}>
        {schemesLoading ? (
          <div style={{ color: '#8b949e', fontSize: 13 }}>Loading schemes…</div>
        ) : schemes.length === 0 ? (
          <div style={{ color: '#484f58', fontSize: 13, fontStyle: 'italic' }}>
            No schemes found. Import a .ttl or .rdf file below.
          </div>
        ) : (
          <select
            value={selectedSchemeUri || ''}
            onChange={(e) => setActiveScheme(e.target.value)}
            style={{
              width: '100%', appearance: 'none',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(88,166,255,0.2)',
              color: '#c9d1d9', padding: '8px 12px',
              borderRadius: 6, fontSize: 13, cursor: 'pointer',
              outline: 'none',
            }}
          >
            {schemes.map((s: VocabularyScheme) => (
              <option key={s.uri} value={s.uri} style={{ background: '#0d1117' }}>
                {s.label}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Concept Tree */}
      <div style={{
        flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column',
      }}>
        {treeLoading ? (
          <div style={{ padding: 20, color: '#8b949e', fontSize: 13, textAlign: 'center' }}>
            Loading hierarchy…
          </div>
        ) : hierarchy.length === 0 ? (
          <div style={{ padding: 20, color: '#484f58', fontSize: 13, textAlign: 'center', fontStyle: 'italic' }}>
            {selectedSchemeUri
              ? 'No concepts found in this scheme.'
              : 'Select a scheme to browse concepts.'}
          </div>
        ) : (
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <ConceptTree data={hierarchy} onSelectConcept={onSelectConcept} />
          </div>
        )}
      </div>

      {/* Import area */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid rgba(88,166,255,0.15)',
      }}>
        <ImportDropzone />
      </div>
    </div>
  );
}
