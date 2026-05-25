import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import { GraphLoadingOverlay } from "./GraphLoadingOverlay";
import { getGraphLoadTitle } from "./graphLoading";
import { useGraphData, useReloadGraphData } from "./useGraphData";
import type {
  ApiNode,
  GraphLayoutStatus,
  GraphLoadProgress,
  GraphPath,
  GraphSelectedNodeState,
  GraphStageHandle,
  GraphViewMode,
} from "./types";

type SearchResult = {
  node: {
    id: string;
    type: string;
    content: string;
    properties: Record<string, unknown>;
  };
  score: number;
};

type LinkPrediction = {
  target: string;
  type: string;
  label?: string;
  score: number;
};

type PathResponse = {
  path: GraphPath;
  total_weight: number;
  hop_count: number;
  distance_band: "direct" | "near" | "mid-range" | "distant";
};

type TemporalBounds = {
  min?: string | null;
  max?: string | null;
};

const GraphRuntimeStage = lazy(() =>
  import("./GraphRuntimeStage").then((module) => ({ default: module.GraphRuntimeStage })),
);
const TimelinePanel = lazy(() =>
  import("./TimelinePanel").then((module) => ({ default: module.TimelinePanel })),
);

const HUD_CSS = `
  .palantir-bg {
    background:
      radial-gradient(circle at top, rgba(103, 182, 255, 0.1), transparent 24%),
      linear-gradient(180deg, #07111d 0%, #02060e 100%);
  }
  .palantir-grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(88, 166, 255, 0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(88, 166, 255, 0.04) 1px, transparent 1px);
    background-size: 44px 44px;
    pointer-events: none;
    z-index: 1;
    opacity: 0.78;
  }
  .palantir-vignette {
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, transparent 34%, rgba(1, 4, 9, 0.88) 100%);
    pointer-events: none;
    z-index: 2;
  }
  .hud-scrollbar::-webkit-scrollbar { width: 6px; }
  .hud-scrollbar::-webkit-scrollbar-track { background: transparent; }
  .hud-scrollbar::-webkit-scrollbar-thumb { background: rgba(88, 166, 255, 0.25); border-radius: 6px; }
  .graph-shell-top { position: absolute; top: 18px; left: 18px; right: 18px; z-index: 10; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; pointer-events: none; }
  .graph-status-card, .graph-command-card {
    pointer-events: auto;
    border: 1px solid rgba(132, 197, 255, 0.12);
    background: linear-gradient(180deg, rgba(7, 16, 29, 0.86), rgba(10, 22, 39, 0.72)), radial-gradient(circle at top, rgba(103, 182, 255, 0.08), transparent 50%);
    box-shadow: 0 18px 42px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255,255,255,0.04);
    backdrop-filter: blur(18px);
  }
  .graph-status-card { width: min(420px, 38vw); border-radius: 24px; padding: 16px 18px; }
  .graph-command-card { width: min(620px, 55vw); border-radius: 24px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
  .graph-status-label { display: inline-flex; align-items: center; gap: 8px; color: rgba(160, 191, 223, 0.88); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; }
  .graph-status-label::before { content: ""; width: 7px; height: 7px; border-radius: 999px; background: linear-gradient(135deg, #8ed3ff, #ffb36a); box-shadow: 0 0 12px rgba(142, 211, 255, 0.5); }
  .graph-status-title { color: #eef5ff; font-size: 20px; font-weight: 800; letter-spacing: -0.04em; margin-bottom: 6px; }
  .graph-status-copy { color: #8fa8c6; font-size: 12px; line-height: 1.55; margin-bottom: 14px; max-width: 40ch; }
  .graph-status-metrics, .graph-command-row, .graph-toggle-cluster, .graph-action-cluster { display: flex; gap: 8px; flex-wrap: wrap; }
  .graph-command-row { justify-content: space-between; align-items: center; gap: 10px; }
  .graph-search-shell { flex: 1; min-width: 260px; display: flex; align-items: center; gap: 10px; padding: 8px 10px 8px 14px; border-radius: 18px; border: 1px solid rgba(132, 197, 255, 0.12); background: rgba(0, 0, 0, 0.18); box-shadow: inset 0 1px 0 rgba(255,255,255,0.03); }
  .graph-search-shell input { flex: 1; min-width: 0; border: none !important; background: transparent !important; padding: 0 !important; margin: 0 !important; }
  .graph-search-shell input:focus { outline: none; }
  .graph-search-results { position: absolute; top: 120px; right: 18px; width: min(420px, calc(100vw - 132px)); max-height: 320px; overflow-y: auto; padding: 12px; border-radius: 20px; border: 1px solid rgba(132, 197, 255, 0.14); background: linear-gradient(180deg, rgba(8, 18, 33, 0.94), rgba(10, 21, 38, 0.86)); box-shadow: 0 18px 50px rgba(0,0,0,0.34); backdrop-filter: blur(18px); pointer-events: auto; z-index: 11; }
  .graph-search-results-label { color: #6f89ab; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; }
  .graph-search-result-card { width: 100%; text-align: left; padding: 12px 14px; border-radius: 16px; border: 1px solid rgba(132, 197, 255, 0.08); background: rgba(255, 255, 255, 0.025); cursor: pointer; transition: transform 160ms ease, border-color 160ms ease, background 160ms ease; }
  .graph-search-result-card:hover { transform: translateY(-1px); border-color: rgba(132, 197, 255, 0.18); background: rgba(103, 182, 255, 0.08); }
  .graph-inspector { pointer-events: auto; position: absolute; right: 18px; top: 154px; bottom: 108px; width: 380px; overflow-y: auto; transition: transform 0.34s cubic-bezier(0.16,1,0.3,1), opacity 0.22s ease; border-radius: 28px; border: 1px solid rgba(132, 197, 255, 0.14); background: linear-gradient(180deg, rgba(8, 18, 33, 0.9), rgba(6, 12, 22, 0.88)), radial-gradient(circle at top, rgba(103, 182, 255, 0.08), transparent 40%); box-shadow: -18px 0 48px rgba(0, 0, 0, 0.32), inset 0 1px 0 rgba(255,255,255,0.04); backdrop-filter: blur(20px); }
  .graph-inspector[data-open='false'] { transform: translateX(calc(100% + 24px)); opacity: 0; }
  @keyframes sem-loader-pulse {
    0%, 100% { transform: translateY(0) scale(0.92); opacity: 0.55; }
    50% { transform: translateY(-4px) scale(1.08); opacity: 1; }
  }
  @media (max-width: 1220px) {
    .graph-shell-top { flex-direction: column; align-items: stretch; }
    .graph-status-card, .graph-command-card { width: auto; }
    .graph-search-results { top: 202px; right: 18px; left: 18px; width: auto; }
  }
`;

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timeout);
  }, [delay, value]);
  return debouncedValue;
}

