import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Loader2,
  Search,
  X,
} from "lucide-react";

interface SearchResult {
  uri: string;
  label: string;
  type: string;
  entity_type: string;
  definition?: string;
  source_ontology?: string;
  namespace_prefix?: string;
}

interface EntityDetail {
  uri: string;
  label: string;
  type: string;
  entity_type: string;
  definition?: string;
  source_ontology?: string;
  superclasses: string[];
  subclasses: string[];
  domain: string[];
  range: string[];
  instance_count: number;
  properties: Record<string, unknown>;
}

const ENTITY_TYPE_COLORS: Record<string, string> = {
  class: "#d2a8ff",
  property: "#f2b66d",
  individual: "#9ee8d7",
  concept: "#58a6ff",
  scheme: "#7fd0ff",
  unknown: "#6a7f97",
};

const ENTITY_TYPE_LABELS: Record<string, string> = {
  class: "Class",
  property: "Property",
  individual: "Individual",
  concept: "Concept",
  scheme: "Scheme",
  unknown: "Entity",
};

function TypeBadge({ entityType }: { entityType: string }) {
  const color = ENTITY_TYPE_COLORS[entityType] || ENTITY_TYPE_COLORS.unknown;
  return (
    <span
      style={{
        padding: "1px 7px",
        borderRadius: 999,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.06em",
        textTransform: "uppercase" as const,
        background: `${color}14`,
        border: `1px solid ${color}28`,
        color,
        flexShrink: 0,
      }}
    >
      {ENTITY_TYPE_LABELS[entityType] || entityType}
    </span>
  );
}

function UriRef({ uri }: { uri: string }) {
  const short = uri.includes("#")
    ? uri.split("#").pop() || uri
    : uri.split("/").pop() || uri;
  return (
    <span
      title={uri}
      style={{ color: "#58a6ff", fontSize: 11, fontFamily: "monospace", cursor: "help" }}
    >
      {short}
    </span>
  );
}

function ResultRow({
  result,
  selected,
  onSelect,
}: {
  result: SearchResult;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 4,
        padding: "10px 14px",
        borderRadius: 10,
        border: "1px solid",
        cursor: "pointer",
        transition: "160ms ease",
        background: selected ? "rgba(74,163,255,0.1)" : "rgba(255,255,255,0.02)",
        borderColor: selected ? "rgba(127,208,255,0.24)" : "rgba(127,208,255,0.08)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ color: "#ebf3ff", fontSize: 13, fontWeight: 700, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {result.label || result.uri}
        </span>
        <TypeBadge entityType={result.entity_type} />
      </div>
      <div style={{ color: "#6a7f97", fontSize: 10, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {result.uri}
      </div>
      {result.definition && (
        <div style={{ color: "#8fa8c6", fontSize: 12, lineHeight: 1.4, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const }}>
          {result.definition}
        </div>
      )}
      {result.source_ontology && (
        <div style={{ color: "#5a7a9a", fontSize: 10 }}>
          From: {result.source_ontology}
        </div>
      )}
    </div>
  );
}

function CollapsibleList({ label, items }: { label: string; items: string[] }) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        style={collapseHdrStyle}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span>{label}</span>
        <span style={{ color: "#6a7f97", fontSize: 10 }}>({items.length})</span>
      </button>
      {open && (
        <div style={{ marginLeft: 16, marginTop: 4, display: "flex", flexDirection: "column", gap: 3 }}>
          {items.slice(0, 12).map((uri) => (
            <div key={uri} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#6a7f97", fontSize: 10 }}>→</span>
              <UriRef uri={uri} />
            </div>
          ))}
          {items.length > 12 && (
            <span style={{ color: "#5a7a9a", fontSize: 10 }}>+{items.length - 12} more</span>
          )}
        </div>
      )}
    </div>
  );
}

