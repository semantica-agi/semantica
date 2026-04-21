import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type Graph from "graphology";
import { batchMergeEdges, batchMergeNodes, graph } from "../../store/graphStore";
import { logEvent } from "../../store/registryStore";
import type { EdgeAttributes, NodeAttributes } from "../../store/graphStore";
import { curveGroupForPair } from "../../store/edgePairKeys.js";
import { InspectorPanel, MetricChip, SurfaceCard } from "../../ui/primitives";
import { lazy, Suspense } from "react";
import { SigmaSceneAdapter } from "./SigmaSceneAdapter";
import { useLoadGraph, useReloadGraph } from "./useLoadGraph";
import { GraphLoadingOverlay } from "./GraphLoadingOverlay";
import { createGraphLoadProgress, getGraphLoadTitle } from "./graphLoading";
import { GRAPH_THEME, withAlpha } from "./graphTheme";
import { resolveDisplayGraph, resolveDisplayStateSnapshot } from "./graphSceneState";
import {
  type GraphPlugin,
  type GraphPluginActionRequest,
  type GraphPluginContext,
  type GraphPluginOverlayDescriptor,
  type GraphPluginPanelDescriptor,
  type GraphPluginToolbarItem,
} from "./plugins";
import type { LinkPrediction, PathResponse } from "./GraphInspectorPanel";
import type { GraphSceneHandle, GraphSceneRuntime } from "./scene";
import type {
  GraphAnalyticsSnapshot,
  GraphDisplayStateSnapshot,
  GraphDiagnosticsSnapshot,
  GraphEffectToggle,
  GraphEffectsState,
  GraphInteractionState,
  GraphLoadProgress,
  GraphLoadSummary,
  GraphSelectedEdgeState,
  GraphSelectedNodeState,
  GraphTemporalState,
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

type TemporalBounds = {
  min?: string | null;
  max?: string | null;
};

type ExploreLayoutState = {
  showInspector: boolean;
  showPluginDock: boolean;
};

type GraphToolbarItem = {
  id: string;
  label: string;
  title?: string;
  active?: boolean;
  disabled?: boolean;
  tone?: "primary" | "secondary";
  onClick: () => void;
};

type GraphToolbarGroup = {
  id: string;
  items: GraphToolbarItem[];
};

type LazyPluginRegistryEntry = {
  id: string;
  panelId: string;
  label: string;
  title: string;
  order: number;
  load: () => Promise<GraphPlugin>;
  shouldLoad: (context: {
    panelState: Record<string, boolean>;
    temporalState: GraphTemporalState | null;
  }) => boolean;
};

const PROVENANCE_KEYS = ["source", "source_url", "pmid", "pmids", "evidence", "provenance", "confidence"] as const;
const DEFAULT_EFFECTS_STATE: GraphEffectsState = {
  pathPulseEnabled: false,
  pathFlowEnabled: false,
  lensEnabled: false,
  temporalEmphasisEnabled: false,
  semanticRegionsEnabled: false,
  contoursEnabled: false,
  pathfindingEnabled: false,
  communitiesEnabled: false,
  centralityEnabled: false,
  legendEnabled: false,
  diagnosticsEnabled: false,
  lensMode: "neighborhood",
  effectQuality: "bounded",
};
const LazyTimelinePanel = lazy(() => import("./TimelinePanel").then((module) => ({ default: module.TimelinePanel })));
const LazyGraphInspectorPanel = lazy(() => import("./GraphInspectorPanel").then((module) => ({ default: module.GraphInspectorPanel })));

const loadExplorationEffectsPlugin = () => import("./plugins/explorationEffectsPluginPhaseC").then((module) => module.explorationEffectsPluginPhaseC);
const loadNeighborhoodPanelPlugin = () => import("./plugins/neighborhoodPanelPlugin").then((module) => module.neighborhoodPanelPlugin);
const loadTemporalOverlayPlugin = () => import("./plugins/temporalOverlayPlugin").then((module) => module.temporalOverlayPlugin);
const EMPTY_PATH: string[] = [];
const DEBUG_GRAPH_WORKSPACE = import.meta.env.DEV;

function debugGraphWorkspace(message: string, payload?: Record<string, unknown>) {
  if (!DEBUG_GRAPH_WORKSPACE) {
    return;
  }
  console.debug(`[GraphWorkspace] ${message}`, payload ?? {});
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timeout);
  }, [delay, value]);
  return debouncedValue;
}

const HUD_CSS = `
  .palantir-bg {
    background:
      radial-gradient(circle at top, rgba(77, 157, 255, 0.08), transparent 22%),
      linear-gradient(180deg, #060b17 0%, #02060d 100%);
  }
  .palantir-grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(88, 166, 255, 0.038) 1px, transparent 1px),
      linear-gradient(90deg, rgba(88, 166, 255, 0.038) 1px, transparent 1px);
    background-size: 42px 42px;
    pointer-events: none;
    z-index: 1;
  }
  .palantir-vignette {
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, transparent 34%, rgba(1, 4, 10, 0.78) 100%);
    pointer-events: none;
    z-index: 2;
  }
  .glass-header {
    background: linear-gradient(180deg, rgba(7, 14, 25, 0.88) 0%, rgba(10, 18, 31, 0.62) 100%);
    border-bottom: 1px solid rgba(112, 196, 255, 0.1);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }
  .glass-hud {
    background: linear-gradient(135deg, rgba(8, 15, 27, 0.76), rgba(10, 19, 32, 0.58));
    backdrop-filter: blur(14px) saturate(1.08);
    -webkit-backdrop-filter: blur(14px) saturate(1.08);
    border-left: 1px solid rgba(112, 196, 255, 0.14);
    box-shadow: -10px 0 28px rgba(0, 0, 0, 0.34), inset 1px 0 0 rgba(255, 255, 255, 0.04);
  }
  .hud-scrollbar::-webkit-scrollbar { width: 6px; }
  .hud-scrollbar::-webkit-scrollbar-track { background: transparent; }
  .hud-scrollbar::-webkit-scrollbar-thumb { background: rgba(88, 166, 255, 0.25); border-radius: 6px; }
  .node-panel-collapse {
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    background: rgba(0, 0, 0, 0.14);
    overflow: hidden;
  }
  .node-panel-collapse + .node-panel-collapse {
    margin-top: 12px;
  }
  .node-panel-summary {
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 14px;
    color: #c6d4e3;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .node-panel-summary::-webkit-details-marker {
    display: none;
  }
  .node-panel-summary::after {
    content: "+";
    color: rgba(127, 208, 255, 0.8);
    font-size: 16px;
    line-height: 1;
  }
  .node-panel-collapse[open] .node-panel-summary::after {
    content: "−";
  }
  .node-panel-body {
    padding: 0 14px 14px;
  }
  .graph-loading-overlay {
    position: absolute;
    inset: 0;
    z-index: 9;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
  }
  .graph-loading-card {
    width: min(460px, calc(100% - 48px));
    border-radius: 20px;
    padding: 22px 22px 18px;
    background: linear-gradient(135deg, rgba(7, 17, 31, 0.9), rgba(14, 28, 48, 0.78));
    border: 1px solid rgba(127, 208, 255, 0.16);
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255,255,255,0.04);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
  }
  .graph-loading-dots {
    display: inline-flex;
    gap: 8px;
    align-items: center;
  }
  .graph-loading-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(127, 208, 255, 0.96), rgba(242, 182, 109, 0.96));
    box-shadow: 0 0 18px rgba(127, 208, 255, 0.35);
    animation: sem-loader-pulse 1.2s ease-in-out infinite;
  }
  .graph-loading-dot:nth-child(2) {
    animation-delay: 0.14s;
  }
  .graph-loading-dot:nth-child(3) {
    animation-delay: 0.28s;
  }
  @keyframes sem-loader-pulse {
    0%, 100% {
      transform: translateY(0) scale(0.92);
      opacity: 0.55;
    }
    50% {
      transform: translateY(-4px) scale(1.08);
      opacity: 1;
    }
  }
  .graph-loading-bar {
    width: 100%;
    height: 10px;
    border-radius: 999px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(127, 208, 255, 0.1);
  }
  .graph-loading-bar > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(74, 163, 255, 0.9), rgba(127, 208, 255, 0.95), rgba(242, 182, 109, 0.92));
    box-shadow: 0 0 28px rgba(74, 163, 255, 0.3);
    transition: width 180ms ease;
  }
  .explore-shell {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .explore-command-deck {
    position: relative;
    z-index: 3;
  }
  .explore-command-grid {
    display: grid;
    grid-template-columns: minmax(260px, 0.9fr) minmax(0, 1.4fr);
    gap: 16px;
  }
  .explore-main-grid {
    position: relative;
    z-index: 3;
    min-height: 0;
    flex: 1;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(340px, 380px);
    gap: 12px;
  }
  .explore-scene-stack {
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .explore-scene-card {
    min-height: 0;
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .explore-scene-shell {
    position: relative;
    min-height: 0;
    flex: 1;
    overflow: hidden;
    border-radius: 20px 20px 0 0;
  }
  .explore-scene-stage {
    position: relative;
    z-index: 3;
    width: 100%;
    height: 100%;
  }
  .explore-scene-footer {
    position: relative;
    z-index: 3;
    border-top: 1px solid rgba(112, 196, 255, 0.1);
    background: linear-gradient(180deg, rgba(5, 11, 20, 0.94), rgba(5, 11, 20, 0.82));
  }
  .explore-plugin-dock {
    position: relative;
    z-index: 3;
  }
  .explore-plugin-dock-tabs {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .explore-plugin-dock-tab {
    border: 1px solid rgba(127, 208, 255, 0.14);
    background: rgba(255, 255, 255, 0.03);
    color: #a9bfd7;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
  }
  .explore-plugin-dock-tab[data-active="true"] {
    color: #eef6ff;
    background: rgba(74, 163, 255, 0.16);
    border-color: rgba(127, 208, 255, 0.28);
  }
  .explore-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }
  .explore-toolbar-groups {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    flex: 1;
    justify-content: flex-end;
  }
  .explore-toolbar-group {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 3px;
    border-radius: 14px;
    border: 1px solid rgba(127, 208, 255, 0.08);
    background: rgba(255, 255, 255, 0.02);
  }
  .explore-search-results {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 260px;
    overflow-y: auto;
    padding-right: 4px;
  }
  .explore-inspector-shell {
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .explore-inspector-card {
    min-height: 0;
    flex: 1;
    overflow: hidden;
  }
  .explore-inspector-scroll {
    height: 100%;
    overflow-y: auto;
  }
  @media (max-width: 1260px) {
    .explore-main-grid {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 980px) {
    .explore-shell {
      padding: 10px;
      gap: 10px;
    }
    .explore-command-grid {
      grid-template-columns: 1fr;
    }
  }
`;

