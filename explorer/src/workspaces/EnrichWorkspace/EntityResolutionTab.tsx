/**
 * src/workspaces/EnrichWorkspace/EntityResolutionTab.tsx
 *
 * Entity Resolution — run duplicate detection, review flagged pairs,
 * perform one-click merges, and view merge history from the Registry.
 */
import { useState, useCallback } from "react";
import { ScanSearch, GitMerge, X, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { logEvent, useRegistry } from "../../store/registryStore";

interface DedupPair {
  a: { id: string; label: string; type: string };
  b: { id: string; label: string; type: string };
  score: number;
  dismissed?: boolean;
}

interface RawDuplicateItem {
  entity_a?: string | Record<string, unknown>;
  entity_b?: string | Record<string, unknown>;
  similarity?: number;
  score?: number;
  [key: string]: unknown;
}

function extractId(entity: string | Record<string, unknown> | undefined): string {
  if (!entity) return "";
  if (typeof entity === "string") return entity;
  return String(entity.id ?? entity.text ?? JSON.stringify(entity));
}

function extractLabel(entity: string | Record<string, unknown> | undefined): string {
  if (!entity) return "";
  if (typeof entity === "string") return entity;
  return String(entity.text ?? entity.label ?? entity.content ?? entity.id ?? "");
}

function extractType(entity: string | Record<string, unknown> | undefined): string {
  if (!entity || typeof entity === "string") return "entity";
  return String(entity.type ?? "entity");
}

function parseDuplicates(raw: RawDuplicateItem[]): DedupPair[] {
  return raw.map((item) => ({
    a: {
      id: extractId(item.entity_a as string | Record<string, unknown>),
      label: extractLabel(item.entity_a as string | Record<string, unknown>),
      type: extractType(item.entity_a as string | Record<string, unknown>),
    },
    b: {
      id: extractId(item.entity_b as string | Record<string, unknown>),
      label: extractLabel(item.entity_b as string | Record<string, unknown>),
      type: extractType(item.entity_b as string | Record<string, unknown>),
    },
    score: Number(item.similarity ?? item.score ?? 0),
  }));
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.round(score * 100));
  const color = score >= 0.9 ? "#ff7b72" : score >= 0.75 ? "#f2b66d" : "#4cc38a";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 999, background: color, transition: "width 300ms ease" }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 34, textAlign: "right" }}>
        {pct}%
      </span>
    </div>
  );
}

