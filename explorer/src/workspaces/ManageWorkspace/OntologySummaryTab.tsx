/**
 * src/workspaces/ManageWorkspace/OntologySummaryTab.tsx
 *
 * A compact read-only view of all loaded SKOS ConceptSchemes and their
 * top-level concepts. Clicking a concept deep-links to the Vocabulary Browser.
 */
import { useState } from "react";
import { BookOpen, ChevronRight, ChevronDown, ExternalLink } from "lucide-react";
import { useVocabularies, useConceptHierarchy } from "../VocabularyWorkspace/queries";
import type { ConceptNode, VocabularyScheme } from "../VocabularyWorkspace/types";

function countConcepts(nodes: ConceptNode[]): number {
  return nodes.reduce((acc, node) => {
    return acc + 1 + countConcepts(node.children ?? []);
  }, 0);
}

function ConceptRow({
  concept,
  depth,
  onSelect,
}: {
  concept: ConceptNode;
  depth: number;
  onSelect: (concept: ConceptNode) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const children = concept.children ?? [];
  const hasChildren = children.length > 0;

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          paddingLeft: 12 + depth * 16,
          paddingRight: 12,
          paddingTop: 5,
          paddingBottom: 5,
          borderRadius: 6,
          cursor: "pointer",
          color: depth === 0 ? "#c6d4e3" : "#8b949e",
          fontSize: depth === 0 ? 13 : 12,
          transition: "background 120ms ease",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = "rgba(74,163,255,0.07)"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
      >
        {hasChildren ? (
          <button
            onClick={() => setExpanded((v) => !v)}
            style={{ background: "transparent", border: "none", color: "#8b949e", cursor: "pointer", padding: 0, display: "flex", alignItems: "center" }}
          >
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
        ) : (
          <span style={{ width: 12, display: "inline-block" }} />
        )}
        <span
          onClick={() => onSelect(concept)}
          style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        >
          {concept.pref_label || concept.uri}
        </span>
        {children.length > 0 ? (
          <span style={{ color: "#6a7f97", fontSize: 10 }}>{children.length}</span>
        ) : null}
      </div>
      {expanded && hasChildren
        ? children.map((child) => (
            <ConceptRow key={child.uri} concept={child} depth={depth + 1} onSelect={onSelect} />
          ))
        : null}
    </>
  );
}