function getProvenanceCount(properties: Record<string, unknown>) {
  return PROVENANCE_KEYS.reduce(
    (count, key) => (properties[key] !== undefined && properties[key] !== null ? count + 1 : count),
    0,
  );
}

function buildRealtimeNodeAttributes(payload: {
  id: string;
  type?: string;
  properties?: Record<string, unknown>;
}): NodeAttributes {
  const properties = payload.properties || {};
  const label = String(properties.content || payload.id);
  const baseColor = GRAPH_THEME.palette.accent.path;
  const hasTemporalBounds = Boolean(properties.valid_from || properties.valid_until);
  const provenanceCount = getProvenanceCount(properties);

  return {
    label,
    x: Number(properties.x ?? Math.random() * 1000 - 500),
    y: Number(properties.y ?? Math.random() * 1000 - 500),
    nodeType: payload.type || "inferred",
    content: label,
    valid_from: (properties.valid_from as string | null | undefined) ?? null,
    valid_until: (properties.valid_until as string | null | undefined) ?? null,
    properties,
    size: 8,
    baseSize: 8,
    semanticGroup: payload.type || "inferred",
    color: baseColor,
    baseColor,
    mutedColor: withAlpha(baseColor, GRAPH_THEME.nodes.mutedAlpha),
    glowColor: withAlpha(baseColor, 0.36),
    visualPriority: 0.82,
    labelPriority: 0.82,
    strokeColor: GRAPH_THEME.palette.background.nodeBorder,
    borderColor: GRAPH_THEME.palette.background.nodeBorder,
    borderSize: 0.85,
    nodeVariant: "inferred",
    nodeShapeVariant: "inferred",
    badgeKind: hasTemporalBounds ? "temporal" : provenanceCount > 0 ? "provenance" : "inferred",
    badgeCount: provenanceCount || undefined,
    ringColor: GRAPH_THEME.nodes.selectedRing.color,
    haloColor: withAlpha(baseColor, 0.42),
    labelVisibilityPolicy: "local",
  };
}

function buildRealtimeEdgeAttributes(payload: {
  id: string;
  familyId?: string;
  source_id: string;
  target_id: string;
  type?: string;
  weight?: number;
  properties?: Record<string, unknown>;
}): EdgeAttributes {
  const properties = payload.properties || {};
  const isInferred = Boolean(properties.inferred);
  const isBidirectional = graph.hasDirectedEdge(payload.target_id, payload.source_id);
  const baseColor = isInferred ? GRAPH_THEME.palette.accent.path : GRAPH_THEME.palette.muted.edgeStructure;

  return {
    edgeId: payload.id,
    familyId: payload.familyId || payload.id,
    sourceId: payload.source_id,
    targetId: payload.target_id,
    weight: Number(payload.weight ?? 1),
    edgeType: payload.type || "related_to",
    properties,
    size: 1,
    baseSize: 1,
    color: baseColor,
    baseColor,
    mutedColor: GRAPH_THEME.palette.muted.edgeOverview,
    visualPriority: isInferred ? 0.95 : 0.5,
    isBidirectional,
    edgeFamily: isInferred ? "path" : isBidirectional ? "bidirectional" : "line",
    curveGroup: isBidirectional ? curveGroupForPair(payload.source_id, payload.target_id) : null,
    type: "line",
    edgeVariant: isInferred ? "pathSignal" : isBidirectional ? "bidirectionalCurve" : "directional",
    arrowVisibilityPolicy: isInferred ? "always" : "contextual",
    relationshipStrength: isInferred ? 0.95 : 0.52,
    isParallelPair: false,
    parallelIndex: 0,
    parallelCount: 1,
    familySize: 1,
  };
}

function buildSelectedNodeState(
  nodeId: string,
  displayState: GraphDisplayStateSnapshot,
): GraphSelectedNodeState | null {
  if (!nodeId || !graph.hasNode(nodeId)) {
    return null;
  }

  const attributes = graph.getNodeAttributes(nodeId) as {
    label?: string;
    content?: string;
    nodeType?: string;
    color?: string;
    valid_from?: string | null;
    valid_until?: string | null;
    properties?: Record<string, unknown>;
  };

  return {
    id: nodeId,
    label: String(attributes.label ?? nodeId),
    content: String(attributes.content ?? attributes.label ?? nodeId),
    nodeType: String(attributes.nodeType ?? "Entity"),
    color: typeof attributes.color === "string" ? attributes.color : undefined,
    valid_from: attributes.valid_from ?? null,
    valid_until: attributes.valid_until ?? null,
    properties: attributes.properties ?? {},
    neighborCount: graph.neighbors(nodeId).length,
    visibleNeighborCount: displayState.selectedVisibleNeighborIds.length,
    collapsedNeighborCount: displayState.selectedCollapsedNeighborIds.length,
    isNeighborhoodCollapsed: displayState.selectedCollapsedNeighborIds.length > 0,
    canCollapseNeighborhood: graph.neighbors(nodeId).length > 8,
  };
}