function DetailPanel({
  uri,
  onClose,
}: {
  uri: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetch(`/api/ontology/entity/${encodeURIComponent(uri)}`)
      .then((r) => {
        if (!r.ok) throw new Error("Not found");
        return r.json();
      })
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [uri]);

  return (
    <div style={detailPanelStyle}>
      <div style={detailHeaderStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <BookOpen size={14} color="#d2a8ff" />
          <span style={{ color: "#ebf3ff", fontSize: 13, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            Entity Detail
          </span>
        </div>
        <button onClick={onClose} style={closeDetailBtnStyle}>
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
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
              <h3 style={{ margin: 0, color: "#ebf3ff", fontSize: 17, fontWeight: 800, letterSpacing: "-0.03em" }}>
                {detail.label || detail.uri.split("/").pop()}
              </h3>
              <TypeBadge entityType={detail.entity_type} />
            </div>
            <div style={{ color: "#5a7a9a", fontSize: 10, fontFamily: "monospace", wordBreak: "break-all" }}>
              {detail.uri}
            </div>
          </div>

          {detail.definition && (
            <DetailSection label="Definition">
              <p style={{ margin: 0, color: "#c6d4e3", fontSize: 13, lineHeight: 1.6 }}>
                {detail.definition}
              </p>
            </DetailSection>
          )}

          {detail.instance_count > 0 && (
            <DetailSection label="Instances">
              <span style={{ color: "#9ee8d7", fontSize: 14, fontWeight: 800 }}>
                {detail.instance_count.toLocaleString()}
              </span>
            </DetailSection>
          )}

          <CollapsibleList label="Superclasses / Broader" items={detail.superclasses} />
          <CollapsibleList label="Subclasses / Narrower" items={detail.subclasses} />
          <CollapsibleList label="Domain" items={detail.domain} />
          <CollapsibleList label="Range" items={detail.range} />

          {detail.source_ontology && (
            <DetailSection label="Source Ontology">
              <span style={{ color: "#c6d4e3", fontSize: 12, fontFamily: "monospace" }}>
                {detail.source_ontology}
              </span>
            </DetailSection>
          )}

          <a
            href={detail.uri}
            target="_blank"
            rel="noreferrer"
            style={openUriStyle}
          >
            <ExternalLink size={11} />
            Open URI
          </a>
        </div>
      )}
    </div>
  );
}

function DetailSection({ label, children }: { label: string; children: React.ReactNode }) {
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
// Main OntologySearch component
// ---------------------------------------------------------------------------

export function OntologySearch() {
  const [query, setQuery] = useState("");
  const [entityType, setEntityType] = useState<string>("all");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedUri, setSelectedUri] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runSearch = async (q: string, type: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const params = new URLSearchParams({ q: q.trim(), limit: "80" });
      if (type !== "all") params.set("entity_type", type);
      const res = await fetch(`/api/ontology/search?${params}`);
      if (!res.ok) throw new Error("Search failed");
      setResults(await res.json());
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => runSearch(query, entityType), 320);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query, entityType]);

  return (
    <div style={searchShellStyle}>
      {/* Search input */}
      <div style={searchTopStyle}>
        <div style={searchBarStyle}>
          <Search size={14} color="#6a7f97" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search classes, properties, concepts…"
            style={searchInputStyle}
          />
          {searching && <Loader2 size={13} color="#4aa3ff" style={{ animation: "spin 0.8s linear infinite", flexShrink: 0 }} />}
          {query && !searching && (
            <button onClick={() => { setQuery(""); setResults([]); }} style={clearBtnStyle}>
              <X size={12} />
            </button>
          )}
        </div>

        <div style={typeFilterStyle}>
          {(["all", "class", "property", "individual", "concept", "scheme"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setEntityType(t)}
              style={{
                ...typeFilterBtnBase,
                ...(entityType === t ? typeFilterBtnActive : typeFilterBtnIdle),
              }}
            >
              {t === "all" ? "All" : ENTITY_TYPE_LABELS[t] || t}
            </button>
          ))}
        </div>
      </div>

      {/* Results + detail */}
      <div style={searchBodyStyle}>
        <div style={resultListStyle}>
          {!query && (
            <div style={hintStyle}>
              <Search size={20} color="rgba(74,163,255,0.2)" />
              <span style={{ color: "#6a7f97", fontSize: 12, marginTop: 8 }}>
                Type to search across all loaded ontologies
              </span>
            </div>
          )}

          {query && results.length === 0 && !searching && (
            <div style={hintStyle}>
              <span style={{ color: "#6a7f97", fontSize: 12 }}>No results for "{query}"</span>
            </div>
          )}

          {results.length > 0 && (
            <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ color: "#6a7f97", fontSize: 11, fontWeight: 700, marginBottom: 2 }}>
                {results.length} result{results.length !== 1 ? "s" : ""}
              </div>
              {results.map((r) => (
                <ResultRow
                  key={r.uri}
                  result={r}
                  selected={selectedUri === r.uri}
                  onSelect={() => setSelectedUri((prev) => (prev === r.uri ? null : r.uri))}
                />
              ))}
            </div>
          )}
        </div>

        {selectedUri && (
          <DetailPanel uri={selectedUri} onClose={() => setSelectedUri(null)} />
        )}
      </div>
    </div>
  );
}

