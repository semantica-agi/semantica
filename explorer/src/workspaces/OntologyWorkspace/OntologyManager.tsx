import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  BookMarked,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  GitMerge,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { OntologyLoader } from "./OntologyLoader";
import { OntologySearch } from "./OntologySearch";
import { SKOSVocabularyManager } from "./SKOSVocabularyManager";

interface OntologyEntry {
  uri: string;
  name: string;
  description?: string;
  format: string;
  status: "published" | "draft" | "external";
  source_url?: string;
  version?: string;
  class_count: number;
  concept_count: number;
  property_count: number;
  loaded_at: string;
  enabled: boolean;
  tags: string[];
}

type RightPanel = "none" | "search" | "skos";

const STATUS_COLORS: Record<string, string> = {
  published: "#4cc38a",
  draft: "#f2b66d",
  external: "#58a6ff",
};

const FORMAT_COLORS: Record<string, string> = {
  turtle: "#9ee8d7",
  xml: "#ff9daf",
  "json-ld": "#f2b66d",
  nt: "#d2a8ff",
  unknown: "#6a7f97",
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || "#6a7f97";
  return (
    <span
      style={{
        padding: "2px 7px",
        borderRadius: 999,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.07em",
        textTransform: "uppercase" as const,
        background: `${color}18`,
        border: `1px solid ${color}33`,
        color,
      }}
    >
      {status}
    </span>
  );
}

function FormatBadge({ format }: { format: string }) {
  const color = FORMAT_COLORS[format] || FORMAT_COLORS.unknown;
  return (
    <span
      style={{
        padding: "2px 7px",
        borderRadius: 999,
        fontSize: 10,
        fontWeight: 700,
        background: `${color}14`,
        border: `1px solid ${color}28`,
        color,
      }}
    >
      {format}
    </span>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
      <span style={{ color: "#ebf3ff", fontSize: 14, fontWeight: 800 }}>
        {value.toLocaleString()}
      </span>
      <span style={{ color: "#6a7f97", fontSize: 10 }}>{label}</span>
    </div>
  );
}