function buildSelectedEdgeState(
  edgeId: string,
  displayGraph: typeof graph | Graph<NodeAttributes, EdgeAttributes>,
): GraphSelectedEdgeState | null {
  if (!edgeId || !displayGraph.hasEdge(edgeId)) {
    return null;
  }

  const [displaySourceId, displayTargetId] = displayGraph.extremities(edgeId);
  const attributes = displayGraph.getEdgeAttributes(edgeId) as {
    edgeType?: string;
    weight?: number;
    properties?: Record<string, unknown>;
    familyId?: string;
    rawEdgeIds?: string[];
    isAggregated?: boolean;
    aggregateCount?: number;
    bundleKind?: "parallel" | "bidirectional" | "community";
    dominantEdgeType?: string;
    representativeWeight?: number;
  };
  const rawEdgeIds = attributes.rawEdgeIds?.length ? attributes.rawEdgeIds.map((rawEdgeId) => String(rawEdgeId)) : [edgeId];
  const primaryRawEdgeId = rawEdgeIds.find((rawEdgeId) => graph.hasEdge(rawEdgeId)) ?? rawEdgeIds[0];
  let sourceId = displaySourceId;
  let targetId = displayTargetId;
  if (primaryRawEdgeId && graph.hasEdge(primaryRawEdgeId)) {
    [sourceId, targetId] = graph.extremities(primaryRawEdgeId);
  }
  const sourceAttributes = graph.hasNode(sourceId)
    ? (graph.getNodeAttributes(sourceId) as { label?: string; content?: string })
    : ({ label: displaySourceId } as { label?: string; content?: string });
  const targetAttributes = graph.hasNode(targetId)
    ? (graph.getNodeAttributes(targetId) as { label?: string; content?: string })
    : ({ label: displayTargetId } as { label?: string; content?: string });
  const properties = attributes.properties ?? {};
  const familyId = String(attributes.familyId || edgeId);
  let familySize = 0;
  let siblingCount = 0;
  rawEdgeIds.forEach((rawEdgeId) => {
    if (!graph.hasEdge(rawEdgeId)) {
      return;
    }
    const candidateAttrs = graph.getEdgeAttributes(rawEdgeId) as { familyId?: string };
    const [candidateSource, candidateTarget] = graph.extremities(rawEdgeId);
    if (String(candidateAttrs.familyId || rawEdgeId) === familyId) {
      familySize += 1;
    }
    if (candidateSource === sourceId && candidateTarget === targetId) {
      siblingCount += 1;
    }
  });

  if (attributes.isAggregated) {
    siblingCount = rawEdgeIds.filter((rawEdgeId) => graph.hasEdge(rawEdgeId)).length;
    familySize = Math.max(familySize, siblingCount);
  }

  return {
    id: edgeId,
    familyId,
    sourceId,
    sourceLabel: String(sourceAttributes.label ?? sourceAttributes.content ?? sourceId),
    targetId,
    targetLabel: String(targetAttributes.label ?? targetAttributes.content ?? targetId),
    edgeType: String(attributes.edgeType ?? "related_to"),
    weight: Number(attributes.weight ?? 1),
    properties,
    provenanceCount: getProvenanceCount(properties),
    familySize,
    siblingCount,
    isAggregated: Boolean(attributes.isAggregated),
    aggregateCount: Number(attributes.aggregateCount ?? rawEdgeIds.length),
    rawEdgeIds,
    bundleKind: attributes.bundleKind ?? null,
    dominantEdgeType: attributes.dominantEdgeType ?? null,
    representativeWeight: Number(attributes.representativeWeight ?? attributes.weight ?? 1),
  };
}

function collectPluginPanels(
  plugins: GraphPlugin[],
  context: GraphPluginContext,
): GraphPluginPanelDescriptor[] {
  const panels: GraphPluginPanelDescriptor[] = [];

  for (const plugin of plugins) {
    try {
      const result = plugin.renderPanel?.(context);
      if (!result) {
        continue;
      }
      if (Array.isArray(result)) {
        panels.push(...result);
      } else {
        panels.push(result);
      }
    } catch (error) {
      console.error(`[GraphPlugin:${plugin.id}] panel render failed`, error);
    }
  }

  return panels.sort((left, right) => (left.order ?? 0) - (right.order ?? 0));
}

function collectPluginOverlays(
  plugins: GraphPlugin[],
  context: GraphPluginContext,
): GraphPluginOverlayDescriptor[] {
  const overlays: GraphPluginOverlayDescriptor[] = [];

  for (const plugin of plugins) {
    try {
      const result = plugin.renderOverlay?.(context);
      if (!result) {
        continue;
      }
      if (Array.isArray(result)) {
        overlays.push(...result);
      } else {
        overlays.push(result);
      }
    } catch (error) {
      console.error(`[GraphPlugin:${plugin.id}] overlay render failed`, error);
    }
  }

  return overlays.sort((left, right) => {
    if ((left.layer ?? 0) !== (right.layer ?? 0)) {
      return (left.layer ?? 0) - (right.layer ?? 0);
    }
    return (left.order ?? 0) - (right.order ?? 0);
  });
}

