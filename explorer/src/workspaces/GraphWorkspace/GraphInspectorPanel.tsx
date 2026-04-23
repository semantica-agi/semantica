import type { CSSProperties } from "react";
import { Loader2 } from "lucide-react";
import { graph } from "../../store/graphStore";
import { GRAPH_THEME } from "./graphTheme";

export type LinkPrediction = {
  target: string;
  type: string;
  label?: string;
  score: number;
};

export type PathResponse = {
  path: string[];
  edge_ids?: string[];
  total_weight: number;
  hop_count: number;
  distance_band: "direct" | "near" | "mid-range" | "distant";
};

export interface GraphInspectorPanelProps {
  nodeId: string;
  predictions: LinkPrediction[];
  predictionType: string;
  onPredictionTypeChange: (value: string) => void;
  onRunPredictions: () => void;
  isRunningPredictions?: boolean;
  pathTargetId: string;
  onPathTargetChange: (value: string) => void;
  onTracePath: () => void;
  pathResult: PathResponse | null;
  onDownloadProvenance: (format: "json" | "markdown") => void;
  onFocusNode?: (nodeId: string) => void;
}

const PROVENANCE_KEYS = ["source", "source_url", "pmid", "pmids", "evidence", "provenance", "confidence"] as const;

function sourceAttribution(properties: Record<string, unknown>) {
  return PROVENANCE_KEYS
    .filter((key) => key in properties)
    .map((key) => ({ key, value: properties[key] }));
}

/* ─── Path Flow Visualizer ──────────────────────────────────────── */

function getNodeLabel(nodeId: string): string {
  if (!graph.hasNode(nodeId)) return nodeId;
  const attrs = graph.getNodeAttributes(nodeId) as { label?: string; content?: string };
  return String(attrs.label ?? attrs.content ?? nodeId);
}

function getEdgeLabelBetween(sourceId: string, targetId: string, edgeIds?: string[]): string {
  // Try to find the specific edge from edgeIds first
  if (edgeIds) {
    for (const edgeId of edgeIds) {
      if (graph.hasEdge(edgeId)) {
        const [src, tgt] = graph.extremities(edgeId);
        if ((src === sourceId && tgt === targetId) || (src === targetId && tgt === sourceId)) {
          const attrs = graph.getEdgeAttributes(edgeId) as { edgeType?: string };
          return attrs.edgeType ?? "→";
        }
      }
    }
  }
  // Fallback: find any edge between the pair
  if (graph.hasNode(sourceId) && graph.hasNode(targetId)) {
    let label = "→";
    graph.forEachEdge(sourceId, targetId, (_edgeId, attrs) => {
      const edgeAttrs = attrs as { edgeType?: string };
      if (edgeAttrs.edgeType) label = edgeAttrs.edgeType;
    });
    return label;
  }
  return "→";
}

