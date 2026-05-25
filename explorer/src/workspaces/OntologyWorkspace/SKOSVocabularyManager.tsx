import { useEffect, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Loader2,
  Search,
  X,
} from "lucide-react";

interface SKOSScheme {
  uri: string;
  title: string;
  description?: string;
  concept_count: number;
}

interface ConceptNode {
  uri: string;
  pref_label: string;
  alt_labels?: string[];
  description?: string;
  notation?: string;
  scheme_uri?: string;
  parent_uri?: string;
  children?: ConceptNode[];
}

interface SKOSConceptDetail {
  uri: string;
  pref_label: string;
  alt_labels: string[];
  hidden_labels: string[];
  definition?: string;
  scope_note?: string;
  editorial_note?: string;
  broader: string[];
  narrower: string[];
  related: string[];
  exact_match: string[];
  close_match: string[];
  broad_match: string[];
  narrow_match: string[];
  scheme_uri?: string;
}

function countConcepts(nodes: ConceptNode[]): number {
  return nodes.reduce((acc, n) => acc + 1 + countConcepts(n.children ?? []), 0);
}

function LabelChip({ label }: { label: string }) {
  return (
    <span style={chipStyle}>{label}</span>
  );
}

function UriLink({ uri }: { uri: string }) {
  const short = uri.includes("#") ? uri.split("#").pop() : uri.split("/").pop();
  return (
    <span title={uri} style={{ color: "#58a6ff", fontSize: 11, fontFamily: "monospace", cursor: "help" }}>
      {short || uri}
    </span>
  );
}

function ConceptDetailPanel({
  uri,
  onClose,
  onNavigate,
}: {
  uri: string;
  onClose: () => void;
  onNavigate: (uri: string) => void;
}) {
  const [detail, setDetail] = useState<SKOSConceptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetch(`/api/ontology/skos/concept/${encodeURIComponent(uri)}`)
      .then((r) => {
        if (!r.ok) throw new Error("Concept not found");
        return r.json();
      })
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [uri]);

  const renderUriList = (label: string, uris: string[]) => {
    if (!uris.length) return null;
    return (
      <PropSection label={label}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {uris.map((u) => (
            <button
              key={u}
              onClick={() => onNavigate(u)}
              style={navLinkStyle}
            >
              <ChevronRight size={10} />
              <UriLink uri={u} />
            </button>
          ))}
        </div>
      </PropSection>
    );
  };

  return (
    <div style={detailPanelStyle}>
      <div style={detailHeaderStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <BookOpen size={13} color="#9ee8d7" />
          <span style={{ color: "#ebf3ff", fontSize: 13, fontWeight: 700 }}>Concept Detail</span>
        </div>
        <button onClick={onClose} style={iconBtnStyle}>
          <X size={14} />
        </button>
      </div>

      {loading && (
        <div style={centerStyle}>
          <Loader2 size={18} color="#4aa3ff" style={{ animation: "spin 1s linear infinite" }} />
        </div>
      )}

      {error && (
        <div style={centerStyle}>
          <AlertCircle size={16} color="#ff9daf" />
          <span style={{ color: "#ff9daf", fontSize: 12, marginTop: 6 }}>{error}</span>
        </div>
      )}

      {detail && !loading && (
        <div style={detailBodyStyle}>
          <div style={{ marginBottom: 14 }}>
            <h3 style={{ margin: "0 0 4px", color: "#ebf3ff", fontSize: 17, fontWeight: 800, letterSpacing: "-0.03em" }}>
              {detail.pref_label}
            </h3>
            {detail.alt_labels.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
                {detail.alt_labels.map((l) => <LabelChip key={l} label={l} />)}
              </div>
            )}
            {detail.hidden_labels.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
                {detail.hidden_labels.map((l) => (
                  <span key={l} style={{ ...chipStyle, opacity: 0.5, fontStyle: "italic" }}>{l}</span>
                ))}
              </div>
            )}
            <div style={{ color: "#5a7a9a", fontSize: 10, fontFamily: "monospace", wordBreak: "break-all" }}>
              {uri}
            </div>
          </div>

          {detail.definition && (
            <PropSection label="Definition">
              <p style={{ margin: 0, color: "#c6d4e3", fontSize: 13, lineHeight: 1.6 }}>
                {detail.definition}
              </p>
            </PropSection>
          )}

          {detail.scope_note && (
            <PropSection label="Scope Note">
              <p style={{ margin: 0, color: "#8fa8c6", fontSize: 12, lineHeight: 1.5 }}>
                {detail.scope_note}
              </p>
            </PropSection>
          )}

          {detail.editorial_note && (
            <PropSection label="Editorial Note">
              <p style={{ margin: 0, color: "#8fa8c6", fontSize: 12, lineHeight: 1.5 }}>
                {detail.editorial_note}
              </p>
            </PropSection>
          )}

          {renderUriList("Broader", detail.broader)}
          {renderUriList("Narrower", detail.narrower)}
          {renderUriList("Related", detail.related)}
          {renderUriList("Exact Match", detail.exact_match)}
          {renderUriList("Close Match", detail.close_match)}
          {renderUriList("Broad Match", detail.broad_match)}
          {renderUriList("Narrow Match", detail.narrow_match)}

          {detail.scheme_uri && (
            <PropSection label="Concept Scheme">
              <span style={{ color: "#c6d4e3", fontSize: 11, fontFamily: "monospace", wordBreak: "break-all" }}>
                {detail.scheme_uri}
              </span>
            </PropSection>
          )}
        </div>
      )}
    </div>
  );
}

function PropSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.05)", marginTop: 10 }}>
      <div style={{ color: "#6a7f97", fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", marginBottom: 5 }}>
        {label}
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Concept tree node
// ---------------------------------------------------------------------------

function ConceptTreeNode({
  concept,
  depth,
  selectedUri,
  onSelect,
}: {
  concept: ConceptNode;
  depth: number;
  selectedUri: string | null;
  onSelect: (uri: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth === 0);
  const children = concept.children ?? [];
  const hasChildren = children.length > 0;
  const isSelected = selectedUri === concept.uri;

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          paddingLeft: 10 + depth * 14,
          paddingRight: 10,
          paddingTop: 5,
          paddingBottom: 5,
          borderRadius: 7,
          cursor: "pointer",
          background: isSelected ? "rgba(74,163,255,0.12)" : "transparent",
          transition: "120ms ease",
        }}
        onMouseEnter={(e) => {
          if (!isSelected)
            (e.currentTarget as HTMLDivElement).style.background = "rgba(74,163,255,0.06)";
        }}
        onMouseLeave={(e) => {
          if (!isSelected)
            (e.currentTarget as HTMLDivElement).style.background = "transparent";
        }}
      >
        {hasChildren ? (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
            style={expandBtnStyle}
          >
            {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
        ) : (
          <span style={{ width: 18, display: "inline-block", flexShrink: 0 }} />
        )}

        <span
          onClick={() => onSelect(concept.uri)}
          style={{
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            color: isSelected ? "#ebf3ff" : depth === 0 ? "#c6d4e3" : "#8fa8c6",
            fontSize: depth === 0 ? 13 : 12,
            fontWeight: depth === 0 ? 600 : 400,
          }}
        >
          {concept.pref_label || concept.uri}
        </span>

        {hasChildren && (
          <span style={{ color: "#5a7a9a", fontSize: 10, flexShrink: 0 }}>
            {children.length}
          </span>
        )}
      </div>

      {expanded && hasChildren && children.map((child) => (
        <ConceptTreeNode
          key={child.uri}
          concept={child}
          depth={depth + 1}
          selectedUri={selectedUri}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Scheme panel
// ---------------------------------------------------------------------------

function SchemePanel({
  scheme,
  selectedUri,
  onSelectConcept,
  searchQuery,
}: {
  scheme: SKOSScheme;
  selectedUri: string | null;
  onSelectConcept: (uri: string) => void;
  searchQuery: string;
}) {
  const [expanded, setExpanded] = useState(true);
  const [hierarchy, setHierarchy] = useState<ConceptNode[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    setLoading(true);
    fetch(`/api/vocabulary/hierarchy?scheme=${encodeURIComponent(scheme.uri)}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setHierarchy)
      .catch(() => setHierarchy([]))
      .finally(() => setLoading(false));
  }, [scheme.uri, expanded]);

  const totalConcepts = countConcepts(hierarchy);

  const filterConcepts = (nodes: ConceptNode[], q: string): ConceptNode[] => {
    if (!q) return nodes;
    return nodes.flatMap((n) => {
      const match = (n.pref_label + " " + (n.alt_labels?.join(" ") ?? "") + " " + (n.description ?? ""))
        .toLowerCase()
        .includes(q.toLowerCase());
      const filteredChildren = filterConcepts(n.children ?? [], q);
      if (match || filteredChildren.length > 0) {
        return [{ ...n, children: filteredChildren }];
      }
      return [];
    });
  };

  const displayedConcepts = filterConcepts(hierarchy, searchQuery);

  return (
    <div style={schemePanelStyle}>
      <button onClick={() => setExpanded((v) => !v)} style={schemeHeaderBtnStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {expanded ? <ChevronDown size={13} color="#8fa8c6" /> : <ChevronRight size={13} color="#8fa8c6" />}
          <span style={{ color: "#e6edf3", fontSize: 14, fontWeight: 700 }}>{scheme.title}</span>
        </div>
        <span style={{ color: "#6a7f97", fontSize: 11 }}>
          {loading ? "…" : `${totalConcepts} concept${totalConcepts !== 1 ? "s" : ""}`}
        </span>
      </button>

      {expanded && (
        <div style={{ paddingBottom: 8 }}>
          {loading ? (
            <div style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: 8 }}>
              <Loader2 size={12} color="#4aa3ff" style={{ animation: "spin 0.8s linear infinite" }} />
              <span style={{ color: "#6a7f97", fontSize: 12 }}>Loading concepts…</span>
            </div>
          ) : displayedConcepts.length === 0 ? (
            <div style={{ padding: "8px 24px", color: "#6a7f97", fontSize: 12, fontStyle: "italic" }}>
              {searchQuery ? "No matching concepts" : "No concepts in this scheme"}
            </div>
          ) : (
            <div style={{ paddingTop: 2 }}>
              {displayedConcepts.map((concept) => (
                <ConceptTreeNode
                  key={concept.uri}
                  concept={concept}
                  depth={0}
                  selectedUri={selectedUri}
                  onSelect={onSelectConcept}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main SKOSVocabularyManager
// ---------------------------------------------------------------------------

interface Props {
  schemeUri?: string;
}

export function SKOSVocabularyManager({ schemeUri }: Props) {
  const [schemes, setSchemes] = useState<SKOSScheme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [selectedUri, setSelectedUri] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch("/api/ontology/skos/schemes")
      .then((r) => (r.ok ? r.json() : []))
      .then(setSchemes)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const displayedSchemes = schemeUri
    ? schemes.filter((s) => s.uri === schemeUri)
    : schemes;

  return (
    <div style={managerShellStyle}>
      {/* Search bar */}
      <div style={skosToolbarStyle}>
        <div style={skosSearchBarStyle}>
          <Search size={13} color="#6a7f97" />
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search labels and definitions…"
            style={skosSearchInputStyle}
          />
          {searchQ && (
            <button onClick={() => setSearchQ("")} style={iconBtnStyle}>
              <X size={11} />
            </button>
          )}
        </div>
      </div>

      <div style={skosBodyStyle}>
        {/* Scheme tree column */}
        <div style={treeColStyle}>
          {loading && (
            <div style={centerStyle}>
              <Loader2 size={18} color="#4aa3ff" style={{ animation: "spin 1s linear infinite" }} />
            </div>
          )}

          {error && (
            <div style={centerStyle}>
              <AlertCircle size={16} color="#ff9daf" />
              <span style={{ color: "#ff9daf", fontSize: 12, marginTop: 6 }}>{error}</span>
            </div>
          )}

          {!loading && !error && displayedSchemes.length === 0 && (
            <div style={{ ...centerStyle, textAlign: "center", padding: 28 }}>
              <BookOpen size={28} color="rgba(158,232,215,0.15)" />
              <span style={{ color: "#8fa8c6", fontSize: 12, marginTop: 10 }}>
                No SKOS concept schemes found
              </span>
              <span style={{ color: "#6a7f97", fontSize: 11, marginTop: 4, maxWidth: 220 }}>
                Import a SKOS vocabulary to browse concepts here
              </span>
            </div>
          )}

          {!loading && displayedSchemes.map((scheme) => (
            <SchemePanel
              key={scheme.uri}
              scheme={scheme}
              selectedUri={selectedUri}
              onSelectConcept={setSelectedUri}
              searchQuery={searchQ}
            />
          ))}
        </div>

        {/* Concept detail panel */}
        {selectedUri && (
          <ConceptDetailPanel
            uri={selectedUri}
            onClose={() => setSelectedUri(null)}
            onNavigate={setSelectedUri}
          />
        )}
      </div>
    </div>
  );
}

/* ─── styles ─────────────────────────────────────────────────────────── */

const managerShellStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100%",
  overflow: "hidden",
};

const skosToolbarStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderBottom: "1px solid rgba(127,208,255,0.08)",
  flexShrink: 0,
};

const skosSearchBarStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 7,
  padding: "6px 10px",
  borderRadius: 8,
  border: "1px solid rgba(127,208,255,0.12)",
  background: "rgba(0,0,0,0.22)",
};

const skosSearchInputStyle: React.CSSProperties = {
  flex: 1,
  background: "transparent",
  border: "none",
  outline: "none",
  color: "#ebf3ff",
  fontSize: 12,
};

const skosBodyStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  display: "flex",
  overflow: "hidden",
};

const treeColStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "8px 6px",
};

const detailPanelStyle: React.CSSProperties = {
  width: 300,
  flexShrink: 0,
  display: "flex",
  flexDirection: "column",
  borderLeft: "1px solid rgba(127,208,255,0.1)",
  background: "rgba(3,9,18,0.5)",
  overflow: "hidden",
};

const detailHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "12px 14px",
  borderBottom: "1px solid rgba(127,208,255,0.08)",
  flexShrink: 0,
};

const detailBodyStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "14px",
};

const schemePanelStyle: React.CSSProperties = {
  borderRadius: 10,
  border: "1px solid rgba(127,208,255,0.1)",
  background: "rgba(255,255,255,0.02)",
  overflow: "hidden",
  marginBottom: 8,
};

const schemeHeaderBtnStyle: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 12px",
  background: "transparent",
  border: "none",
  cursor: "pointer",
  borderBottom: "1px solid rgba(255,255,255,0.05)",
};

const expandBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#8fa8c6",
  cursor: "pointer",
  padding: 0,
  display: "flex",
  alignItems: "center",
  flexShrink: 0,
  width: 18,
};

const chipStyle: React.CSSProperties = {
  padding: "2px 8px",
  borderRadius: 999,
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.08)",
  color: "#8fa8c6",
  fontSize: 11,
};

const iconBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#8fa8c6",
  cursor: "pointer",
  padding: 2,
  display: "grid",
  placeItems: "center",
};

const navLinkStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  background: "transparent",
  border: "none",
  cursor: "pointer",
  padding: "2px 0",
  textAlign: "left",
};

const centerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  padding: 24,
};
