export type GraphViewMode = "focused" | "full" | "grouped";
export type GraphLayoutSource = "provided" | "carried" | "runtime";
export type GraphLayoutState = "idle" | "bootstrapping" | "running" | "stabilized" | "interactive" | "failed";
export type GraphLoadPhase =
  | "bootstrapping"
  | "fetching_nodes"
  | "fetching_edges"
  | "computing_styling"
  | "hydrating_scene"
  | "stabilizing_layout"
  | "ready";
export type GraphLoadProgressKind = "determinate" | "indeterminate";
export type GraphNodeInteractionState = "default" | "hovered" | "selected" | "neighbor" | "path" | "inactive" | "muted";
export type GraphEdgeInteractionState = "default" | "backbone" | "hovered" | "selected" | "neighbor" | "path" | "inactive" | "muted";
export type GraphSelectedNodeKind = "none" | "base" | "grouped" | "unavailable";

export interface GraphCameraState {
  x: number;
  y: number;
  ratio: number;
}

export interface GraphInteractionState {
  hoveredNodeId: string | null;
  selectedNodeId: string;
  selectedEdgeId: string;
  focusedNodeId: string;
  activePath: string[];
  activePathEdgeIds: string[];
  viewMode: GraphViewMode;
  zoomTier: "overview" | "structure" | "inspection";
  isLayoutRunning: boolean;
}

export interface GraphDisplayStateSnapshot {
  aggregationEnabled: boolean;
  groupedViewAvailable: boolean;
  groupedViewReason: string | null;
  selectedRootNodeId: string | null;
  selectedVisibleNeighborIds: string[];
  selectedCollapsedNeighborIds: string[];
  selectedNodeKind: GraphSelectedNodeKind;
  canActivateFocused: boolean;
  resolvedFocusedNodeId: string | null;
  focusedUnavailableReason: string | null;
}

export type GraphDisplayLayoutMode = "base" | "mirrored" | "owned";

export interface GraphDisplayMeta {
  layoutMode: GraphDisplayLayoutMode;
  positionSource: "store" | "display";
  tracksStoreNodePositions: boolean;
  hasSyntheticNodes: boolean;
}

export type GraphEffectToggle =
  | "pathPulseEnabled"
  | "pathFlowEnabled"
  | "lensEnabled"
  | "temporalEmphasisEnabled"
  | "semanticRegionsEnabled"
  | "contoursEnabled"
  | "pathfindingEnabled"
  | "communitiesEnabled"
  | "centralityEnabled"
  | "legendEnabled"
  | "diagnosticsEnabled";

export interface GraphEffectsState {
  pathPulseEnabled: boolean;
  pathFlowEnabled: boolean;
  lensEnabled: boolean;
  temporalEmphasisEnabled: boolean;
  semanticRegionsEnabled: boolean;
  contoursEnabled: boolean;
  pathfindingEnabled: boolean;
  communitiesEnabled: boolean;
  centralityEnabled: boolean;
  legendEnabled: boolean;
  diagnosticsEnabled: boolean;
  lensMode: "neighborhood";
  effectQuality: "bounded";
}

export interface GraphEffectAvailability {
  enabled: boolean;
  available: boolean;
  reason: string;
  detail?: string;
  visibleSegments?: number;
  segmentCap?: number;
}

export interface GraphDiagnosticsSnapshot {
  interactionState: GraphInteractionState;
  activePluginIds: string[];
  openPanelIds: string[];
  effectsState: GraphEffectsState;
  effectAvailability: {
    pathPulse: GraphEffectAvailability;
    pathFlow: GraphEffectAvailability;
    lens: GraphEffectAvailability;
    temporalEmphasis: GraphEffectAvailability;
    semanticRegions: GraphEffectAvailability;
    contours: GraphEffectAvailability;
    pathfinding: GraphEffectAvailability;
    communities: GraphEffectAvailability;
    centrality: GraphEffectAvailability;
    legend: GraphEffectAvailability;
    diagnostics: GraphEffectAvailability;
  };
}

export interface GraphTemporalState {
  currentTime: Date | null;
  activeNodeCount: number | null;
  minDate?: string;
  maxDate?: string;
}