function sourceAttribution(properties: Record<string, unknown>) {
  const keys = ["source", "source_url", "pmid", "pmids", "evidence", "provenance", "confidence"];
  return keys
    .filter((key) => key in properties)
    .map((key) => ({ key, value: properties[key] }));
}

function toSelectedNodeState(node: ApiNode, neighborCount: number, fallbackColor = "#58a6ff"): GraphSelectedNodeState {
  return {
    id: node.id,
    label: node.content || node.id,
    content: node.content || node.id,
    nodeType: node.type,
    color: fallbackColor,
    valid_from: node.valid_from ?? null,
    valid_until: node.valid_until ?? null,
    properties: node.properties ?? {},
    neighborCount,
    visibleNeighborCount: neighborCount,
    collapsedNeighborCount: 0,
    isNeighborhoodCollapsed: false,
    canCollapseNeighborhood: neighborCount > 8,
  };
}

function TimelineFallback({ min, max }: TemporalBounds) {
  return (
    <div
      style={{
        width: "100%",
        height: "90px",
        borderTop: "1px solid rgba(88, 166, 255, 0.2)",
        background: "rgba(1, 4, 9, 0.88)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 18px",
        color: "#8fa8c6",
        fontSize: 12,
        flexShrink: 0,
      }}
    >
      <span>Temporal scrubber</span>
      <span>{min || max ? "Preparing timeline runtime..." : "Temporal bounds loading..."}</span>
    </div>
  );
}