function PairRow({
  pair,
  onMerge,
  onDismiss,
}: {
  pair: DedupPair;
  onMerge: (primaryId: string, duplicateId: string) => Promise<void>;
  onDismiss: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [merging, setMerging] = useState(false);

  const handleMerge = async () => {
    setMerging(true);
    await onMerge(pair.a.id, pair.b.id);
    setMerging(false);
  };

  return (
    <div style={pairCardStyle}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        {/* Expand */}
        <button onClick={() => setExpanded((v) => !v)} style={iconBtnStyle}>
          {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>

        {/* Entity Labels */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={entityChipStyle}>{pair.a.label || pair.a.id}</span>
            <span style={{ color: "#f2b66d", fontSize: 12, fontWeight: 700 }}>≈</span>
            <span style={entityChipStyle}>{pair.b.label || pair.b.id}</span>
          </div>
          <div style={{ marginTop: 8 }}>
            <ScoreBar score={pair.score} />
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button
            onClick={() => void handleMerge()}
            disabled={merging}
            style={{
              ...actionBtnStyle,
              background: "rgba(76,195,138,0.12)",
              border: "1px solid rgba(76,195,138,0.28)",
              color: "#4cc38a",
            }}
          >
            {merging ? <Loader2 size={12} className="animate-spin" /> : <GitMerge size={12} />}
            <span>Merge</span>
          </button>
          <button onClick={onDismiss} style={iconBtnStyle} title="Dismiss">
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Expanded diff */}
      {expanded ? (
        <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {[
            { label: "Primary (keep)", entity: pair.a, accentColor: "#4aa3ff" },
            { label: "Duplicate (remove)", entity: pair.b, accentColor: "#ff7b72" },
          ].map(({ label, entity, accentColor }) => (
            <div key={entity.id} style={{ ...diffCardStyle, borderColor: `${accentColor}33` }}>
              <div style={{ color: accentColor, fontSize: 10, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>
                {label}
              </div>
              <div style={{ color: "#e6edf3", fontSize: 13, fontWeight: 600 }}>{entity.label || entity.id}</div>
              <div style={{ color: "#8b949e", fontSize: 11, marginTop: 3 }}>{entity.type}</div>
              <div style={{ color: "#6a7f97", fontSize: 10, marginTop: 4, fontFamily: "monospace" }}>{entity.id}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function EntityResolutionTab() {
  const [threshold, setThreshold] = useState(0.82);
  const [scanning, setScanning] = useState(false);
  const [pairs, setPairs] = useState<DedupPair[]>([]);
  const [scanError, setScanError] = useState("");
  const registryEntries = useRegistry();

  const mergeHistory = registryEntries.filter((e) => e.op === "merge");

  const handleScan = useCallback(async () => {
    setScanning(true);
    setScanError("");
    try {
      const res = await fetch("/api/enrich/dedup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threshold }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as Record<string, string>).detail ?? `Scan failed (${res.status})`);
      }
      const data = await res.json();
      const rawDuplicates: RawDuplicateItem[] = Array.isArray(data.duplicates)
        ? (data.duplicates as RawDuplicateItem[])
        : [];
      const parsed = parseDuplicates(rawDuplicates);
      setPairs(parsed);
      logEvent("import", `Dedup scan found ${parsed.length} flagged pair${parsed.length !== 1 ? "s" : ""} (threshold ${threshold.toFixed(2)})`, {
        threshold,
        flagged: parsed.length,
      });
    } catch (err) {
      setScanError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }, [threshold]);

  const handleMerge = useCallback(async (primaryId: string, duplicateId: string) => {
    try {
      const res = await fetch("/api/enrich/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ primary_id: primaryId, duplicate_ids: [duplicateId] }),
      });
      if (!res.ok) throw new Error(`Merge failed (${res.status})`);
      const data = await res.json();
      logEvent("merge", `Merged ${duplicateId} → ${primaryId} · ${data.edges_updated ?? 0} edges redirected`, {
        primary: primaryId,
        duplicate: duplicateId,
        edgesUpdated: data.edges_updated,
      });
      setPairs((prev) => prev.filter((p) => !(p.a.id === primaryId && p.b.id === duplicateId)));
    } catch (err) {
      console.error("[EntityResolution] merge failed", err);
    }
  }, []);

  const handleDismiss = useCallback((index: number) => {
    setPairs((prev) => prev.filter((_, i) => i !== index));
  }, []);

  return (
    <div style={shellStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <ScanSearch size={18} color="#f2b66d" />
          <div>
            <div style={{ color: "#ebf3ff", fontSize: 16, fontWeight: 700 }}>Entity Resolution</div>
            <div style={{ color: "#8b949e", fontSize: 12 }}>Detect and merge duplicate entities in the knowledge graph</div>
          </div>
        </div>
      </div>

      {/* Scan controls */}
      <div style={controlsCardStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <label style={{ color: "#c6d4e3", fontSize: 12, fontWeight: 600 }}>Similarity Threshold</label>
              <span style={{ color: "#f2b66d", fontSize: 12, fontWeight: 700 }}>{threshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={0.5}
              max={0.99}
              step={0.01}
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              style={{ width: "100%", accentColor: "#f2b66d", cursor: "pointer" }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", color: "#6a7f97", fontSize: 10, marginTop: 2 }}>
              <span>More results (0.50)</span>
              <span>Fewer, higher confidence (0.99)</span>
            </div>
          </div>
          <button
            onClick={() => void handleScan()}
            disabled={scanning}
            style={scanBtnStyle}
          >
            {scanning ? <Loader2 size={14} className="animate-spin" /> : <ScanSearch size={14} />}
            <span>{scanning ? "Scanning…" : "Run Dedup Scan"}</span>
          </button>
        </div>
        {scanError ? (
          <div style={{ color: "#ff7b72", fontSize: 12, marginTop: 8 }}>{scanError}</div>
        ) : null}
      </div>

      <div style={{ flex: 1, overflow: "hidden", display: "flex", gap: 0 }}>
        {/* Flagged pairs */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px", display: "flex", flexDirection: "column", gap: 10 }}>
          {pairs.length > 0 ? (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <div style={{ color: "#8b949e", fontSize: 12, fontWeight: 600 }}>
                  {pairs.length} flagged pair{pairs.length !== 1 ? "s" : ""}
                </div>
                <button onClick={() => setPairs([])} style={clearAllBtnStyle}>Clear all</button>
              </div>
              {pairs.map((pair, index) => (
                <PairRow
                  key={`${pair.a.id}:${pair.b.id}`}
                  pair={pair}
                  onMerge={handleMerge}
                  onDismiss={() => handleDismiss(index)}
                />
              ))}
            </>
          ) : (
            <div style={emptyStateStyle}>
              <ScanSearch size={36} color="rgba(242,182,109,0.15)" />
              <div style={{ color: "#8b949e", fontSize: 14, marginTop: 12, fontWeight: 500 }}>
                No flagged pairs
              </div>
              <div style={{ color: "#6a7f97", fontSize: 12, marginTop: 4, textAlign: "center", maxWidth: 280 }}>
                Set a similarity threshold and run a dedup scan to detect potential duplicates.
              </div>
            </div>
          )}
        </div>

        {/* Merge history sidebar */}
        {mergeHistory.length > 0 ? (
          <div style={historyPanelStyle}>
            <div style={{ color: "#8b949e", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 10 }}>
              Merge History
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {mergeHistory.map((entry) => (
                <div key={entry.id} style={historyRowStyle}>
                  <GitMerge size={11} color="#f2b66d" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: "#c6d4e3", fontSize: 11, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {entry.summary}
                    </div>
                    <div style={{ color: "#6a7f97", fontSize: 10 }}>
                      {entry.timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
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
  padding: "20px 24px 16px",
  borderBottom: "1px solid rgba(88,166,255,0.1)",
  flexShrink: 0,
};

const controlsCardStyle: React.CSSProperties = {
  margin: "16px 24px",
  padding: "16px 20px",
  borderRadius: 14,
  background: "linear-gradient(135deg, rgba(13,17,23,0.75), rgba(22,27,34,0.6))",
  border: "1px solid rgba(242,182,109,0.18)",
  flexShrink: 0,
};

const scanBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 7,
  padding: "10px 18px",
  borderRadius: 10,
  background: "linear-gradient(135deg, rgba(242,182,109,0.22), rgba(242,182,109,0.1))",
  border: "1px solid rgba(242,182,109,0.32)",
  color: "#f2b66d",
  fontSize: 13,
  fontWeight: 700,
  cursor: "pointer",
  flexShrink: 0,
};

const pairCardStyle: React.CSSProperties = {
  padding: "12px 14px",
  borderRadius: 12,
  background: "linear-gradient(135deg, rgba(13,17,23,0.6), rgba(22,27,34,0.4))",
  border: "1px solid rgba(255,255,255,0.07)",
};

const entityChipStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "4px 10px",
  borderRadius: 8,
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.08)",
  color: "#e6edf3",
  fontSize: 12,
  fontWeight: 600,
};

const actionBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  padding: "5px 10px",
  borderRadius: 8,
  fontSize: 11,
  fontWeight: 700,
  cursor: "pointer",
};

const iconBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#8b949e",
  cursor: "pointer",
  padding: 4,
  borderRadius: 6,
  display: "flex",
  alignItems: "center",
};

const diffCardStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  background: "rgba(0,0,0,0.2)",
  border: "1px solid transparent",
};

const historyPanelStyle: React.CSSProperties = {
  width: 240,
  borderLeft: "1px solid rgba(255,255,255,0.06)",
  padding: "16px 16px",
  overflowY: "auto",
  flexShrink: 0,
};

const historyRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: 7,
  padding: "8px 0",
  borderBottom: "1px solid rgba(255,255,255,0.04)",
};

const emptyStateStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: 40,
  minHeight: 200,
};

const clearAllBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#8b949e",
  fontSize: 12,
  cursor: "pointer",
  padding: "2px 6px",
  borderRadius: 6,
};