function RegistryRow({
  entry,
  selected,
  onSelect,
  onToggle,
  onRefresh,
  onRemove,
}: {
  entry: OntologyEntry;
  selected: boolean;
  onSelect: (e: OntologyEntry) => void;
  onToggle: (uri: string) => void;
  onRefresh: (uri: string) => void;
  onRemove: (uri: string) => void;
}) {
  const [busyToggle, setBusyToggle] = useState(false);
  const [busyRefresh, setBusyRefresh] = useState(false);
  const [busyRemove, setBusyRemove] = useState(false);

  const handleToggle = async (ev: React.MouseEvent) => {
    ev.stopPropagation();
    setBusyToggle(true);
    await onToggle(entry.uri);
    setBusyToggle(false);
  };

  const handleRefresh = async (ev: React.MouseEvent) => {
    ev.stopPropagation();
    setBusyRefresh(true);
    await onRefresh(entry.uri);
    setBusyRefresh(false);
  };

  const handleRemove = async (ev: React.MouseEvent) => {
    ev.stopPropagation();
    if (!window.confirm(`Remove "${entry.name}" from the registry?`)) return;
    setBusyRemove(true);
    await onRemove(entry.uri);
    setBusyRemove(false);
  };

  return (
    <div
      onClick={() => onSelect(entry)}
      style={{
        ...rowStyle,
        background: selected
          ? "rgba(74,163,255,0.1)"
          : "rgba(255,255,255,0.02)",
        borderColor: selected
          ? "rgba(127,208,255,0.26)"
          : "rgba(127,208,255,0.1)",
        opacity: entry.enabled ? 1 : 0.55,
      }}
    >
      <div style={rowMainStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={rowNameStyle}>{entry.name}</span>
          <StatusBadge status={entry.status} />
          <FormatBadge format={entry.format} />
          {!entry.enabled && (
            <span style={disabledBadgeStyle}>Disabled</span>
          )}
        </div>
        <div style={rowUriStyle}>{entry.uri}</div>
        {entry.source_url && (
          <a
            href={entry.source_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={sourceLinkStyle}
          >
            <ExternalLink size={10} />
            {entry.source_url.slice(0, 60)}{entry.source_url.length > 60 ? "…" : ""}
          </a>
        )}
      </div>

      <div style={rowStatsStyle}>
        <Stat value={entry.class_count} label="Classes" />
        <Stat value={entry.concept_count} label="Concepts" />
        <Stat value={entry.property_count} label="Props" />
      </div>

      <div style={rowActionsStyle}>
        <button
          title={entry.enabled ? "Disable" : "Enable"}
          onClick={handleToggle}
          disabled={busyToggle}
          style={actionBtnStyle}
        >
          {busyToggle ? (
            <Loader2 size={13} style={{ animation: "spin 0.8s linear infinite" }} />
          ) : entry.enabled ? (
            <ToggleRight size={15} color="#4cc38a" />
          ) : (
            <ToggleLeft size={15} color="#6a7f97" />
          )}
        </button>

        {entry.source_url && (
          <button
            title="Re-fetch from source URL"
            onClick={handleRefresh}
            disabled={busyRefresh}
            style={actionBtnStyle}
          >
            {busyRefresh ? (
              <Loader2 size={13} style={{ animation: "spin 0.8s linear infinite" }} />
            ) : (
              <RefreshCw size={13} color="#58a6ff" />
            )}
          </button>
        )}

        <button
          title="Remove from registry"
          onClick={handleRemove}
          disabled={busyRemove}
          style={{ ...actionBtnStyle, color: "#ff9daf" }}
        >
          {busyRemove ? (
            <Loader2 size={13} style={{ animation: "spin 0.8s linear infinite" }} />
          ) : (
            <Trash2 size={13} />
          )}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function OntologyManager() {
  const [entries, setEntries] = useState<OntologyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQ, setSearchQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showLoader, setShowLoader] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<OntologyEntry | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanel>("none");
  const [actionMsg, setActionMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const fetchRegistry = useCallback(async () => {
    setLoading(true);
    setActionMsg(null);
    try {
      const params = new URLSearchParams();
      if (searchQ) params.set("q", searchQ);
      const res = await fetch(`/api/ontology/registry?${params}`);
      if (res.ok) {
        setEntries(await res.json());
      } else {
        // Non-OK response — show empty state with a soft warning (not a blocking error)
        setEntries([]);
        if (res.status !== 404) {
          flashMsg("err", `Registry unavailable (HTTP ${res.status}) — connect the backend to load ontologies`);
        }
      }
    } catch {
      // Network error — backend not running; show empty state silently
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [searchQ, statusFilter]);

  useEffect(() => {
    fetchRegistry();
  }, [fetchRegistry]);

  const flashMsg = (type: "ok" | "err", text: string) => {
    setActionMsg({ type, text });
    setTimeout(() => setActionMsg(null), 3000);
  };

  const handleToggle = useCallback(async (uri: string) => {
    try {
      const res = await fetch(`/api/ontology/${encodeURIComponent(uri)}/toggle`, {
        method: "PATCH",
      });
      if (!res.ok) throw new Error("Toggle failed");
      const data = await res.json();
      setEntries((prev) =>
        prev.map((e) => (e.uri === uri ? { ...e, enabled: data.enabled } : e))
      );
    } catch {
      flashMsg("err", "Could not toggle ontology");
    }
  }, []);

  const handleRefresh = useCallback(async (uri: string) => {
    try {
      const res = await fetch(`/api/ontology/${encodeURIComponent(uri)}/refresh`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Refresh failed");
      flashMsg("ok", "Ontology refreshed");
      fetchRegistry();
    } catch {
      flashMsg("err", "Refresh failed — check source URL");
    }
  }, [fetchRegistry]);

  const handleRemove = useCallback(async (uri: string) => {
    try {
      const res = await fetch(`/api/ontology/${encodeURIComponent(uri)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Remove failed");
      setEntries((prev) => prev.filter((e) => e.uri !== uri));
      if (selectedEntry?.uri === uri) setSelectedEntry(null);
      flashMsg("ok", "Removed from registry");
    } catch {
      flashMsg("err", "Could not remove ontology");
    }
  }, [selectedEntry]);

  const handleSelect = (entry: OntologyEntry) => {
    setSelectedEntry((prev) => (prev?.uri === entry.uri ? null : entry));
    setRightPanel("none");
  };

  const handleLoaded = () => {
    setShowLoader(false);
    fetchRegistry();
  };

  const filteredEntries = entries.filter((e) => {
    if (statusFilter === "owl") return ["owl:Ontology"].includes(e.format) || e.format === "xml" || e.format === "turtle";
    if (statusFilter === "skos") return e.concept_count > 0;
    if (statusFilter === "internal") return e.status === "draft" || e.status === "published";
    if (statusFilter === "external") return e.status === "external";
    return true;
  });

  const isSKOS = selectedEntry ? selectedEntry.concept_count > 0 : false;

  return (
    <>
      {showLoader && (
        <OntologyLoader
          onLoaded={handleLoaded}
          onClose={() => setShowLoader(false)}
        />
      )}

      <div style={shellStyle}>
        {/* Toolbar */}
        <div style={toolbarStyle}>
          <div style={searchBoxStyle}>
            <Search size={14} color="#6a7f97" />
            <input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder="Search ontologies by name, URI, or namespace…"
              style={searchInputStyle}
            />
          </div>

          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {(["all", "owl", "skos", "internal", "external"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                style={{
                  ...filterPillBase,
                  ...(statusFilter === f ? filterPillActive : filterPillIdle),
                }}
              >
                {f === "all" ? "All" : f.toUpperCase()}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
            <button
              onClick={() => setRightPanel((p) => (p === "search" ? "none" : "search"))}
              style={{
                ...toolBtnStyle,
                ...(rightPanel === "search" ? toolBtnActive : {}),
              }}
            >
              <Search size={13} />
              Entity Search
            </button>
            <button
              onClick={() => setShowLoader(true)}
              style={primaryToolBtnStyle}
            >
              <Plus size={13} />
              Load Ontology
            </button>
          </div>
        </div>

        {actionMsg && (
          <div
            style={{
              ...actionMsgStyle,
              borderColor:
                actionMsg.type === "ok"
                  ? "rgba(76,195,138,0.22)"
                  : "rgba(255,157,175,0.22)",
              background:
                actionMsg.type === "ok"
                  ? "rgba(76,195,138,0.06)"
                  : "rgba(255,157,175,0.06)",
              color: actionMsg.type === "ok" ? "#4cc38a" : "#ff9daf",
            }}
          >
            {actionMsg.type === "ok" ? (
              <CheckCircle2 size={13} />
            ) : (
              <AlertCircle size={13} />
            )}
            {actionMsg.text}
          </div>
        )}

        {/* Main content area */}
        <div style={mainAreaStyle}>
          {/* Registry list */}
          <div style={listPanelStyle}>
            {loading ? (
              <div style={centerStyle}>
                <Loader2 size={22} color="#4aa3ff" style={{ animation: "spin 1s linear infinite" }} />
                <span style={{ color: "#8fa8c6", fontSize: 13, marginTop: 10 }}>Loading registry…</span>
              </div>
            ) : filteredEntries.length === 0 ? (
              <div style={emptyStateStyle}>
                <BookMarked size={36} color="rgba(74,163,255,0.18)" />
                <div style={{ color: "#8fa8c6", fontSize: 14, fontWeight: 600, marginTop: 14 }}>
                  {searchQ ? "No ontologies match your search" : "No ontologies loaded yet"}
                </div>
                <div style={{ color: "#6a7f97", fontSize: 12, marginTop: 6, textAlign: "center", maxWidth: 300, lineHeight: 1.6 }}>
                  {searchQ
                    ? "Try a different search term or clear the filter."
                    : <>Import from a URL, upload a file, or create a new ontology to get started. Click <strong style={{ color: "#7fd0ff" }}>Load Ontology</strong> above.</>}
                </div>
                {!searchQ && (
                  <button onClick={() => setShowLoader(true)} style={{ ...primaryToolBtnStyle, marginTop: 18 }}>
                    <Plus size={13} />
                    Load Ontology
                  </button>
                )}
              </div>
            ) : (
              <div style={listStyle}>
                <div style={listHeaderStyle}>
                  <span style={listHeaderTextStyle}>
                    {filteredEntries.length} ontolog{filteredEntries.length === 1 ? "y" : "ies"}
                  </span>
                </div>
                {filteredEntries.map((entry) => (
                  <RegistryRow
                    key={entry.uri}
                    entry={entry}
                    selected={selectedEntry?.uri === entry.uri}
                    onSelect={handleSelect}
                    onToggle={handleToggle}
                    onRefresh={handleRefresh}
                    onRemove={handleRemove}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Right panel */}
          {rightPanel === "search" && (
            <div style={rightPanelStyle}>
              <div style={rightPanelHeaderStyle}>
                <span style={rightPanelTitleStyle}>Entity Search</span>
                <button onClick={() => setRightPanel("none")} style={closePanelBtnStyle}>×</button>
              </div>
              <OntologySearch />
            </div>
          )}

          {rightPanel === "none" && selectedEntry && (
            <div style={rightPanelStyle}>
              <div style={rightPanelHeaderStyle}>
                <span style={rightPanelTitleStyle}>{selectedEntry.name}</span>
                <div style={{ display: "flex", gap: 6 }}>
                  {isSKOS && (
                    <button
                      onClick={() => setRightPanel("skos")}
                      style={browseBtnStyle}
                    >
                      <BookOpen size={12} />
                      Browse SKOS
                    </button>
                  )}
                  <button onClick={() => setSelectedEntry(null)} style={closePanelBtnStyle}>×</button>
                </div>
              </div>
              <div style={detailBodyStyle}>
                <DetailSection label="URI">
                  <span style={{ fontFamily: "monospace", fontSize: 11, wordBreak: "break-all", color: "#c6d4e3" }}>
                    {selectedEntry.uri}
                  </span>
                </DetailSection>
                {selectedEntry.description && (
                  <DetailSection label="Description">
                    <span style={{ color: "#c6d4e3", fontSize: 13, lineHeight: 1.6 }}>
                      {selectedEntry.description}
                    </span>
                  </DetailSection>
                )}
                {selectedEntry.source_url && (
                  <DetailSection label="Source URL">
                    <a
                      href={selectedEntry.source_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: "#58a6ff", fontSize: 11, wordBreak: "break-all" }}
                    >
                      {selectedEntry.source_url}
                    </a>
                  </DetailSection>
                )}
                {selectedEntry.version && (
                  <DetailSection label="Version">
                    <span style={{ color: "#c6d4e3", fontSize: 12 }}>{selectedEntry.version}</span>
                  </DetailSection>
                )}
                {selectedEntry.loaded_at && (
                  <DetailSection label="Loaded at">
                    <span style={{ color: "#c6d4e3", fontSize: 12 }}>
                      {new Date(selectedEntry.loaded_at).toLocaleString()}
                    </span>
                  </DetailSection>
                )}
                <div style={statRowStyle}>
                  <StatBlock value={selectedEntry.class_count} label="Classes" color="#d2a8ff" />
                  <StatBlock value={selectedEntry.concept_count} label="Concepts" color="#9ee8d7" />
                  <StatBlock value={selectedEntry.property_count} label="Properties" color="#f2b66d" />
                </div>
                {selectedEntry.tags.length > 0 && (
                  <DetailSection label="Tags">
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {selectedEntry.tags.map((tag) => (
                        <span key={tag} style={tagChipStyle}>{tag}</span>
                      ))}
                    </div>
                  </DetailSection>
                )}
              </div>
            </div>
          )}

          {rightPanel === "skos" && selectedEntry && (
            <div style={rightPanelStyle}>
              <div style={rightPanelHeaderStyle}>
                <span style={rightPanelTitleStyle}>SKOS — {selectedEntry.name}</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={() => setRightPanel("none")} style={browseBtnStyle}>
                    <Layers size={12} />
                    Registry Detail
                  </button>
                  <button onClick={() => setRightPanel("none")} style={closePanelBtnStyle}>×</button>
                </div>
              </div>
              <SKOSVocabularyManager schemeUri={selectedEntry.uri} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ─── sub-components ─────────────────────────────────────────────────── */

function DetailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: 10, paddingBottom: 2 }}>
      <div style={{ color: "#6a7f97", fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.07em", marginBottom: 4 }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function StatBlock({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2, padding: "10px 6px", background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)" }}>
      <span style={{ color, fontSize: 18, fontWeight: 800 }}>{value.toLocaleString()}</span>
      <span style={{ color: "#6a7f97", fontSize: 10 }}>{label}</span>
    </div>
  );
}

/* ─── styles ─────────────────────────────────────────────────────────── */

const shellStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  width: "100%",
  height: "100%",
  background: "#0a1525",
  overflow: "hidden",
};

const toolbarStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "12px 18px",
  borderBottom: "1px solid rgba(127,208,255,0.1)",
  background: "rgba(5,12,22,0.72)",
  flexWrap: "wrap",
  flexShrink: 0,
};

const searchBoxStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "7px 12px",
  borderRadius: 10,
  border: "1px solid rgba(127,208,255,0.14)",
  background: "rgba(0,0,0,0.24)",
  flex: "0 0 280px",
};

const searchInputStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  outline: "none",
  color: "#ebf3ff",
  fontSize: 12,
  width: "100%",
};

const filterPillBase: React.CSSProperties = {
  padding: "5px 11px",
  borderRadius: 999,
  border: "1px solid transparent",
  fontSize: 11,
  fontWeight: 700,
  cursor: "pointer",
  transition: "160ms ease",
};

const filterPillIdle: React.CSSProperties = {
  background: "transparent",
  color: "#8fa8c6",
  borderColor: "rgba(127,208,255,0.1)",
};

const filterPillActive: React.CSSProperties = {
  background: "rgba(74,163,255,0.14)",
  color: "#ebf3ff",
  borderColor: "rgba(127,208,255,0.26)",
};

const toolBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "7px 12px",
  borderRadius: 8,
  border: "1px solid rgba(127,208,255,0.16)",
  background: "rgba(74,163,255,0.06)",
  color: "#8fa8c6",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
};

const toolBtnActive: React.CSSProperties = {
  background: "rgba(74,163,255,0.16)",
  color: "#ebf3ff",
  borderColor: "rgba(127,208,255,0.28)",
};

const primaryToolBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 7,
  padding: "7px 14px",
  borderRadius: 9,
  border: "1px solid rgba(74,163,255,0.3)",
  background: "linear-gradient(135deg, rgba(74,163,255,0.2), rgba(74,163,255,0.08))",
  color: "#7fd0ff",
  fontSize: 12,
  fontWeight: 700,
  cursor: "pointer",
};

const actionMsgStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "8px 18px",
  fontSize: 12,
  borderBottom: "1px solid",
  flexShrink: 0,
};

const mainAreaStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  display: "flex",
  overflow: "hidden",
};

const listPanelStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  overflowY: "auto",
  borderRight: "1px solid rgba(127,208,255,0.08)",
};

const listStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "12px 14px",
  gap: 8,
};

const listHeaderStyle: React.CSSProperties = {
  paddingBottom: 6,
};

const listHeaderTextStyle: React.CSSProperties = {
  color: "#6a7f97",
  fontSize: 11,
  fontWeight: 700,
};

const rowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "12px 14px",
  borderRadius: 12,
  border: "1px solid",
  cursor: "pointer",
  transition: "160ms ease",
};

const rowMainStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  display: "flex",
  flexDirection: "column",
  gap: 4,
};

const rowNameStyle: React.CSSProperties = {
  color: "#ebf3ff",
  fontSize: 14,
  fontWeight: 700,
};

const rowUriStyle: React.CSSProperties = {
  color: "#6a7f97",
  fontSize: 11,
  fontFamily: "monospace",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const sourceLinkStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  color: "#58a6ff",
  fontSize: 11,
  textDecoration: "none",
};

const rowStatsStyle: React.CSSProperties = {
  display: "flex",
  gap: 16,
  flexShrink: 0,
};

const rowActionsStyle: React.CSSProperties = {
  display: "flex",
  gap: 4,
  flexShrink: 0,
};

const actionBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  padding: 5,
  borderRadius: 6,
  display: "grid",
  placeItems: "center",
  color: "#8fa8c6",
};

const rightPanelStyle: React.CSSProperties = {
  width: 360,
  flexShrink: 0,
  display: "flex",
  flexDirection: "column",
  borderLeft: "1px solid rgba(127,208,255,0.1)",
  background: "rgba(5,12,22,0.6)",
  overflow: "hidden",
};

const rightPanelHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "14px 16px",
  borderBottom: "1px solid rgba(127,208,255,0.1)",
  flexShrink: 0,
};

const rightPanelTitleStyle: React.CSSProperties = {
  color: "#ebf3ff",
  fontSize: 13,
  fontWeight: 700,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const closePanelBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#8fa8c6",
  cursor: "pointer",
  fontSize: 18,
  lineHeight: 1,
  padding: "0 2px",
};

const browseBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  padding: "4px 10px",
  borderRadius: 7,
  border: "1px solid rgba(127,208,255,0.18)",
  background: "rgba(74,163,255,0.06)",
  color: "#7fd0ff",
  fontSize: 11,
  fontWeight: 600,
  cursor: "pointer",
};

const detailBodyStyle: React.CSSProperties = {
  padding: "14px 16px",
  overflowY: "auto",
  flex: 1,
  display: "flex",
  flexDirection: "column",
  gap: 0,
};

const statRowStyle: React.CSSProperties = {
  display: "flex",
  gap: 6,
  marginTop: 12,
  marginBottom: 4,
};

const tagChipStyle: React.CSSProperties = {
  padding: "3px 8px",
  borderRadius: 999,
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.08)",
  color: "#8fa8c6",
  fontSize: 11,
};

const disabledBadgeStyle: React.CSSProperties = {
  padding: "2px 7px",
  borderRadius: 999,
  fontSize: 10,
  fontWeight: 700,
  background: "rgba(106,127,151,0.12)",
  border: "1px solid rgba(106,127,151,0.2)",
  color: "#6a7f97",
};

const centerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  padding: 40,
};

const emptyStateStyle: React.CSSProperties = {
  ...centerStyle,
  textAlign: "center",
};