function NodePanel({
  node,
  predictions,
  predictionType,
  onPredictionTypeChange,
  onRunPredictions,
  pathTargetId,
  onPathTargetChange,
  onTracePath,
  pathResult,
  onDownloadProvenance,
}: {
  node: GraphSelectedNodeState | null;
  predictions: LinkPrediction[];
  predictionType: string;
  onPredictionTypeChange: (value: string) => void;
  onRunPredictions: () => void;
  pathTargetId: string;
  onPathTargetChange: (value: string) => void;
  onTracePath: () => void;
  pathResult: PathResponse | null;
  onDownloadProvenance: (format: "json" | "markdown") => void;
}) {
  if (!node) {
    return (
      <div style={{ padding: 32, textAlign: "center" }}>
        <p style={{ color: "#8b949e", fontSize: 14, margin: 0 }}>
          Search for a node or click one in the canvas to inspect its properties.
        </p>
      </div>
    );
  }

  const properties = node.properties ?? {};
  const attribution = sourceAttribution(properties);
  const accentColor = node.color || "#58a6ff";
  const propertyEntries = Object.entries(properties).filter(([key]) => !["x", "y", "valid_from", "valid_until", "content", "source", "source_url", "pmid", "pmids", "evidence", "provenance", "confidence"].includes(key));

  return (
    <aside style={{ padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ borderBottom: "1px solid rgba(88, 166, 255, 0.14)", paddingBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <span style={{ background: accentColor, boxShadow: `0 0 10px ${accentColor}`, width: 8, height: 8, borderRadius: "50%" }} />
          <span style={{ color: accentColor, fontSize: 12, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em" }}>{node.nodeType || "Entity"}</span>
        </div>
        <h3 style={{ margin: 0, color: "#fff", fontSize: 24, lineHeight: 1, fontWeight: 800, letterSpacing: "-0.04em", wordBreak: "break-word" }}>{node.label}</h3>
        <div style={{ color: "#8b949e", fontSize: 12, marginTop: 8 }}>{node.id}</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {node.valid_from || node.valid_until ? <span style={subtleChipStyle}>temporal</span> : null}
          <span style={subtleChipStyle}>{node.neighborCount} neighbors</span>
          {attribution.length ? <span style={subtleChipStyle}>{attribution.length} source fields</span> : null}
          {predictions.length ? <span style={subtleChipStyle}>{predictions.length} candidate links</span> : null}
        </div>
      </div>

      <section style={sectionStyle}>
        <div style={sectionTitleStyle}>Actions</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <button style={{ ...actionButtonStyle, width: "100%", justifyContent: "center" }} onClick={onRunPredictions}>Run Link Prediction</button>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button style={secondaryActionButtonStyle} onClick={() => onDownloadProvenance("json")}>Provenance JSON</button>
            <button style={secondaryActionButtonStyle} onClick={() => onDownloadProvenance("markdown")}>Provenance MD</button>
          </div>
        </div>
        <input value={predictionType} onChange={(event) => onPredictionTypeChange(event.target.value)} placeholder="Optional candidate type filter, e.g. disease" style={inputStyle} />
      </section>

      <section style={sectionStyle}>
        <div style={sectionTitleStyle}>Trace Path</div>
        <input value={pathTargetId} onChange={(event) => onPathTargetChange(event.target.value)} placeholder="Target node ID" style={inputStyle} />
        <button style={actionButtonStyle} onClick={onTracePath}>Trace Causal Path</button>
        {pathResult?.path?.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            {pathResult.path.map((step, index) => (
              <div key={`${step}-${index}`} style={pathStepStyle}>{index + 1}. {step}</div>
            ))}
            <div style={{ color: "#79c0ff", fontSize: 12, marginTop: 4 }}>total weight: {pathResult.total_weight.toFixed(3)}</div>
          </div>
        ) : (
          <div style={emptyTextStyle}>Choose a target or click a candidate prediction to prepare a path trace.</div>
        )}
      </section>

      <details style={collapseStyle} open={predictions.length > 0}>
        <summary style={summaryStyle}>Candidate Links</summary>
        <div style={{ padding: "0 14px 14px" }}>
          {predictions.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {predictions.map((prediction) => (
                <button key={`${prediction.target}-${prediction.type}`} style={predictionCardStyle} onClick={() => onPathTargetChange(prediction.target)}>
                  <div style={{ color: "#fff", fontWeight: 600 }}>{prediction.label || prediction.target}</div>
                  <div style={{ color: "#8b949e", fontSize: 12 }}>{prediction.type}</div>
                  <div style={{ color: "#58a6ff", fontSize: 12, marginTop: 4 }}>confidence {prediction.score.toFixed(3)}</div>
                </button>
              ))}
            </div>
          ) : (
            <div style={emptyTextStyle}>Run link prediction to surface likely next-hop relationships.</div>
          )}
        </div>
      </details>

      <details style={collapseStyle}>
        <summary style={summaryStyle}>Source Attribution</summary>
        <div style={{ padding: "0 14px 14px" }}>
          {attribution.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {attribution.map(({ key, value }) => (
                <div key={key} style={propertyCardStyle}>
                  <div style={{ color: "rgba(88, 166, 255, 0.7)", fontSize: 11, marginBottom: 4 }}>{key}</div>
                  <div style={{ color: "#e6edf3", fontSize: 13, wordBreak: "break-word" }}>{typeof value === "object" ? JSON.stringify(value) : String(value)}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={emptyTextStyle}>No explicit attribution metadata was found on this node.</div>
          )}
        </div>
      </details>

      <details style={collapseStyle}>
        <summary style={summaryStyle}>Properties</summary>
        <div style={{ padding: "0 14px 14px" }}>
          {propertyEntries.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {propertyEntries.map(([key, value]) => (
                <div key={key} style={propertyCardStyle}>
                  <div style={{ color: "rgba(88, 166, 255, 0.7)", fontSize: 11, marginBottom: 4 }}>{key}</div>
                  <div style={{ color: "#e6edf3", fontSize: 13, wordBreak: "break-word" }}>{typeof value === "object" ? JSON.stringify(value) : String(value)}</div>
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

export function GraphWorkspaceShell() {
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [selectedNodeState, setSelectedNodeState] = useState<GraphSelectedNodeState | null>(null);
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const [viewMode, setViewMode] = useState<GraphViewMode>("full");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState("");
  const [predictionType, setPredictionType] = useState("");
  const [predictions, setPredictions] = useState<LinkPrediction[]>([]);
  const [pathTargetId, setPathTargetId] = useState("");
  const [pathResult, setPathResult] = useState<PathResponse | null>(null);
  const [activeNodeCount, setActiveNodeCount] = useState<number | null>(null);
  const [temporalBounds, setTemporalBounds] = useState<TemporalBounds | null>(null);
  const [scrubberTime, setScrubberTime] = useState<Date | null>(null);
  const [loadingProgress, setLoadingProgress] = useState<GraphLoadProgress | null>(null);
  const [isGraphStageReady, setIsGraphStageReady] = useState(false);
  const [layoutStatus, setLayoutStatus] = useState<GraphLayoutStatus>({
    state: "idle",
    source: "runtime",
    hasCoordinates: false,
    layoutReady: false,
    displacement: null,
    elapsedMs: 0,
    stableSamples: 0,
  });

  const debouncedTime = useDebounce(scrubberTime, 150);
  const stageRef = useRef<GraphStageHandle>(null);
  const reload = useReloadGraphData();
  const { data: snapshot, isLoading, isFetching, isError, error } = useGraphData({ enabled: true, onProgress: setLoadingProgress });

  const handleSelectedNodeStateChange = useCallback((state: GraphSelectedNodeState | null) => {
    setSelectedNodeState(state);
  }, []);

  const handleLayoutRunningChange = useCallback((running: boolean) => {
    setIsLayoutRunning(running);
  }, []);

  const handleActiveNodeCountChange = useCallback((count: number | null) => {
    setActiveNodeCount(count);
  }, []);

  const handleProgressChange = useCallback((progress: GraphLoadProgress | null) => {
    setLoadingProgress(progress);
  }, []);

  const handleRuntimeReady = useCallback(() => {
    setIsGraphStageReady(true);
  }, []);

  const handleLayoutStatusChange = useCallback((status: GraphLayoutStatus) => {
    setLayoutStatus(status);
    if (status.layoutReady) {
      setLoadingProgress(null);
    }
  }, []);

  useEffect(() => {
    if (snapshot) {
      setIsGraphStageReady(false);
      setActiveNodeCount(null);
      setLayoutStatus({
        state: snapshot.summary.layoutReady ? "interactive" : "idle",
        source: snapshot.summary.layoutSource ?? "runtime",
        hasCoordinates: snapshot.summary.hasCoordinates ?? false,
        layoutReady: snapshot.summary.layoutReady ?? false,
        displacement: null,
        elapsedMs: 0,
        stableSamples: 0,
      });
    }
  }, [snapshot?.fetchedAt]);

  useEffect(() => {
    let cancelled = false;
    const loadBounds = async () => {
      try {
        const response = await fetch("/api/temporal/bounds");
        if (!response.ok || cancelled) return;
        const data: TemporalBounds = await response.json();
        if (!cancelled) setTemporalBounds(data);
      } catch {
        if (!cancelled) setTemporalBounds(null);
      }
    };
    void loadBounds();
    return () => {
      cancelled = true;
    };
  }, [snapshot?.summary.nodeCount, snapshot?.summary.edgeCount]);

  const neighborCountMap = useMemo(() => {
    const map = new Map<string, number>();
    if (!snapshot) return map;
    for (const node of snapshot.nodes) map.set(node.id, 0);
    for (const edge of snapshot.edges) {
      map.set(edge.source, (map.get(edge.source) ?? 0) + 1);
      map.set(edge.target, (map.get(edge.target) ?? 0) + 1);
    }
    return map;
  }, [snapshot]);

  const visibleSelectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    if (selectedNodeState?.id === selectedNodeId) return selectedNodeState;
    const snapshotNode = snapshot?.nodes.find((candidate) => candidate.id === selectedNodeId);
    if (snapshotNode) return toSelectedNodeState(snapshotNode, neighborCountMap.get(snapshotNode.id) ?? 0);
    const searchNode = searchResults.find((candidate) => candidate.node.id === selectedNodeId)?.node;
    return searchNode
      ? {
          id: searchNode.id,
          label: searchNode.content || searchNode.id,
          content: searchNode.content || searchNode.id,
          nodeType: searchNode.type,
          color: "#58a6ff",
          valid_from: null,
          valid_until: null,
          properties: searchNode.properties ?? {},
          neighborCount: 0,
          visibleNeighborCount: 0,
          collapsedNeighborCount: 0,
          isNeighborhoodCollapsed: false,
          canCollapseNeighborhood: false,
        }
      : null;
  }, [neighborCountMap, searchResults, selectedNodeId, selectedNodeState, snapshot]);

  const focusNode = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    setPathResult(null);

    if (!nodeId) {
      setSelectedNodeState(null);
      setPredictions([]);
      return;
    }

    setSearchResults([]);
    setIsLayoutRunning(false);
  }, []);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    setSearchError("");
    try {
      const response = await fetch("/api/graph/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery, limit: 8 }),
      });
      if (!response.ok) {
        throw new Error(`Search failed with status ${response.status}`);
      }

      const data = await response.json();
      setSearchResults(data.results || []);
      if (data.results?.length) {
        focusNode(data.results[0].node.id);
      }
    } catch (searchFetchError) {
      setSearchError(searchFetchError instanceof Error ? searchFetchError.message : "Search failed");
    }
  }, [focusNode, searchQuery]);

  const handleRunPredictions = useCallback(async () => {
    if (!selectedNodeId) return;

    try {
      const response = await fetch("/api/enrich/links", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: selectedNodeId,
          top_n: 6,
          candidate_type: predictionType || undefined,
          min_score: 0,
        }),
      });
      if (!response.ok) {
        throw new Error(`Link prediction failed with status ${response.status}`);
      }

      const data = await response.json();
      setPredictions(data.predictions || []);
    } catch (predictionError) {
      console.error("[GraphWorkspaceShell] prediction failed", predictionError);
      setPredictions([]);
    }
  }, [predictionType, selectedNodeId]);

  const handleTracePath = useCallback(async () => {
    if (!selectedNodeId || !pathTargetId.trim()) return;

    try {
      const pathParams = new URLSearchParams({
        source: selectedNodeId,
        target: pathTargetId.trim(),
        algorithm: "dijkstra",
      });
      const response = await fetch(
        `/api/graph/path?${pathParams.toString()}`,
      );
      if (!response.ok) {
        throw new Error(`Path lookup failed with status ${response.status}`);
      }

      const data: PathResponse = await response.json();
      setPathResult(data);
      if (data.path?.length) {
        const lastStep = data.path[data.path.length - 1];
        stageRef.current?.focusNode(lastStep);
      }
    } catch (pathError) {
      console.error("[GraphWorkspaceShell] path trace failed", pathError);
      setPathResult(null);
    }
  }, [pathTargetId, selectedNodeId]);

  const handleDownloadProvenance = useCallback(async (format: "json" | "markdown") => {
    if (!selectedNodeId) return;

    const suffix = format === "markdown" ? "markdown" : "json";
    const response = await fetch(`/api/provenance/report?node_id=${encodeURIComponent(selectedNodeId)}&format=${suffix}`);
    if (!response.ok) {
      throw new Error(`Provenance report failed with status ${response.status}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selectedNodeId}_provenance.${format === "markdown" ? "md" : "json"}`;
    document.body.appendChild(anchor);
    anchor.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(anchor);
  }, [selectedNodeId]);

  const searchSummary = useMemo(() => {
    if (!searchResults.length) return null;
    return `${searchResults.length} search result${searchResults.length === 1 ? "" : "s"}`;
  }, [searchResults.length]);

  const focusedSummary = useMemo(() => {
    if (!visibleSelectedNode) return null;
    if (viewMode === "focused") {
      const visibleNeighbors = Math.min(visibleSelectedNode.neighborCount, 16);
      return `${visibleNeighbors + 1} nodes in focused view`;
    }
    return `${visibleSelectedNode.neighborCount} direct neighbors highlighted`;
  }, [viewMode, visibleSelectedNode]);

  const requestViewMode = useCallback((nextViewMode: GraphViewMode) => {
    if (nextViewMode === "focused") {
      if (!selectedNodeId) {
        return;
      }
      setViewMode("focused");
      setIsLayoutRunning(false);
      return;
    }

    setViewMode("full");
  }, [selectedNodeId]);

  const showLoadingOverlay =
    isLoading
    || isFetching
    || !isGraphStageReady
    || (layoutStatus.source === "runtime" && !layoutStatus.layoutReady && !selectedNodeId && viewMode === "full");

  const layoutStatusLabel = useMemo(() => {
    if (layoutStatus.source === "provided" && layoutStatus.layoutReady) return "Persisted layout";
    if (layoutStatus.source === "carried" && layoutStatus.layoutReady) return "Preserved layout";
    if (layoutStatus.state === "bootstrapping") return "Bootstrapping layout";
    if (layoutStatus.state === "running") return "Stabilizing layout";
    if (layoutStatus.state === "failed") return "Layout timeout fallback";
    return null;
  }, [layoutStatus]);

  return (
    <div className="palantir-bg" style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <style>{HUD_CSS}</style>
      <div className="palantir-grid" />
      <div className="palantir-vignette" />

      <div style={{ flex: 1, position: "relative", zIndex: 3, minHeight: 0 }}>
        <Suspense fallback={null}>
          <GraphRuntimeStage
            ref={stageRef}
            snapshot={snapshot}
            selectedNodeId={selectedNodeId}
            activePath={pathResult?.path ?? []}
            onNodeSelect={focusNode}
            onSelectedNodeStateChange={handleSelectedNodeStateChange}
            isLayoutRunning={isLayoutRunning}
            onLayoutRunningChange={handleLayoutRunningChange}
            viewMode={viewMode}
            temporalTime={debouncedTime}
            onActiveNodeCountChange={handleActiveNodeCountChange}
            onProgressChange={handleProgressChange}
            onLayoutStatusChange={handleLayoutStatusChange}
            onRuntimeReady={handleRuntimeReady}
          />
        </Suspense>
        <GraphLoadingOverlay
          progress={loadingProgress}
          visible={showLoadingOverlay}
          showGraphBehind={Boolean(loadingProgress?.showGraphBehind || isGraphStageReady)}
        />
      </div>

      <Suspense fallback={<TimelineFallback min={temporalBounds?.min ?? null} max={temporalBounds?.max ?? null} />}>
        <TimelinePanel
          onTimeChange={setScrubberTime}
          minDate={temporalBounds?.min ?? undefined}
          maxDate={temporalBounds?.max ?? undefined}
        />
      </Suspense>

      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 10 }}>
        <div className="graph-shell-top">
          <section className="graph-status-card">
            <div className="graph-status-label">Graph Studio</div>
            <div className="graph-status-title">{visibleSelectedNode ? visibleSelectedNode.label : "Knowledge Explorer"}</div>
            <div className="graph-status-metrics">
              {showLoadingOverlay && loadingProgress ? <span style={{ ...metricPillStyle, color: "#a9ddff" }}>{getGraphLoadTitle(loadingProgress.phase)}</span> : null}
              {layoutStatusLabel ? <span style={{ ...metricPillStyle, color: "#a9ddff" }}>{layoutStatusLabel}</span> : null}
              {snapshot ? <span style={metricPillStyle}>{snapshot.summary.nodeCount.toLocaleString()} nodes · {snapshot.summary.edgeCount.toLocaleString()} edges</span> : null}
              {activeNodeCount !== null ? <span style={{ ...metricPillStyle, color: "#4fd49c", borderColor: "rgba(79, 212, 156, 0.22)" }}>{activeNodeCount.toLocaleString()} active</span> : null}
              {searchSummary ? <span style={metricPillStyle}>{searchSummary}</span> : null}
              {focusedSummary ? <span style={{ ...metricPillStyle, color: "#f2b66d", borderColor: "rgba(242, 182, 109, 0.24)" }}>{focusedSummary}</span> : null}
              {isError ? <span style={{ ...metricPillStyle, color: "#ff8f85", borderColor: "rgba(255, 123, 114, 0.22)" }}>{(error as Error).message}</span> : null}
            </div>
          </section>

          <section className="graph-command-card">
            <div className="graph-command-row">
              <div className="graph-toggle-cluster">
              {selectedNodeId ? (
                  <>
                    <button onClick={() => requestViewMode("focused")} style={{ ...actionButtonStyle, background: viewMode === "focused" ? "rgba(31, 111, 235, 0.38)" : actionButtonStyle.background, borderColor: viewMode === "focused" ? "rgba(127, 208, 255, 0.42)" : "rgba(88, 166, 255, 0.2)" }}>Focused View</button>
                    <button onClick={() => requestViewMode("full")} style={{ ...actionButtonStyle, background: viewMode === "full" ? "rgba(31, 111, 235, 0.38)" : actionButtonStyle.background, borderColor: viewMode === "full" ? "rgba(127, 208, 255, 0.42)" : "rgba(88, 166, 255, 0.2)" }}>Full Graph</button>
                  </>
                ) : (
                  <span style={{ color: "#7f95b3", fontSize: 12 }}>Select a node to switch graph views</span>
                )}
              </div>

              <div className="graph-action-cluster">
                <button onClick={() => setIsLayoutRunning((value) => !value)} style={secondaryActionButtonStyle} disabled={isLoading || isFetching}>
                  {isLayoutRunning ? "Pause Layout" : "Run Layout"}
                </button>
                <button onClick={() => { setIsGraphStageReady(false); reload(); }} style={secondaryActionButtonStyle} disabled={isLoading || isFetching}>
                  Reload
                </button>
              </div>
            </div>

            <div className="graph-command-row">
              <div className="graph-search-shell">
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      void handleSearch();
                    }
                  }}
                  placeholder="Search a node, e.g. Metformin"
                  style={{ ...inputStyle, minWidth: 260 }}
                  disabled={showLoadingOverlay && !selectedNodeId}
                />
                <button onClick={() => void handleSearch()} style={actionButtonStyle} disabled={showLoadingOverlay && !selectedNodeId}>Search</button>
              </div>
            </div>
          </section>
        </div>

        {searchError ? <div style={{ position: "absolute", top: 144, right: 34, color: "#ff7b72", fontSize: 12, pointerEvents: "auto" }}>{searchError}</div> : null}
        {searchResults.length ? (
          <div className="graph-search-results hud-scrollbar">
            <div className="graph-search-results-label">Search Results</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {searchResults.map((result) => (
                <button key={result.node.id} className="graph-search-result-card" onClick={() => focusNode(result.node.id)}>
                  <div style={{ color: "#fff", fontWeight: 700 }}>{result.node.content || result.node.id}</div>
                  <div style={{ color: "#8b949e", fontSize: 12 }}>{result.node.type}</div>
                  <div style={{ color: "#58a6ff", fontSize: 12, marginTop: 4 }}>score {result.score.toFixed(3)}</div>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="graph-inspector hud-scrollbar" data-open={selectedNodeId ? "true" : "false"}>
          <NodePanel
            node={visibleSelectedNode}
            predictions={predictions}
            predictionType={predictionType}
            onPredictionTypeChange={setPredictionType}
            onRunPredictions={() => void handleRunPredictions()}
            pathTargetId={pathTargetId}
            onPathTargetChange={setPathTargetId}
            onTracePath={() => void handleTracePath()}
            pathResult={pathResult}
            onDownloadProvenance={(format) => void handleDownloadProvenance(format)}
          />
        </div>
      </div>
    </div>
  );
}

const metricPillStyle: CSSProperties = {
  background: "rgba(88, 166, 255, 0.08)",
  color: "#8ed3ff",
  padding: "6px 11px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 700,
  border: "1px solid rgba(88, 166, 255, 0.14)",
};

const sectionStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 10,
  padding: 14,
  background: "linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.01))",
  border: "1px solid rgba(255, 255, 255, 0.06)",
  borderRadius: 16,
};

const sectionTitleStyle: CSSProperties = {
  color: "#8fa8c6",
  fontSize: 11,
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const inputStyle: CSSProperties = {
  width: "100%",
  background: "rgba(0, 0, 0, 0.24)",
  border: "1px solid rgba(88, 166, 255, 0.14)",
  color: "#fff",
  borderRadius: 12,
  padding: "10px 12px",
  fontSize: 13,
};

const actionButtonStyle: CSSProperties = {
  background: "linear-gradient(180deg, rgba(53, 130, 245, 0.28), rgba(25, 88, 185, 0.18))",
  color: "#fff",
  border: "1px solid rgba(88, 166, 255, 0.2)",
  borderRadius: 12,
  padding: "10px 13px",
  cursor: "pointer",
  fontWeight: 700,
  fontSize: 12,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)",
};

const secondaryActionButtonStyle: CSSProperties = {
  ...actionButtonStyle,
  background: "rgba(255, 255, 255, 0.035)",
  border: "1px solid rgba(255, 255, 255, 0.06)",
  color: "#d6e5f8",
  fontWeight: 500,
};

const predictionCardStyle: CSSProperties = {
  textAlign: "left",
  padding: 12,
  background: "rgba(88, 166, 255, 0.06)",
  border: "1px solid rgba(88, 166, 255, 0.1)",
  borderRadius: 14,
  cursor: "pointer",
};

const pathStepStyle: CSSProperties = {
  color: "#e6edf3",
  fontSize: 13,
  padding: "8px 10px",
  background: "rgba(255, 255, 255, 0.03)",
  borderRadius: 8,
};

const propertyCardStyle: CSSProperties = {
  background: "rgba(0, 0, 0, 0.18)",
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid rgba(255, 255, 255, 0.05)",
};

const emptyTextStyle: CSSProperties = {
  color: "#8b949e",
  fontSize: 12,
  lineHeight: 1.5,
};

const subtleChipStyle: CSSProperties = {
  background: "rgba(255, 255, 255, 0.035)",
  color: "#9fb6d2",
  padding: "5px 9px",
  borderRadius: 999,
  fontSize: 11,
  border: "1px solid rgba(255, 255, 255, 0.06)",
};

const collapseStyle: CSSProperties = {
  border: "1px solid rgba(255, 255, 255, 0.05)",
  borderRadius: 14,
  background: "rgba(0, 0, 0, 0.14)",
  overflow: "hidden",
};

const summaryStyle: CSSProperties = {
  cursor: "pointer",
  listStyle: "none",
  padding: "12px 14px",
  color: "#c6d4e3",
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
};