/* ─── styles ─────────────────────────────────────────────────────────── */

const searchShellStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100%",
  overflow: "hidden",
};

const searchTopStyle: React.CSSProperties = {
  padding: "12px 14px 10px",
  borderBottom: "1px solid rgba(127,208,255,0.08)",
  display: "flex",
  flexDirection: "column",
  gap: 8,
  flexShrink: 0,
};

const searchBarStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "7px 12px",
  borderRadius: 10,
  border: "1px solid rgba(127,208,255,0.14)",
  background: "rgba(0,0,0,0.24)",
};

const searchInputStyle: React.CSSProperties = {
  flex: 1,
  background: "transparent",
  border: "none",
  outline: "none",
  color: "#ebf3ff",
  fontSize: 13,
};

const clearBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#6a7f97",
  cursor: "pointer",
  padding: 2,
  display: "grid",
  placeItems: "center",
};

const typeFilterStyle: React.CSSProperties = {
  display: "flex",
  gap: 5,
  flexWrap: "wrap",
};

const typeFilterBtnBase: React.CSSProperties = {
  padding: "4px 10px",
  borderRadius: 999,
  border: "1px solid transparent",
  fontSize: 11,
  fontWeight: 600,
  cursor: "pointer",
  transition: "160ms ease",
};

const typeFilterBtnIdle: React.CSSProperties = {
  background: "transparent",
  color: "#8fa8c6",
  borderColor: "rgba(127,208,255,0.1)",
};

const typeFilterBtnActive: React.CSSProperties = {
  background: "rgba(74,163,255,0.14)",
  color: "#ebf3ff",
  borderColor: "rgba(127,208,255,0.26)",
};

const searchBodyStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  display: "flex",
  overflow: "hidden",
};

const resultListStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  minWidth: 0,
};

const hintStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  padding: 32,
};

const detailPanelStyle: React.CSSProperties = {
  width: 320,
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

const closeDetailBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#8fa8c6",
  cursor: "pointer",
  padding: 2,
  display: "grid",
  placeItems: "center",
};

const detailBodyStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "14px",
  display: "flex",
  flexDirection: "column",
  gap: 0,
};

const centerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  padding: 24,
};

const collapseHdrStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 5,
  background: "transparent",
  border: "none",
  color: "#8fa8c6",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
  padding: "6px 0",
  width: "100%",
  textAlign: "left",
};

const openUriStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  marginTop: 14,
  color: "#58a6ff",
  fontSize: 11,
  textDecoration: "none",
};