function SchemePanel({
  scheme,
  onSelectConcept,
}: {
  scheme: VocabularyScheme;
  onSelectConcept: (concept: ConceptNode) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const { data: hierarchy = [], isLoading } = useConceptHierarchy(scheme.uri);
  const totalConcepts = countConcepts(hierarchy);

  return (
    <div style={schemeCardStyle}>
      {/* Scheme header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        style={schemeHeaderStyle}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {expanded ? <ChevronDown size={14} color="#8b949e" /> : <ChevronRight size={14} color="#8b949e" />}
          <span style={{ color: "#e6edf3", fontSize: 14, fontWeight: 700 }}>{scheme.label}</span>
        </div>
        <span style={{ color: "#6a7f97", fontSize: 11 }}>
          {isLoading ? "…" : `${totalConcepts} concept${totalConcepts !== 1 ? "s" : ""}`}
        </span>
      </button>

      {/* Concept tree */}
      {expanded ? (
        <div style={{ paddingTop: 4, paddingBottom: 8 }}>
          {isLoading ? (
            <div style={{ padding: "8px 24px", color: "#6a7f97", fontSize: 12 }}>Loading concepts…</div>
          ) : hierarchy.length === 0 ? (
            <div style={{ padding: "8px 24px", color: "#6a7f97", fontSize: 12, fontStyle: "italic" }}>
              No concepts found in this scheme.
            </div>
          ) : (
            hierarchy.map((concept) => (
              <ConceptRow key={concept.uri} concept={concept} depth={0} onSelect={onSelectConcept} />
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

export function OntologySummaryTab({
  onOpenVocabularyBrowser,
}: {
  onOpenVocabularyBrowser?: () => void;
}) {
  const { data: schemes = [], isLoading } = useVocabularies();
  const [selectedConcept, setSelectedConcept] = useState<ConceptNode | null>(null);

  return (
    <div style={shellStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <BookOpen size={18} color="#d2a8ff" />
          <div>
            <div style={{ color: "#ebf3ff", fontSize: 16, fontWeight: 700 }}>Ontology Summary</div>
            <div style={{ color: "#8b949e", fontSize: 12 }}>
              {isLoading
                ? "Loading schemes…"
                : `${schemes.length} vocabulary scheme${schemes.length !== 1 ? "s" : ""} loaded`}
            </div>
          </div>
        </div>
        {onOpenVocabularyBrowser ? (
          <button onClick={onOpenVocabularyBrowser} style={openBrowserBtnStyle}>
            <ExternalLink size={12} />
            <span>Open Full Browser</span>
          </button>
        ) : null}
      </div>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Scheme tree column */}
        <div style={treeColumnStyle}>
          {isLoading ? (
            <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 10 }}>
              {[90, 75, 60].map((w, i) => (
                <div key={i} style={{ height: 36, borderRadius: 8, background: "rgba(255,255,255,0.04)", width: `${w}%` }} />
              ))}
            </div>
          ) : schemes.length === 0 ? (
            <div style={emptyStateStyle}>
              <BookOpen size={32} color="rgba(210,168,255,0.15)" />
              <div style={{ color: "#8b949e", fontSize: 13, marginTop: 12 }}>No vocabulary schemes loaded</div>
              <div style={{ color: "#6a7f97", fontSize: 12, marginTop: 4, textAlign: "center", maxWidth: 240 }}>
                Import a .ttl or .rdf file via the Vocabulary Browser to see your ontology here.
              </div>
            </div>
          ) : (
            <div style={{ padding: "12px 8px", display: "flex", flexDirection: "column", gap: 8 }}>
              {schemes.map((scheme) => (
                <SchemePanel key={scheme.uri} scheme={scheme} onSelectConcept={setSelectedConcept} />
              ))}
            </div>
          )}
        </div>

        {/* Concept detail panel */}
        {selectedConcept ? (
          <div style={detailPanelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div style={{ color: "#d2a8ff", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                Concept Detail
              </div>
              <button onClick={() => setSelectedConcept(null)} style={{ background: "transparent", border: "none", color: "#8b949e", cursor: "pointer", fontSize: 16 }}>×</button>
            </div>

            <h3 style={{ color: "#ffffff", fontSize: 18, fontWeight: 800, letterSpacing: "-0.03em", margin: "0 0 6px 0" }}>
              {selectedConcept.pref_label}
            </h3>
            {selectedConcept.notation ? (
              <div style={{ color: "#8b949e", fontSize: 12, marginBottom: 8 }}>Notation: {selectedConcept.notation}</div>
            ) : null}
            <div style={{ color: "#6a7f97", fontSize: 11, fontFamily: "monospace", wordBreak: "break-all", marginBottom: 14 }}>
              {selectedConcept.uri}
            </div>

            {selectedConcept.description ? (
              <div style={detailSectionStyle}>
                <div style={detailLabelStyle}>Description</div>
                <div style={{ color: "#c6d4e3", fontSize: 13, lineHeight: 1.6 }}>{selectedConcept.description}</div>
              </div>
            ) : null}

            {selectedConcept.alt_labels?.length ? (
              <div style={detailSectionStyle}>
                <div style={detailLabelStyle}>Alternative Labels</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {selectedConcept.alt_labels.map((label) => (
                    <span key={label} style={altLabelChipStyle}>{label}</span>
                  ))}
                </div>
              </div>
            ) : null}

            {(selectedConcept.children?.length ?? 0) > 0 ? (
              <div style={detailSectionStyle}>
                <div style={detailLabelStyle}>Narrower Concepts ({selectedConcept.children!.length})</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {selectedConcept.children!.slice(0, 8).map((child) => (
                    <div
                      key={child.uri}
                      onClick={() => setSelectedConcept(child)}
                      style={{ color: "#79c0ff", fontSize: 12, cursor: "pointer", padding: "3px 0" }}
                    >
                      → {child.pref_label}
                    </div>
                  ))}
                  {selectedConcept.children!.length > 8 ? (
                    <div style={{ color: "#6a7f97", fontSize: 11 }}>+{selectedConcept.children!.length - 8} more</div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* ─── styles ─────────────────────────────────────────────────────── */

const shellStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  width: "100%",
  height: "100%",
  background: "#0d1117",
  overflow: "hidden",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "20px 24px 16px",
  borderBottom: "1px solid rgba(88,166,255,0.1)",
  flexShrink: 0,
};

const openBrowserBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "6px 12px",
  borderRadius: 8,
  border: "1px solid rgba(210,168,255,0.22)",
  background: "rgba(210,168,255,0.08)",
  color: "#d2a8ff",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
};

const treeColumnStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  borderRight: "1px solid rgba(255,255,255,0.06)",
};

const schemeCardStyle: React.CSSProperties = {
  borderRadius: 10,
  border: "1px solid rgba(210,168,255,0.1)",
  background: "rgba(255,255,255,0.02)",
  overflow: "hidden",
};

const schemeHeaderStyle: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 14px",
  background: "transparent",
  border: "none",
  cursor: "pointer",
  borderBottom: "1px solid rgba(255,255,255,0.05)",
};

const detailPanelStyle: React.CSSProperties = {
  width: 300,
  padding: "20px",
  overflowY: "auto",
  borderLeft: "1px solid rgba(255,255,255,0.06)",
  flexShrink: 0,
};

const detailSectionStyle: React.CSSProperties = {
  marginTop: 14,
  paddingTop: 12,
  borderTop: "1px solid rgba(255,255,255,0.06)",
};

const detailLabelStyle: React.CSSProperties = {
  color: "#8b949e",
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.07em",
  marginBottom: 6,
};

const altLabelChipStyle: React.CSSProperties = {
  padding: "3px 8px",
  borderRadius: 999,
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.08)",
  color: "#8fa8c6",
  fontSize: 11,
};

const emptyStateStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: 40,
  height: "100%",
};