function PathFlowViz({
  path,
  edgeIds,
  totalWeight,
  onFocusNode,
}: {
  path: string[];
  edgeIds?: string[];
  totalWeight: number;
  onFocusNode?: (nodeId: string) => void;
}) {
  if (path.length === 0) {
    return <div style={emptyTextStyle}>No path found between the selected nodes.</div>;
  }

  return (
    <div>
      {/* Horizontal scrollable chip flow */}
      <div style={pathFlowContainerStyle}>
        {path.map((nodeId, index) => {
          const label = getNodeLabel(nodeId);
          const edgeLabel =
            index < path.length - 1
              ? getEdgeLabelBetween(nodeId, path[index + 1], edgeIds)
              : null;

          return (
            <div key={`${nodeId}-${index}`} style={{ display: "contents" }}>
              {/* Node chip */}
              <button
                onClick={() => onFocusNode?.(nodeId)}
                title={`Focus: ${nodeId}`}
                style={{
                  ...pathNodeChipStyle,
                  cursor: onFocusNode ? "pointer" : "default",
                }}
              >
                <span style={pathNodeIndexStyle}>{index + 1}</span>
                <span style={{ maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {label}
                </span>
              </button>

              {/* Edge connector */}
              {edgeLabel !== null ? (
                <div style={pathEdgeConnectorStyle}>
                  <div style={{ width: 16, height: 1, background: "rgba(88,166,255,0.3)" }} />
                  <span style={pathEdgeLabelStyle}>{edgeLabel}</span>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <div style={{ width: 12, height: 1, background: "rgba(88,166,255,0.3)" }} />
                    <div style={{ width: 0, height: 0, borderTop: "4px solid transparent", borderBottom: "4px solid transparent", borderLeft: "5px solid rgba(88,166,255,0.4)" }} />
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {/* Weight badge */}
      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ color: "#6a7f97", fontSize: 11 }}>Total weight:</span>
        <span style={{ color: "#79c0ff", fontSize: 12, fontWeight: 700 }}>{totalWeight.toFixed(3)}</span>
        <span style={{ color: "#6a7f97", fontSize: 11 }}>·</span>
        <span style={{ color: "#6a7f97", fontSize: 11 }}>{path.length} hops</span>
      </div>
    </div>
  );
}

/* ─── Main Panel ─────────────────────────────────────────────────── */

export function GraphInspectorPanel({
  nodeId,
  predictions,
  predictionType,
  onPredictionTypeChange,
  onRunPredictions,
  isRunningPredictions = false,
  pathTargetId,
  onPathTargetChange,
  onTracePath,
  pathResult,
  onDownloadProvenance,
  onFocusNode,
}: GraphInspectorPanelProps) {
  if (!nodeId) {
    return (
      <div style={{ padding: 32, textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 12, marginTop: 32 }}>
        <div style={{ width: 40, height: 40, borderRadius: "50%", background: "rgba(74,163,255,0.08)", border: "1px solid rgba(74,163,255,0.14)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: "rgba(127,208,255,0.3)" }} />
        </div>
        <p style={{ color: "#8b949e", fontSize: 14, margin: 0, lineHeight: 1.6 }}>
          Search for a node or click one in the canvas to inspect its properties.
        </p>
      </div>
    );
  }

  if (!graph.hasNode(nodeId)) {
    return (
      <div style={{ padding: 24, color: "#8b949e", fontSize: 13, lineHeight: 1.6 }}>
        Selected item is not available for inspection in the current graph.
      </div>
    );
  }

  const attributes = graph.getNodeAttributes(nodeId) as {
    color?: string;
    content?: string;
    label?: string;
    nodeType?: string;
    valid_from?: string | null;
    valid_until?: string | null;
    properties?: Record<string, unknown>;
  };
  const properties = attributes?.properties ?? {};
  const attribution = sourceAttribution(properties);
  const accentColor = attributes?.color || "#58a6ff";
  const propertyEntries = Object.entries(properties).filter(
    ([key]) =>
      !["x","y","valid_from","valid_until","content","source","source_url","pmid","pmids","evidence","provenance","confidence"].includes(key),
  );

  return (
    <aside style={{ padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Node identity */}
      <div style={{ borderBottom: "1px solid rgba(88, 166, 255, 0.2)", paddingBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <span style={{ background: accentColor, boxShadow: `0 0 10px ${accentColor}`, width: 8, height: 8, borderRadius: "50%" }} />
          <span style={{ color: accentColor, fontSize: 12, fontWeight: 700 }}>{attributes?.nodeType || "Entity"}</span>
        </div>
        <h3 style={{ margin: 0, color: "#fff", fontSize: 20, fontWeight: 700, wordBreak: "break-word" }}>
          {String(attributes?.label ?? nodeId)}
        </h3>
        <div style={{ color: "#8b949e", fontSize: 12, marginTop: 6, fontFamily: "monospace", wordBreak: "break-all" }}>{nodeId}</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {attributes?.valid_from || attributes?.valid_until ? (
            <span style={subtleChipStyle}>temporal</span>
          ) : null}
          {attribution.length ? <span style={subtleChipStyle}>{attribution.length} source fields</span> : null}
          {predictions.length ? <span style={subtleChipStyle}>{predictions.length} candidate links</span> : null}
        </div>
      </div>

      {/* Temporal bounds */}
      {(attributes?.valid_from || attributes?.valid_until) ? (
        <div style={{ padding: "10px 12px", background: "rgba(88,166,255,0.08)", border: "1px solid rgba(88,166,255,0.2)", borderRadius: 8, fontSize: 12, color: "#79c0ff", fontFamily: "monospace" }}>
          {attributes?.valid_from ? <div>from: {attributes.valid_from}</div> : null}
          {attributes?.valid_until ? <div>until: {attributes.valid_until}</div> : null}
        </div>
      ) : null}

      {/* Actions */}
      <section style={sectionStyle}>
        <div style={sectionTitleStyle}>Actions</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <button
            style={{ ...actionButtonStyle, width: "100%", justifyContent: "center", opacity: isRunningPredictions ? 0.7 : 1 }}
            onClick={onRunPredictions}
            disabled={isRunningPredictions}
          >
            {isRunningPredictions ? (
              <Loader2 size={14} className="animate-spin" style={{ marginRight: 6 }} />
            ) : null}
            {isRunningPredictions ? "Running…" : "Run Link Prediction"}
          </button>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button style={secondaryActionButtonStyle} onClick={() => onDownloadProvenance("json")}>
              Provenance JSON
            </button>
            <button style={secondaryActionButtonStyle} onClick={() => onDownloadProvenance("markdown")}>
              Provenance MD
            </button>
          </div>
        </div>
        <input
          value={predictionType}
          onChange={(event) => onPredictionTypeChange(event.target.value)}
          placeholder="Optional candidate type filter, e.g. disease"
          style={inputStyle}
        />
      </section>

      {/* Trace Path */}
      <section style={sectionStyle}>
        <div style={sectionTitleStyle}>Trace Path</div>
        <input
          value={pathTargetId}
          onChange={(event) => onPathTargetChange(event.target.value)}
          placeholder="Target node ID"
          style={inputStyle}
        />
        <button style={actionButtonStyle} onClick={onTracePath}>Trace Causal Path</button>

        {pathResult?.path?.length ? (
          <PathFlowViz
            path={pathResult.path}
            edgeIds={pathResult.edge_ids}
            totalWeight={pathResult.total_weight}
            onFocusNode={onFocusNode}
          />
        ) : (
          <div style={emptyTextStyle}>
            Choose a target or click a candidate prediction to prepare a path trace.
          </div>
        )}
      </section>

      {/* Candidate Links */}
      <details className="node-panel-collapse" open={predictions.length > 0}>
        <summary className="node-panel-summary">Candidate Links</summary>
        <div className="node-panel-body">
          {predictions.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {predictions.map((prediction) => (
                <button
                  key={`${prediction.target}-${prediction.type}`}
                  style={predictionCardStyle}
                  onClick={() => onPathTargetChange(prediction.target)}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div>
                      <div style={{ color: "#fff", fontWeight: 600 }}>{prediction.label || prediction.target}</div>
                      <div style={{ color: "#8b949e", fontSize: 12 }}>{prediction.type}</div>
                    </div>
                    <div style={{ flexShrink: 0 }}>
                      <div style={{
                        padding: "2px 7px",
                        borderRadius: 999,
                        fontSize: 10,
                        fontWeight: 700,
                        background: "rgba(88,166,255,0.12)",
                        border: "1px solid rgba(88,166,255,0.22)",
                        color: "#58a6ff",
                      }}>
                        {(prediction.score * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : isRunningPredictions ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 8, color: "#8b949e", fontSize: 12 }}>
              <Loader2 size={13} className="animate-spin" />
              <span>Computing candidate links…</span>
            </div>
          ) : (
            <div style={emptyTextStyle}>Run link prediction to surface likely next-hop relationships.</div>
          )}
        </div>
      </details>

      {/* Source Attribution */}
      <details className="node-panel-collapse">
        <summary className="node-panel-summary">Source Attribution</summary>
        <div className="node-panel-body">
          {attribution.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {attribution.map(({ key, value }) => (
                <div key={key} style={propertyCardStyle}>
                  <div style={{ color: "rgba(88,166,255,0.7)", fontSize: 11, marginBottom: 4 }}>{key}</div>
                  <div style={{ color: "#e6edf3", fontSize: 13, wordBreak: "break-word" }}>
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={emptyTextStyle}>No explicit attribution metadata was found on this node.</div>
          )}
        </div>
      </details>

      {/* Properties */}
      <details className="node-panel-collapse">
        <summary className="node-panel-summary">Properties</summary>
        <div className="node-panel-body">
          {propertyEntries.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {propertyEntries.map(([key, value]) => (
                <div key={key} style={propertyCardStyle}>
                  <div style={{ color: "rgba(88,166,255,0.7)", fontSize: 11, marginBottom: 4 }}>{key}</div>
                  <div style={{ color: "#e6edf3", fontSize: 13, wordBreak: "break-word" }}>
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={emptyTextStyle}>No additional properties are attached to this node.</div>
          )}
        </div>
      </details>
    </aside>
  );
}

/* ─── styles ─────────────────────────────────────────────────────── */

const inputStyle: CSSProperties = {
  width: "100%",
  background: "rgba(4, 10, 18, 0.5)",
  border: `1px solid ${GRAPH_THEME.palette.background.shellBorder}`,
  color: "#edf5ff",
  borderRadius: 12,
  padding: "11px 13px",
  fontSize: 13,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
};

const actionButtonStyle: CSSProperties = {
  background: "linear-gradient(135deg, rgba(24, 63, 133, 0.42), rgba(35, 85, 176, 0.28))",
  color: "#fff",
  border: `1px solid ${GRAPH_THEME.palette.background.shellBorder}`,
  borderRadius: 12,
  padding: "9px 12px",
  cursor: "pointer",
  fontWeight: 700,
  fontSize: 12,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  boxShadow: `0 8px 22px ${GRAPH_THEME.palette.background.shellGlow}`,
};

const secondaryActionButtonStyle: CSSProperties = {
  ...actionButtonStyle,
  background: "rgba(255, 255, 255, 0.03)",
  border: "1px solid rgba(255, 255, 255, 0.08)",
  color: "#c6d4e3",
  fontWeight: 600,
};

const predictionCardStyle: CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  background: "rgba(88, 166, 255, 0.08)",
  border: "1px solid rgba(88, 166, 255, 0.12)",
  borderRadius: 10,
  cursor: "pointer",
  width: "100%",
};

const propertyCardStyle: CSSProperties = {
  background: "rgba(0, 0, 0, 0.2)",
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid rgba(255, 255, 255, 0.05)",
};

const emptyTextStyle: CSSProperties = {
  color: "#8b949e",
  fontSize: 12,
  lineHeight: 1.5,
};

const subtleChipStyle: CSSProperties = {
  background: "rgba(255, 255, 255, 0.04)",
  color: "#9fb6d2",
  padding: "4px 8px",
  borderRadius: 999,
  fontSize: 11,
  border: "1px solid rgba(255, 255, 255, 0.06)",
};

const sectionStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 10,
  padding: 14,
  background: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015))",
  border: "1px solid rgba(255, 255, 255, 0.06)",
  borderRadius: 14,
};

const sectionTitleStyle: CSSProperties = {
  color: "#8b949e",
  fontSize: 11,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const pathFlowContainerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 0,
  flexWrap: "wrap",
  rowGap: 8,
};

const pathNodeChipStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "5px 10px",
  borderRadius: 999,
  background: "rgba(88,166,255,0.1)",
  border: "1px solid rgba(88,166,255,0.22)",
  color: "#e6edf3",
  fontSize: 12,
  fontWeight: 600,
  maxWidth: 160,
};

const pathNodeIndexStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 16,
  height: 16,
  borderRadius: "50%",
  background: "rgba(88,166,255,0.22)",
  color: "#79c0ff",
  fontSize: 9,
  fontWeight: 800,
  flexShrink: 0,
};

const pathEdgeConnectorStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 2,
  flexShrink: 0,
};

const pathEdgeLabelStyle: CSSProperties = {
  fontSize: 9,
  fontWeight: 700,
  color: "#6a7f97",
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  maxWidth: 70,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