export interface GraphDirectedPathSnapshot {
  ready: boolean;
  reason: string;
  sourceId: string | null;
  targetId: string | null;
  path: string[];
  length: number | null;
  verifiedAgainstActivePath: boolean;
}

export interface GraphCommunitySummary {
  communityId: string;
  nodeCount: number;
  visibleNodeCount: number;
  dominantSemanticGroup: string;
  color: string;
  anchorNodeId: string | null;
  anchorLabel: string;
  prominence: number;
}

export interface GraphSemanticRegionSummary {
  semanticGroup: string;
  nodeCount: number;
  visibleNodeCount: number;
  color: string;
  anchorNodeId: string | null;
  anchorLabel: string;
  dominantCommunityId: string | null;
  prominence: number;
}

export interface GraphCentralityNodeSummary {
  id: string;
  label: string;
  semanticGroup: string;
  color: string;
  degree: number;
  betweenness: number;
  score: number;
}

export interface GraphOverviewBackboneSnapshot {
  ready: boolean;
  reason: string;
  edgeIds: string[];
}

export interface GraphAnalyticsSnapshot {
  generatedAt: number;
  directedPath: GraphDirectedPathSnapshot;
  communities: {
    ready: boolean;
    reason: string;
    count: number;
    modularity: number | null;
    summaries: GraphCommunitySummary[];
  };
  centrality: {
    ready: boolean;
    reason: string;
    topNodes: GraphCentralityNodeSummary[];
  };
  semanticRegions: {
    ready: boolean;
    reason: string;
    summaries: GraphSemanticRegionSummary[];
  };
  overviewBackbone: GraphOverviewBackboneSnapshot;
}

export interface ApiNode {
  id: string;
  type: string;
  content: string;
  x?: number | null;
  y?: number | null;
  properties: Record<string, unknown>;
  valid_from?: string | null;
  valid_until?: string | null;
}

export interface ApiEdge {
  id: string;
  familyId: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  properties: Record<string, unknown>;
}

export interface GraphLoadSummary {
  nodeCount: number;
  edgeCount: number;
  loadTimeMs: number;
  hasCoordinates?: boolean;
  layoutSource?: GraphLayoutSource;
  layoutReady?: boolean;
}

export interface GraphLoadProgress {
  phase: GraphLoadPhase;
  title: string;
  nodesLoaded: number;
  nodesTotal: number | null;
  edgesLoaded: number;
  edgesTotal: number | null;
  message: string;
  progressKind: GraphLoadProgressKind;
  loaded: number | null;
  total: number | null;
  showGraphBehind: boolean;
  stageIndex?: number;
  stageCount?: number;
  layoutSource?: GraphLayoutSource;
  layoutState?: GraphLayoutState;
}

export interface GraphDataSnapshot {
  nodes: ApiNode[];
  edges: ApiEdge[];
  summary: GraphLoadSummary;
  fetchedAt: number;
}

export interface GraphLayoutStatus {
  state: GraphLayoutState;
  source: GraphLayoutSource;
  hasCoordinates: boolean;
  layoutReady: boolean;
  displacement: number | null;
  elapsedMs: number;
  stableSamples: number;
  timedOut?: boolean;
}

export type GraphPath = string[];

export interface GraphSelectedNodeState {
  id: string;
  label: string;
  content: string;
  nodeType: string;
  color?: string;
  valid_from?: string | null;
  valid_until?: string | null;
  properties: Record<string, unknown>;
  neighborCount: number;
  visibleNeighborCount: number;
  collapsedNeighborCount: number;
  isNeighborhoodCollapsed: boolean;
  canCollapseNeighborhood: boolean;
}

export interface GraphSelectedEdgeState {
  id: string;
  familyId: string;
  sourceId: string;
  sourceLabel: string;
  targetId: string;
  targetLabel: string;
  edgeType: string;
  weight: number;
  properties: Record<string, unknown>;
  provenanceCount: number;
  familySize: number;
  siblingCount: number;
  isAggregated: boolean;
  aggregateCount: number;
  rawEdgeIds: string[];
  bundleKind: "parallel" | "bidirectional" | "community" | null;
  dominantEdgeType: string | null;
  representativeWeight: number;
}

export interface GraphStageHandle {
  fitView: () => void;
  focusNode: (nodeId: string) => void;
}