export function GraphWorkspace() {
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [selectedEdgeId, setSelectedEdgeId] = useState("");
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const [graphReady, setGraphReady] = useState(false);
  const [graphVersion, setGraphVersion] = useState(0);
  const [viewMode, setViewMode] = useState<GraphViewMode>("full");
  const [aggregationEnabled] = useState(true);
  const [collapsedNeighborhoodNodeIds, setCollapsedNeighborhoodNodeIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState("");
  const [predictionType, setPredictionType] = useState("");
  const [isRunningPredictions, setIsRunningPredictions] = useState(false);
  const [predictions, setPredictions] = useState<LinkPrediction[]>([]);
  const [pathTargetId, setPathTargetId] = useState("");
  const [pathResult, setPathResult] = useState<PathResponse | null>(null);
  const [activeNodeCount, setActiveNodeCount] = useState<number | null>(null);
  const [temporalBounds, setTemporalBounds] = useState<TemporalBounds | null>(null);
  const [scrubberTime, setScrubberTime] = useState<Date | null>(null);
  const [loadingProgress, setLoadingProgress] = useState<GraphLoadProgress | null>(null);
  const [pluginPanelState, setPluginPanelState] = useState<Record<string, boolean>>({
    "effects-panel": false,
    "neighborhood-panel": false,
    "temporal-panel": false,
  });
  const [activeDockPanelId, setActiveDockPanelId] = useState<string | null>(null);
  const [pluginRuntimeVersion, setPluginRuntimeVersion] = useState(0);
  const [effectsState, setEffectsState] = useState<GraphEffectsState>(DEFAULT_EFFECTS_STATE);
  const [graphDiagnosticsState, setGraphDiagnosticsState] = useState<GraphDiagnosticsSnapshot["effectAvailability"] | null>(null);
  const [graphAnalyticsState, setGraphAnalyticsState] = useState<GraphAnalyticsSnapshot | null>(null);
  const [loadedPlugins, setLoadedPlugins] = useState<Record<string, GraphPlugin>>({});

  const debouncedTime = useDebounce(scrubberTime, 150);
  const prevActiveIdsRef = useRef<Set<string>>(new Set());
  const sceneRef = useRef<GraphSceneHandle>(null);
  const pluginRuntimeRef = useRef<GraphSceneRuntime | null>(null);
  const settlingOverlayTimeoutRef = useRef<number | null>(null);
  const pluginInteractionStateRef = useRef<GraphInteractionState>({
    hoveredNodeId: null,
    selectedNodeId: "",
    selectedEdgeId: "",
    focusedNodeId: "",
    activePath: [],
    activePathEdgeIds: [],
    viewMode: "full",
    zoomTier: "overview",
    isLayoutRunning: false,
  });
  const reload = useReloadGraph();

  const handleLoadProgress = useCallback((progress: GraphLoadProgress) => {
    setLoadingProgress(progress);
    if (progress.phase !== "ready" && progress.phase !== "stabilizing_layout") {
      setGraphReady(false);
    }
  }, []);

  const { data: summary, isLoading, isFetching } = useLoadGraph({
    enabled: true,
    onGraphReady: (graphSummary) => {
      setGraphReady(true);
      setGraphVersion((current) => current + 1);
      setIsLayoutRunning(!graphSummary.layoutReady);
      if (settlingOverlayTimeoutRef.current !== null) {
        window.clearTimeout(settlingOverlayTimeoutRef.current);
        settlingOverlayTimeoutRef.current = null;
      }

      if (graphSummary.layoutReady) {
        setLoadingProgress(null);
        return;
      }

      setLoadingProgress(createGraphLoadProgress({
        phase: "stabilizing_layout",
        progressKind: "indeterminate",
        nodesLoaded: graphSummary.nodeCount,
        nodesTotal: graphSummary.nodeCount,
        edgesLoaded: graphSummary.edgeCount,
        edgesTotal: graphSummary.edgeCount,
        message: "Settling runtime layout",
        showGraphBehind: true,
        layoutSource: graphSummary.layoutSource,
        layoutState: "bootstrapping",
      }));
      settlingOverlayTimeoutRef.current = window.setTimeout(() => {
        setLoadingProgress((current) => (current?.phase === "stabilizing_layout" ? null : current));
        settlingOverlayTimeoutRef.current = null;
      }, 900);
    },
    onProgress: handleLoadProgress,
  });

  useEffect(() => {
    return () => {
      if (settlingOverlayTimeoutRef.current !== null) {
        window.clearTimeout(settlingOverlayTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadBounds = async () => {
      try {
        const response = await fetch("/api/temporal/bounds");
        if (!response.ok || cancelled) return;
        const data: TemporalBounds = await response.json();
        if (!cancelled) {
          setTemporalBounds(data);
        }
      } catch {
        if (!cancelled) {
          setTemporalBounds(null);
        }
      }
    };
    loadBounds();
    return () => {
      cancelled = true;
    };
  }, [summary?.nodeCount, summary?.edgeCount]);

  useEffect(() => {
    if (!debouncedTime || isLoading) return;
    let cancelled = false;

    const applySnapshot = async () => {
      try {
        const at = debouncedTime.toISOString();
        const response = await fetch(`/api/temporal/snapshot?at=${encodeURIComponent(at)}`);
        if (!response.ok || cancelled) return;

        const data: { active_node_ids: string[]; active_node_count: number } = await response.json();
        if (cancelled) return;

        const nextActiveIds = new Set(data.active_node_ids);
        requestAnimationFrame(() => {
          if (cancelled) return;
          const previous = prevActiveIdsRef.current;
          previous.forEach((id) => {
            if (!nextActiveIds.has(id) && graph.hasNode(id)) {
              graph.setNodeAttribute(id, "hidden", true);
            }
          });
          nextActiveIds.forEach((id) => {
            if (graph.hasNode(id)) {
              graph.setNodeAttribute(id, "hidden", false);
            }
          });
          prevActiveIdsRef.current = nextActiveIds;
          setActiveNodeCount(data.active_node_count);
          setGraphVersion((current) => current + 1);
          sceneRef.current?.getRuntime()?.requestRender();
        });
      } catch (fetchError) {
        if (!cancelled) {
          console.error("[Temporal] Snapshot fetch failed", fetchError);
        }
      }
    };

    applySnapshot();
    return () => {
      cancelled = true;
    };
  }, [debouncedTime, isLoading]);

  const focusNode = useCallback((nodeId: string) => {
    const currentDisplayGraph = pluginRuntimeRef.current?.displayGraph ?? graph;
    if (viewMode === "grouped" && currentDisplayGraph.hasNode(nodeId)) {
      const displayAttrs = currentDisplayGraph.getNodeAttributes(nodeId) as NodeAttributes;
      const communityGroup = displayAttrs.properties?.__communityGroup as
        | {
            anchorNodeId?: string | null;
            sampleNodeIds?: string[];
          }
        | undefined;
      const anchorNodeId = communityGroup?.anchorNodeId || communityGroup?.sampleNodeIds?.[0] || "";
      if (anchorNodeId && graph.hasNode(anchorNodeId)) {
        setViewMode("focused");
        setSelectedNodeId(anchorNodeId);
        setSelectedEdgeId("");
        setPathResult(null);
        setSearchResults([]);
        setSearchError("");
        setIsLayoutRunning(false);
        return;
      }
    }

    setSelectedNodeId(nodeId);
    setSelectedEdgeId("");
    setPathResult(null);
    setSearchResults([]);
    setSearchError("");
    if (nodeId && viewMode === "focused") {
      setIsLayoutRunning(false);
    }
  }, [viewMode]);

  const handleEdgeSelect = useCallback((edgeId: string) => {
    setSelectedEdgeId(edgeId);
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
    } catch (searchFetchError) {
      setSearchError(searchFetchError instanceof Error ? searchFetchError.message : "Search failed");
    }
  }, [searchQuery]);

  const handleRunPredictions = useCallback(async () => {
    if (!selectedNodeId) return;
    setIsRunningPredictions(true);
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
      console.error("[GraphWorkspace] prediction failed", predictionError);
      setPredictions([]);
    } finally {
      setIsRunningPredictions(false);
    }
  }, [predictionType, selectedNodeId]);

  const handleTracePath = useCallback(async () => {
    if (!selectedNodeId || !pathTargetId.trim()) return;
    try {
      const response = await fetch(
        `/api/graph/node/${encodeURIComponent(selectedNodeId)}/path?target=${encodeURIComponent(pathTargetId.trim())}&algorithm=dijkstra`
      );
      if (!response.ok) {
        throw new Error(`Path lookup failed with status ${response.status}`);
      }
      const data: PathResponse = await response.json();
      setPathResult(data);
      if (data.path?.length) {
        const lastStep = data.path[data.path.length - 1];
        if (graph.hasNode(lastStep)) {
          sceneRef.current?.focusNode(lastStep);
        }
      }
    } catch (pathError) {
      console.error("[GraphWorkspace] path trace failed", pathError);
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

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/graph-updates`);

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.event === "connection_ack") {
          return;
        }
        if (message.event !== "graph_mutation") {
          return;
        }
        const eventType = message.data?.event_type;
        const payload = message.data?.payload;
        if (eventType === "ADD_NODE" && payload?.id) {
          batchMergeNodes([
            {
              id: payload.id,
              attributes: buildRealtimeNodeAttributes(payload),
            },
          ]);
          logEvent("add-node", `Added node ${payload.label ?? payload.id}${payload.nodeType ? ` (${payload.nodeType})` : ""} via realtime ws`, { nodeId: payload.id, nodeType: payload.nodeType });
          setGraphVersion((current) => current + 1);
          sceneRef.current?.getRuntime()?.requestRender();
        }
        if (eventType === "ADD_EDGE") {
          batchMergeEdges([
            {
              id: String(payload.id),
              familyId: payload.familyId ? String(payload.familyId) : String(payload.id),
              source: payload.source_id,
              target: payload.target_id,
              attributes: buildRealtimeEdgeAttributes(payload),
            },
          ]);
          logEvent("add-edge", `Added edge ${payload.edgeType ?? payload.id} (${payload.source_id} → ${payload.target_id}) via realtime ws`, { edgeId: payload.id, edgeType: payload.edgeType, source: payload.source_id, target: payload.target_id });
          setGraphVersion((current) => current + 1);
          sceneRef.current?.getRuntime()?.requestRender();
        }
      } catch (socketError) {
        console.error("[GraphWorkspace] websocket update failed", socketError);
      }
    };

    return () => {
      socket.close();
    };
  }, []);

  useEffect(() => {
    setCollapsedNeighborhoodNodeIds([]);
  }, [summary?.edgeCount, summary?.nodeCount]);

  const showLoadingOverlay = !graphReady && (isLoading || isFetching || Boolean(loadingProgress));
  const showSettlingStatus = graphReady && loadingProgress?.phase === "stabilizing_layout";
  const hasGraphContent = Boolean(summary?.nodeCount);
  const activePath = pathResult?.path ?? EMPTY_PATH;
  const activePathEdgeIds = pathResult?.edge_ids ?? EMPTY_PATH;
  const structuralSelectedNodeId = useMemo(() => {
    if (!selectedNodeId || !graph.hasNode(selectedNodeId)) {
      return "";
    }
    if (viewMode === "focused") {
      return selectedNodeId;
    }
    return collapsedNeighborhoodNodeIds.includes(selectedNodeId) ? selectedNodeId : "";
  }, [collapsedNeighborhoodNodeIds, selectedNodeId, viewMode]);
  const structuralActivePath = structuralSelectedNodeId ? activePath : EMPTY_PATH;
  const structuralActivePathEdgeIds = structuralSelectedNodeId ? activePathEdgeIds : EMPTY_PATH;
  const displayResult = useMemo(
    () => resolveDisplayGraph(structuralSelectedNodeId, structuralActivePath, structuralActivePathEdgeIds, viewMode, {
      aggregationEnabled,
      collapsedNeighborhoodNodeIds,
    }),
    [
      aggregationEnabled,
      collapsedNeighborhoodNodeIds,
      graphVersion,
      structuralActivePath,
      structuralActivePathEdgeIds,
      structuralSelectedNodeId,
      viewMode,
    ],
  );
  const displayState = useMemo(
    () => resolveDisplayStateSnapshot(selectedNodeId, activePath, viewMode, {
      aggregationEnabled,
      collapsedNeighborhoodNodeIds,
    }),
    [activePath, aggregationEnabled, collapsedNeighborhoodNodeIds, graphVersion, selectedNodeId, viewMode],
  );
  const displayMeta = displayResult.meta;
  const previousDisplayGraphRef = useRef(displayResult.graph);
  const previousDisplayStateRef = useRef(displayState);
  useEffect(() => {
    const graphRebuilt = previousDisplayGraphRef.current !== displayResult.graph;
    const displayStateChanged = previousDisplayStateRef.current !== displayState;
    debugGraphWorkspace("display-state-derived", {
      selectedNodeId,
      structuralSelectedNodeId,
      viewMode,
      graphRebuilt,
      displayStateChanged,
      aggregationEnabled,
      collapsedNeighborhoodActive: Boolean(structuralSelectedNodeId && collapsedNeighborhoodNodeIds.includes(structuralSelectedNodeId)),
    });
    previousDisplayGraphRef.current = displayResult.graph;
    previousDisplayStateRef.current = displayState;
  }, [
    aggregationEnabled,
    collapsedNeighborhoodNodeIds,
    displayResult.graph,
    displayState,
    selectedNodeId,
    structuralSelectedNodeId,
    viewMode,
  ]);
  const focusedSummary = useMemo(() => {
    if (!selectedNodeId || !graph.hasNode(selectedNodeId)) {
      if (viewMode === "grouped") {
        return displayState.groupedViewAvailable
          ? "Communities compressed into grouped structure view"
          : "Grouped view is unavailable for the current graph";
      }
      return null;
    }

    const localNeighborCount = graph.neighbors(selectedNodeId).length;
    if (viewMode === "focused") {
      const visibleNeighbors = displayState.selectedVisibleNeighborIds.length || Math.min(localNeighborCount, 16);
      return `${visibleNeighbors + 1} nodes in focused view`;
    }

    if (viewMode === "grouped") {
      return "Grouped structure view with direct community drill-in";
    }

    if (displayState.selectedCollapsedNeighborIds.length > 0) {
      return `${displayState.selectedVisibleNeighborIds.length} visible neighbors, ${displayState.selectedCollapsedNeighborIds.length} collapsed`;
    }

    return `${localNeighborCount} direct neighbors highlighted`;
  }, [displayState, selectedNodeId, viewMode]);
  const graphSummary = summary as GraphLoadSummary | null;
  const selectedNodeState = useMemo(
    () => buildSelectedNodeState(selectedNodeId, displayState),
    [displayState, selectedNodeId, summary?.nodeCount, summary?.edgeCount],
  );
  const selectedEdgeState = useMemo(
    () => buildSelectedEdgeState(selectedEdgeId, displayResult.graph),
    [displayResult.graph, selectedEdgeId, summary?.nodeCount, summary?.edgeCount],
  );
  const temporalState = useMemo(
    () => ({
      currentTime: scrubberTime,
      activeNodeCount,
      minDate: temporalBounds?.min ?? undefined,
      maxDate: temporalBounds?.max ?? undefined,
    }),
    [activeNodeCount, scrubberTime, temporalBounds?.max, temporalBounds?.min],
  );

  const pluginRegistry = useMemo<LazyPluginRegistryEntry[]>(
    () => [
      {
        id: "exploration-effects",
        panelId: "effects-panel",
        label: "Effects",
        title: "Open exploration effects controls",
        order: 18,
        load: loadExplorationEffectsPlugin,
        shouldLoad: ({ panelState }) => Boolean(panelState["effects-panel"]),
      },
      {
        id: "neighborhood-panel",
        panelId: "neighborhood-panel",
        label: "Neighbors",
        title: "Toggle neighborhood panel",
        order: 30,
        load: loadNeighborhoodPanelPlugin,
        shouldLoad: ({ panelState }) => Boolean(panelState["neighborhood-panel"]),
      },
      {
        id: "temporal-overlay",
        panelId: "temporal-panel",
        label: "Temporal",
        title: "Toggle temporal context panel",
        order: 40,
        load: loadTemporalOverlayPlugin,
        shouldLoad: ({ panelState, temporalState }) => Boolean(panelState["temporal-panel"] || temporalState?.currentTime),
      },
    ],
    [],
  );
  const activePlugins = useMemo(
    () => pluginRegistry.map((entry) => loadedPlugins[entry.id]).filter((plugin): plugin is GraphPlugin => Boolean(plugin)),
    [loadedPlugins, pluginRegistry],
  );

  useEffect(() => {
    let cancelled = false;

    pluginRegistry.forEach((entry) => {
      if (loadedPlugins[entry.id]) {
        return;
      }

      if (!entry.shouldLoad({ panelState: pluginPanelState, temporalState })) {
        return;
      }

      void entry.load()
        .then((plugin) => {
          if (cancelled) {
            return;
          }
          setLoadedPlugins((current) => (current[entry.id] ? current : { ...current, [entry.id]: plugin }));
        })
        .catch((error) => {
          console.error(`[GraphPlugin:${entry.id}] lazy load failed`, error);
        });
    });

    return () => {
      cancelled = true;
    };
  }, [loadedPlugins, pluginPanelState, pluginRegistry, temporalState]);

  const setEffectToggle = useCallback((effect: GraphEffectToggle, enabled: boolean | ((current: boolean) => boolean)) => {
    setEffectsState((current) => {
      const nextValue = typeof enabled === "function" ? enabled(current[effect]) : enabled;
      if (effect === "diagnosticsEnabled" && !GRAPH_THEME.effects.diagnostics.enabledInDev) {
        return current;
      }
      if (current[effect] === nextValue) {
        return current;
      }
      return {
        ...current,
        [effect]: nextValue,
      };
    });
  }, []);

  const handlePluginAction = useCallback((action: GraphPluginActionRequest) => {
    switch (action.type) {
      case "fitView":
        sceneRef.current?.fitView();
        return;
      case "focusNode":
        sceneRef.current?.focusNode(action.nodeId);
        return;
      case "selectNode":
        focusNode(action.nodeId);
        return;
      case "setViewMode":
        setViewMode(action.viewMode);
        return;
      case "collapseNeighborhood":
        if (!selectedNodeId) {
          return;
        }
        setCollapsedNeighborhoodNodeIds((current) => (
          current.includes(selectedNodeId) ? current : [...current, selectedNodeId]
        ));
        return;
      case "expandNeighborhood":
        if (!selectedNodeId) {
          return;
        }
        setCollapsedNeighborhoodNodeIds((current) => current.filter((nodeId) => nodeId !== selectedNodeId));
        return;
      case "toggleEffect":
        setEffectToggle(action.effect, (current) => !current);
        return;
      case "setEffect":
        setEffectToggle(action.effect, action.enabled);
        return;
      case "togglePanel":
        setPluginPanelState((current) => {
          const nextOpen = !current[action.panelId];
          setActiveDockPanelId((previous) => {
            if (nextOpen) {
              return action.panelId;
            }
            return previous === action.panelId ? null : previous;
          });
          return {
            ...current,
            [action.panelId]: nextOpen,
          };
        });
        return;
      case "openPanel":
        setActiveDockPanelId(action.panelId);
        setPluginPanelState((current) => ({
          ...current,
          [action.panelId]: true,
        }));
        return;
      case "closePanel":
        setPluginPanelState((current) => ({
          ...current,
          [action.panelId]: false,
        }));
        setActiveDockPanelId((previous) => (previous === action.panelId ? null : previous));
        return;
    }
  }, [focusNode, selectedNodeId, setEffectToggle]);

  const diagnosticsSnapshot = useMemo<GraphDiagnosticsSnapshot | null>(() => {
    if (!GRAPH_THEME.effects.diagnostics.enabledInDev || !graphDiagnosticsState) {
      return null;
    }

    return {
      interactionState: pluginInteractionStateRef.current,
      activePluginIds: activePlugins.map((plugin) => plugin.id),
      openPanelIds: Object.entries(pluginPanelState)
        .filter(([, isOpen]) => isOpen)
        .map(([panelId]) => panelId),
      effectsState,
      effectAvailability: graphDiagnosticsState,
    };
  }, [activePlugins, effectsState, graphDiagnosticsState, pluginPanelState]);

  const pluginContext = useMemo<GraphPluginContext>(() => ({
    get scene() {
      return pluginRuntimeRef.current;
    },
    get graph() {
      return graph;
    },
    get displayGraph() {
      return pluginRuntimeRef.current?.displayGraph ?? graph;
    },
    theme: GRAPH_THEME,
    getInteractionState: () => pluginInteractionStateRef.current,
    getSelectedNodeState: () => selectedNodeState,
    getInspectorState: () => ({
      selectedNodeId: selectedNodeId || null,
      ownsSelectionDetails: true,
    }),
    getGraphSummary: () => graphSummary,
    getTemporalState: () => temporalState,
    getEffectsState: () => effectsState,
    getDiagnosticsSnapshot: () => diagnosticsSnapshot,
    getAnalyticsSnapshot: () => graphAnalyticsState,
    getDisplayState: () => displayState,
    isPanelOpen: (panelId: string) => Boolean(pluginPanelState[panelId]),
    dispatchAction: handlePluginAction,
  }), [
    displayState,
    graphAnalyticsState,
    diagnosticsSnapshot,
    effectsState,
    graphSummary,
    handlePluginAction,
    pluginPanelState,
    selectedNodeId,
    selectedNodeState,
    temporalState,
  ]);

  const handleSceneRuntimeChange = useCallback((runtime: GraphSceneRuntime | null) => {
    pluginRuntimeRef.current = runtime;
    if (!runtime) {
      setGraphAnalyticsState(null);
    }
    setPluginRuntimeVersion((version) => version + 1);
  }, []);

  const handleInteractionStateChange = useCallback((interactionState: GraphInteractionState) => {
    pluginInteractionStateRef.current = interactionState;
    for (const plugin of activePlugins) {
      try {
        plugin.onStateChange(pluginContext, interactionState);
      } catch (error) {
        console.error(`[GraphPlugin:${plugin.id}] state update failed`, error);
      }
    }
  }, [activePlugins, pluginContext]);

  const handleDiagnosticsChange = useCallback((effectAvailability: GraphDiagnosticsSnapshot["effectAvailability"]) => {
    if (!GRAPH_THEME.effects.diagnostics.enabledInDev) {
      return;
    }
    setGraphDiagnosticsState(effectAvailability);
  }, []);

  const handleAnalyticsChange = useCallback((analytics: GraphAnalyticsSnapshot | null) => {
    setGraphAnalyticsState(analytics);
  }, []);

  useEffect(() => {
    if (!pluginRuntimeRef.current) {
      return;
    }

    const mountedPlugins: GraphPlugin[] = [];
    for (const plugin of activePlugins) {
      try {
        plugin.mount(pluginContext);
        mountedPlugins.push(plugin);
      } catch (error) {
        console.error(`[GraphPlugin:${plugin.id}] mount failed`, error);
      }
    }

    return () => {
      for (const plugin of mountedPlugins.reverse()) {
        try {
          plugin.unmount(pluginContext);
        } catch (error) {
          console.error(`[GraphPlugin:${plugin.id}] unmount failed`, error);
        }
      }
    };
  }, [activePlugins, pluginContext, pluginRuntimeVersion]);

  const pluginToolbarItems = useMemo<GraphPluginToolbarItem[]>(
    () => pluginRegistry.map((entry) => ({
      id: `${entry.id}-toggle`,
      label: entry.label,
      title: entry.title,
      active: pluginContext.isPanelOpen(entry.panelId),
      order: entry.order,
      onClick: () => pluginContext.dispatchAction({ type: "togglePanel", panelId: entry.panelId }),
    })),
    [pluginContext, pluginRegistry],
  );
  const pluginPanels = useMemo(
    () => collectPluginPanels(activePlugins, pluginContext),
    [activePlugins, pluginContext],
  );
  const pluginOverlays = useMemo(
    () => collectPluginOverlays(activePlugins, pluginContext),
    [activePlugins, pluginContext],
  );
  const pendingDockPanels = useMemo<GraphPluginPanelDescriptor[]>(
    () => pluginRegistry
      .filter((entry) => pluginPanelState[entry.panelId] && !loadedPlugins[entry.id])
      .map((entry) => ({
        id: entry.panelId,
        title: entry.label,
        placement: "bottom" as const,
        order: entry.order,
        content: <div style={pluginLoadingStyle}>Loading {entry.label.toLowerCase()}…</div>,
      })),
    [loadedPlugins, pluginPanelState, pluginRegistry],
  );
  const dockPanels = [...pluginPanels, ...pendingDockPanels]
    .filter((panel) => panel.placement === "bottom" || panel.placement === "side")
    .sort((left, right) => (left.order ?? 0) - (right.order ?? 0));
  const openDockPanels = dockPanels.filter((panel) => pluginPanelState[panel.id]);
  const activeDockPanel =
    openDockPanels.find((panel) => panel.id === activeDockPanelId)
    ?? openDockPanels[0]
    ?? null;
  const layoutState: ExploreLayoutState = {
    showInspector: Boolean(selectedNodeId),
    showPluginDock: openDockPanels.length > 0,
  };

  useEffect(() => {
    if (!openDockPanels.length) {
      setActiveDockPanelId(null);
      return;
    }

    if (!activeDockPanelId || !openDockPanels.some((panel) => panel.id === activeDockPanelId)) {
      setActiveDockPanelId(openDockPanels[0].id);
    }
  }, [activeDockPanelId, openDockPanels]);

  const coreToolbarGroups = useMemo<GraphToolbarGroup[]>(() => {
    const groups: GraphToolbarGroup[] = [];

    if (hasGraphContent) {
      groups.push({
        id: "view-mode",
        items: [
          {
            id: "view-full",
            label: "Full Graph",
            title: "Return to the full graph context",
            active: viewMode === "full",
            onClick: () => setViewMode("full"),
          },
          {
            id: "view-grouped",
            label: "Grouped View",
            title: displayState.groupedViewAvailable
              ? "Compress dense structure into detected communities"
              : "Grouped view is unavailable until communities can be detected",
            active: viewMode === "grouped",
            disabled: !displayState.groupedViewAvailable,
            onClick: () => setViewMode("grouped"),
          },
          {
            id: "view-focused",
            label: "Focused",
            title: "Inspect the selected node in a focused local graph",
            active: viewMode === "focused",
            disabled: !selectedNodeId,
            onClick: () => setViewMode("focused"),
          },
        ],
      });
    }

    if (selectedNodeState) {
      groups.push({
        id: "local-structure",
        items: [
          {
            id: "collapse-neighborhood",
            label: "Collapse Neighborhood",
            title: "Hide lower-priority fanout around the selected node",
            disabled: !selectedNodeState.canCollapseNeighborhood || selectedNodeState.isNeighborhoodCollapsed,
            onClick: () => handlePluginAction({ type: "collapseNeighborhood" }),
          },
          {
            id: "expand-neighborhood",
            label: "Expand Neighborhood",
            title: "Restore the collapsed local neighborhood",
            disabled: !selectedNodeState.isNeighborhoodCollapsed,
            onClick: () => handlePluginAction({ type: "expandNeighborhood" }),
          },
        ],
      });
    }

    groups.push({
      id: "graph-actions",
      items: [
        {
          id: "search-submit",
          label: "Search",
          title: "Search for the current query",
          tone: "primary",
          disabled: showLoadingOverlay || !searchQuery.trim(),
          onClick: () => void handleSearch(),
        },
        {
          id: "zoom-in",
          label: "＋ Zoom In",
          title: "Zoom in (or scroll up on the canvas)",
          onClick: () => sceneRef.current?.zoomIn(),
        },
        {
          id: "zoom-out",
          label: "－ Zoom Out",
          title: "Zoom out (or scroll down on the canvas)",
          onClick: () => sceneRef.current?.zoomOut(),
        },
        {
          id: "fit-view",
          label: "Fit View",
          title: "Reset the camera to fit the whole graph",
          onClick: () => sceneRef.current?.fitView(),
        },
        {
          id: "layout-toggle",
          label: isLayoutRunning ? "Pause Layout" : "Run Layout",
          title: "Toggle the layout worker",
          active: isLayoutRunning,
          disabled: showLoadingOverlay,
          onClick: () => setIsLayoutRunning((value) => !value),
        },
        {
          id: "reload",
          label: "Reload",
          title: "Reload the graph data",
          disabled: showLoadingOverlay,
          onClick: reload,
        },
      ],
    });

    if (pluginToolbarItems.length) {
      groups.push({
        id: "plugin-tools",
        items: pluginToolbarItems.map((item) => ({
          id: item.id,
          label: item.label,
          title: item.title,
          active: item.active,
          onClick: item.onClick,
        })),
      });
    }

    return groups;
  }, [
    displayState.groupedViewAvailable,
    handlePluginAction,
    hasGraphContent,
    isLayoutRunning,
    pluginToolbarItems,
    reload,
    searchQuery,
    selectedNodeId,
    selectedNodeState,
    showLoadingOverlay,
    viewMode,
  ]);

  const sceneAdapterProps = {
    onNodeSelect: focusNode,
    onEdgeSelect: handleEdgeSelect,
    graphVersion,
    graphReady,
    displayGraph: displayResult.graph,
    displayMeta,
    displayState,
    selectedNodeId,
    selectedEdgeId,
    activePath,
    activePathEdgeIds,
    effectsState,
    temporalState,
    isLayoutRunning,
    layoutSource: graphSummary?.layoutSource,
    viewMode,
    showFitViewButton: false,
    pluginOverlays: pluginOverlays.map((overlay) => overlay.element),
    onRuntimeChange: handleSceneRuntimeChange,
    onInteractionStateChange: handleInteractionStateChange,
    onDiagnosticsChange: handleDiagnosticsChange,
    onAnalyticsChange: handleAnalyticsChange,
  } as const;

  return (
    <div className="palantir-bg" style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden" }}>
      <style>{HUD_CSS}</style>
      <div className="palantir-grid" />
      <div className="palantir-vignette" />

      <div className="explore-shell">
        <section className="explore-command-deck">
          <SurfaceCard tone="subtle">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="explore-toolbar">
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  {(showLoadingOverlay || showSettlingStatus) && loadingProgress ? (
                    <MetricChip>{getGraphLoadTitle(loadingProgress.phase)}</MetricChip>
                  ) : null}
                  {summary ? (
                    <MetricChip>{summary.nodeCount.toLocaleString()} nodes · {summary.edgeCount.toLocaleString()} edges</MetricChip>
                  ) : null}
                  {activeNodeCount !== null ? (
                    <MetricChip tone="success">{activeNodeCount.toLocaleString()} active</MetricChip>
                  ) : null}
                  {focusedSummary ? <MetricChip tone="warm">{focusedSummary}</MetricChip> : null}
                </div>
                <div className="explore-toolbar-groups">
                  <div style={{ minWidth: 280, flex: "1 1 320px" }}>
                    <input
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          void handleSearch();
                        }
                      }}
                      placeholder="Search a node, e.g. Metformin"
                      style={{ ...inputStyle, margin: 0, minHeight: 38 }}
                    />
                  </div>
                  {coreToolbarGroups.map((group) => (
                    <div key={group.id} className="explore-toolbar-group">
                      {group.items.map((item) => {
                        const baseStyle = item.tone === "primary" ? actionButtonStyle : secondaryActionButtonStyle;
                        return (
                          <button
                            key={item.id}
                            onClick={item.onClick}
                            title={item.title}
                            disabled={item.disabled}
                            style={{
                              ...baseStyle,
                              minHeight: 36,
                              padding: "8px 12px",
                              background: item.active
                                ? "rgba(31, 111, 235, 0.28)"
                                : baseStyle.background,
                              border: item.active
                                ? "1px solid rgba(127, 208, 255, 0.35)"
                                : baseStyle.border,
                              color: item.active ? "#e6f2ff" : baseStyle.color,
                              boxShadow: item.active ? `0 0 0 1px rgba(127, 208, 255, 0.12)` : baseStyle.boxShadow,
                            }}
                          >
                            {item.label}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>

              {searchError ? <div style={{ color: "#ff7b72", fontSize: 12 }}>{searchError}</div> : null}

              {searchResults.length ? (
                <div className="explore-search-results hud-scrollbar" style={searchResultsStripStyle}>
                  {searchResults.map((result) => (
                    <button key={result.node.id} style={predictionCardStyle} onClick={() => focusNode(result.node.id)}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ color: "#fff", fontWeight: 600 }}>{result.node.content || result.node.id}</div>
                          <div style={{ color: "#8b949e", fontSize: 12 }}>{result.node.type}</div>
                        </div>
                        <div style={{ color: "#58a6ff", fontSize: 12, whiteSpace: "nowrap" }}>
                          {result.score.toFixed(3)}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : null}

              {selectedEdgeState ? (
                <div style={selectedEdgeCardStyle}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ color: "rgba(127, 208, 255, 0.76)", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                        Relationship
                      </div>
                      <div style={{ color: "#f4f8ff", fontSize: 15, fontWeight: 700, marginTop: 6 }}>
                        {selectedEdgeState.edgeType}
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedEdgeId("")}
                      style={{ ...secondaryActionButtonStyle, minHeight: 30, padding: "6px 10px" }}
                    >
                      Close
                    </button>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <button style={selectedEdgeNodeChipStyle} onClick={() => focusNode(selectedEdgeState.sourceId)}>
                      {selectedEdgeState.sourceLabel}
                    </button>
                    <span style={{ color: "#7fa7ce", fontSize: 12 }}>→</span>
                    <button style={selectedEdgeNodeChipStyle} onClick={() => focusNode(selectedEdgeState.targetId)}>
                      {selectedEdgeState.targetLabel}
                    </button>
                  </div>

                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <MetricChip tone="warm">weight {selectedEdgeState.weight.toFixed(2)}</MetricChip>
                    {selectedEdgeState.isAggregated ? (
                      <MetricChip tone="success">
                        {selectedEdgeState.aggregateCount} bundled edge{selectedEdgeState.aggregateCount === 1 ? "" : "s"}
                      </MetricChip>
                    ) : (
                      <MetricChip>{selectedEdgeState.siblingCount} parallel lane{selectedEdgeState.siblingCount === 1 ? "" : "s"}</MetricChip>
                    )}
                    <MetricChip>{selectedEdgeState.familySize} family member{selectedEdgeState.familySize === 1 ? "" : "s"}</MetricChip>
                    {selectedEdgeState.bundleKind ? (
                      <MetricChip>{selectedEdgeState.bundleKind} bundle</MetricChip>
                    ) : null}
                    {selectedEdgeState.dominantEdgeType ? (
                      <MetricChip>{selectedEdgeState.dominantEdgeType}</MetricChip>
                    ) : null}
                    {selectedEdgeState.provenanceCount > 0 ? (
                      <MetricChip>{selectedEdgeState.provenanceCount} provenance fields</MetricChip>
                    ) : null}
                  </div>

                  {Object.keys(selectedEdgeState.properties).length ? (
                    <div style={selectedEdgePropertyGridStyle}>
                      {Object.entries(selectedEdgeState.properties).slice(0, 4).map(([key, value]) => (
                        <div key={key} style={selectedEdgePropertyCardStyle}>
                          <div style={{ color: "rgba(127, 208, 255, 0.68)", fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                            {key}
                          </div>
                          <div style={{ color: "#dce7f4", fontSize: 12, marginTop: 4, wordBreak: "break-word" }}>
                            {typeof value === "object" ? JSON.stringify(value) : String(value)}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </SurfaceCard>
        </section>

        <div
          className="explore-main-grid"
          style={{
            gridTemplateColumns: layoutState.showInspector ? "minmax(0, 1fr) minmax(320px, 360px)" : "minmax(0, 1fr)",
          }}
        >
          <div className="explore-scene-stack">
            <SurfaceCard padding="none" className="explore-scene-card">
              <div className="explore-scene-shell">
                <div className="palantir-grid" />
                <div className="palantir-vignette" />
                <div className="explore-scene-stage">
                  <SigmaSceneAdapter
                    ref={sceneRef}
                    {...sceneAdapterProps}
                  />
                  <GraphLoadingOverlay
                    progress={loadingProgress}
                    visible={showLoadingOverlay}
                    showGraphBehind={hasGraphContent || Boolean(loadingProgress?.showGraphBehind)}
                  />
                </div>
              </div>

              {layoutState.showPluginDock ? (
                <div className="explore-plugin-dock">
                  <SurfaceCard tone="subtle" style={{ borderRadius: 0, borderLeft: "none", borderRight: "none", borderBottom: "none" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                        <div className="explore-plugin-dock-tabs">
                          {openDockPanels.map((panel) => (
                            <button
                              key={panel.id}
                              className="explore-plugin-dock-tab"
                              data-active={activeDockPanel?.id === panel.id}
                              onClick={() => setActiveDockPanelId(panel.id)}
                            >
                              {panel.title}
                            </button>
                          ))}
                          {activeDockPanel ? (
                            <button
                              className="explore-plugin-dock-tab"
                              onClick={() => handlePluginAction({ type: "closePanel", panelId: activeDockPanel.id })}
                            >
                              ×
                            </button>
                          ) : null}
                        </div>
                      </div>
                      {activeDockPanel ? (
                        <div style={pluginDockContentStyle}>{activeDockPanel.content}</div>
                      ) : null}
                    </div>
                  </SurfaceCard>
                </div>
              ) : null}

              <div className="explore-scene-footer">
                <Suspense fallback={<div style={timelineFallbackStyle}>Loading timeline…</div>}>
                  <LazyTimelinePanel
                    onTimeChange={setScrubberTime}
                    minDate={temporalBounds?.min ?? undefined}
                    maxDate={temporalBounds?.max ?? undefined}
                  />
                </Suspense>
              </div>
            </SurfaceCard>
          </div>

          {layoutState.showInspector ? (
            <div className="explore-inspector-shell">
              <InspectorPanel open={layoutState.showInspector} className="explore-inspector-card">
                <div className="explore-inspector-scroll hud-scrollbar">
                  <Suspense fallback={<div style={inspectorFallbackStyle}>Loading inspector…</div>}>
                    <LazyGraphInspectorPanel
                      nodeId={selectedNodeId}
                      predictions={predictions}
                      predictionType={predictionType}
                      onPredictionTypeChange={setPredictionType}
                      onRunPredictions={() => void handleRunPredictions()}
                      isRunningPredictions={isRunningPredictions}
                      pathTargetId={pathTargetId}
                      onPathTargetChange={setPathTargetId}
                      onTracePath={() => void handleTracePath()}
                      pathResult={pathResult}
                      onDownloadProvenance={(format) => void handleDownloadProvenance(format)}
                    />
                  </Suspense>
                </div>
              </InspectorPanel>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  background: "rgba(4, 10, 18, 0.5)",
  border: `1px solid ${GRAPH_THEME.palette.background.shellBorder}`,
  color: "#edf5ff",
  borderRadius: 12,
  padding: "11px 13px",
  fontSize: 13,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
};

const actionButtonStyle: React.CSSProperties = {
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

const secondaryActionButtonStyle: React.CSSProperties = {
  ...actionButtonStyle,
  background: "rgba(255, 255, 255, 0.03)",
  border: "1px solid rgba(255, 255, 255, 0.08)",
  color: "#c6d4e3",
  fontWeight: 600,
};

const predictionCardStyle: React.CSSProperties = {
  textAlign: "left",
  padding: 12,
  background: "rgba(88, 166, 255, 0.08)",
  border: "1px solid rgba(88, 166, 255, 0.12)",
  borderRadius: 10,
  cursor: "pointer",
};

const selectedEdgeCardStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 12,
  padding: 14,
  background: "linear-gradient(135deg, rgba(88, 166, 255, 0.1), rgba(88, 166, 255, 0.04))",
  border: "1px solid rgba(127, 208, 255, 0.16)",
  borderRadius: 14,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
};

const selectedEdgeNodeChipStyle: React.CSSProperties = {
  ...secondaryActionButtonStyle,
  minHeight: 32,
  padding: "7px 12px",
  whiteSpace: "nowrap",
};

const selectedEdgePropertyGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: 8,
};

const selectedEdgePropertyCardStyle: React.CSSProperties = {
  borderRadius: 10,
  padding: 10,
  background: "rgba(255, 255, 255, 0.03)",
  border: "1px solid rgba(255, 255, 255, 0.06)",
};

const pluginDockContentStyle: React.CSSProperties = {
  borderRadius: 16,
  border: "1px solid rgba(255, 255, 255, 0.06)",
  background: "rgba(255, 255, 255, 0.02)",
  padding: 14,
};

const pluginLoadingStyle: React.CSSProperties = {
  color: "#8ea4be",
  fontSize: 12,
  padding: 10,
};

const searchResultsStripStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 10,
  maxHeight: 186,
  overflowY: "auto",
};

const inspectorFallbackStyle: React.CSSProperties = {
  padding: 24,
  color: "#8ea4be",
  fontSize: 12,
};

const timelineFallbackStyle: React.CSSProperties = {
  height: "90px",
  display: "flex",
  alignItems: "center",
  padding: "0 18px",
  color: "#8ea4be",
  fontSize: 12,
  borderTop: "1px solid rgba(88, 166, 255, 0.2)",
  background: "rgba(1, 4, 9, 0.88)",
};
