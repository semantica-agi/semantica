import Graph from "graphology";

import { graph, type EdgeAttributes, type NodeAttributes } from "../../store/graphStore";
import {
  clamp,
  blendHex,
  GRAPH_THEME,
  type GraphArrowVisibilityPolicy,
  type GraphBadgeKind,
  type GraphEdgeVariant,
  type GraphEdgeVisualState,
  type GraphLabelVisibilityPolicy,
  type GraphNodeShapeVariant,
  type GraphNodeVisualState,
  type GraphTheme,
  type GraphZoomTier,
  hashString,
  withAlpha,
  zoomTierAtLeast,
} from "./graphTheme";
import { computeGraphAnalyticsBase } from "./graphAnalytics";
import type {
  GraphDisplayMeta,
  GraphDisplayStateSnapshot,
  GraphInteractionState,
  GraphSelectedNodeKind,
  GraphViewMode,
} from "./types";

const MAX_FOCUS_NEIGHBORS = GRAPH_THEME.focus.maxNeighbors;
const FOCUS_PRIMARY_LABELS = GRAPH_THEME.focus.primaryLabels;
const COLLAPSE_VISIBLE_NEIGHBORS = 8;
const GROUP_SAMPLE_MEMBERS = 8;
const AGGREGATED_EDGE_PREFIX = "__agg__:";
const COMMUNITY_NODE_PREFIX = "__community__:";
const DEBUG_GRAPH_SCENE_STATE = import.meta.env.DEV;

type GraphRef = typeof graph | Graph<NodeAttributes, EdgeAttributes>;

export type GraphDisplayResult = {
  graph: GraphRef;
  state: GraphDisplayStateSnapshot;
  meta: GraphDisplayMeta;
};

const BASE_DISPLAY_META: GraphDisplayMeta = {
  layoutMode: "base",
  positionSource: "store",
  tracksStoreNodePositions: true,
  hasSyntheticNodes: false,
};

const MIRRORED_DISPLAY_META: GraphDisplayMeta = {
  layoutMode: "mirrored",
  positionSource: "store",
  tracksStoreNodePositions: true,
  hasSyntheticNodes: false,
};

const OWNED_DISPLAY_META: GraphDisplayMeta = {
  layoutMode: "owned",
  positionSource: "display",
  tracksStoreNodePositions: false,
  hasSyntheticNodes: true,
};

const FOCUSED_DISPLAY_META: GraphDisplayMeta = {
  layoutMode: "owned",
  positionSource: "display",
  tracksStoreNodePositions: false,
  hasSyntheticNodes: false,
};

function getOverviewPresenceBoost(cameraRatio: number) {
  return clamp(0, Math.log2(Math.max(cameraRatio, 1)) / 1.85, 1);
}

export type GraphSigmaEdgeType = "line" | "arrow" | "curve" | "curvedArrow";

export type ResolvedNodeStyle = {
  color: string;
  shellColor: string;
  coreScale: number;
  size: number;
  forceLabel: boolean;
  label: string;
  zIndex: number;
  hidden: boolean;
  borderColor: string;
  borderSize: number;
  nodeVariant: GraphNodeShapeVariant;
  badgeKind?: GraphBadgeKind;
  badgeCount?: number;
  showBadge: boolean;
  showRing: boolean;
  ringColor?: string;
  ringSize: number;
  showHalo: boolean;
  haloColor: string;
};

export type ResolvedEdgeStyle = {
  hidden: boolean;
  type?: GraphSigmaEdgeType;
  color?: string;
  size?: number;
  zIndex: number;
  edgeVariant: GraphEdgeVariant;
  arrowVisibilityPolicy: GraphArrowVisibilityPolicy;
  curveStrength: number;
  curvature: number;
};

function forEachDirectedEdgeBetween(
  graphRef: GraphRef,
  source: string,
  target: string,
  callback: (edgeId: string, attrs: EdgeAttributes) => void,
) {
  graphRef.forEachDirectedEdge(source, target, (edgeId, attrs) => {
    callback(String(edgeId), attrs as EdgeAttributes);
  });
}

function collectDirectedEdgeIdsBetween(
  graphRef: GraphRef,
  source: string,
  target: string,
): string[] {
  const edgeIds: string[] = [];
  forEachDirectedEdgeBetween(graphRef, source, target, (edgeId) => {
    edgeIds.push(edgeId);
  });
  return edgeIds;
}

function isAggregatedEdgeAttributes(attrs: EdgeAttributes | undefined): boolean {
  return Boolean(attrs?.isAggregated || (attrs?.rawEdgeIds?.length ?? 0) > 1);
}

function collectRawEdgeIds(attrs: EdgeAttributes | undefined, fallbackEdgeId?: string): string[] {
  const rawEdgeIds = attrs?.rawEdgeIds?.map((edgeId) => String(edgeId)).filter(Boolean) ?? [];
  if (rawEdgeIds.length > 0) {
    return rawEdgeIds;
  }
  return fallbackEdgeId ? [String(fallbackEdgeId)] : [];
}

function createEmptyDisplayState(
  selectedNodeId: string,
  aggregationEnabled: boolean,
): GraphDisplayStateSnapshot {
  return {
    aggregationEnabled,
    groupedViewAvailable: false,
    groupedViewReason: null,
    selectedRootNodeId: selectedNodeId || null,
    selectedVisibleNeighborIds: [],
    selectedCollapsedNeighborIds: [],
    selectedNodeKind: selectedNodeId ? "unavailable" : "none",
    canActivateFocused: false,
    resolvedFocusedNodeId: null,
    focusedUnavailableReason: selectedNodeId ? "Selected item is not available in the current graph." : null,
  };
}

function resolveGroupedDisplayNodeId(
  displayGraph: GraphRef,
  nodeId: string,
): string | null {
  if (!nodeId) {
    return null;
  }

  if (displayGraph.hasNode(nodeId)) {
    return nodeId;
  }

  let resolvedNodeId: string | null = null;
  displayGraph.forEachNode((candidateId, attrs) => {
    if (resolvedNodeId) {
      return;
    }

    const communityGroup = (attrs as NodeAttributes).properties?.__communityGroup as
      | {
          anchorNodeId?: string | null;
          memberNodeIds?: string[];
          sampleNodeIds?: string[];
        }
      | undefined;
    if (!communityGroup) {
      return;
    }

    if (communityGroup.anchorNodeId === nodeId) {
      resolvedNodeId = candidateId;
      return;
    }

    if (communityGroup.sampleNodeIds?.includes(nodeId) || communityGroup.memberNodeIds?.includes(nodeId)) {
      resolvedNodeId = candidateId;
    }
  });

  return resolvedNodeId;
}

function rankGroupedNeighbors(
  displayGraph: GraphRef,
  nodeId: string,
): string[] {
  const resolvedNodeId = resolveGroupedDisplayNodeId(displayGraph, nodeId);
  if (!resolvedNodeId) {
    return [];
  }

  const scoredNeighbors = new Map<string, number>();
  displayGraph.forEachEdge((_, attrs, source, target) => {
    const sourceId = String(source);
    const targetId = String(target);
    if (sourceId !== resolvedNodeId && targetId !== resolvedNodeId) {
      return;
    }

    const neighborId = sourceId === resolvedNodeId ? targetId : sourceId;
    if (!neighborId || neighborId === resolvedNodeId || !displayGraph.hasNode(neighborId)) {
      return;
    }

    const weightCandidate = Number(
      (attrs as EdgeAttributes).aggregateCount
      ?? (attrs as EdgeAttributes).baseSize
      ?? (attrs as EdgeAttributes).size
      ?? (attrs as EdgeAttributes).weight
      ?? 1,
    );
    const weight = Number.isFinite(weightCandidate) && weightCandidate > 0 ? weightCandidate : 1;
    scoredNeighbors.set(neighborId, (scoredNeighbors.get(neighborId) ?? 0) + weight);
  });

  return Array.from(scoredNeighbors.entries())
    .sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    })
    .map(([neighborId]) => neighborId);
}

export function resolveGroupedDisplayStateSnapshot(
  displayGraph: GraphRef,
  selectedNodeId: string,
  options?: {
    groupedViewAvailable?: boolean;
    groupedViewReason?: string | null;
    selectedNodeKind?: GraphSelectedNodeKind;
    resolvedFocusedNodeId?: string | null;
    focusedUnavailableReason?: string | null;
  },
): GraphDisplayStateSnapshot {
  const displayState = createEmptyDisplayState(selectedNodeId, true);
  displayState.groupedViewAvailable = options?.groupedViewAvailable ?? true;
  displayState.groupedViewReason = options?.groupedViewReason ?? null;
  displayState.selectedNodeKind = options?.selectedNodeKind ?? (selectedNodeId ? "grouped" : "none");
  displayState.resolvedFocusedNodeId = options?.resolvedFocusedNodeId ?? null;
  displayState.canActivateFocused = Boolean(displayState.resolvedFocusedNodeId);
  displayState.focusedUnavailableReason = displayState.canActivateFocused
    ? null
    : (options?.focusedUnavailableReason ?? displayState.focusedUnavailableReason);

  if (!selectedNodeId) {
    return displayState;
  }

  const resolvedNodeId = resolveGroupedDisplayNodeId(displayGraph, selectedNodeId);
  if (!resolvedNodeId) {
    return displayState;
  }

  const rankedNeighbors = rankGroupedNeighbors(displayGraph, resolvedNodeId);
  displayState.selectedRootNodeId = resolvedNodeId;
  displayState.selectedVisibleNeighborIds = rankedNeighbors.slice(0, MAX_FOCUS_NEIGHBORS);
  displayState.selectedCollapsedNeighborIds = rankedNeighbors.slice(MAX_FOCUS_NEIGHBORS);
  return displayState;
}

function validateGroupedDisplayGraph(grouped: Graph<NodeAttributes, EdgeAttributes>): string | null {
  if (grouped.order === 0) {
    return "Grouped view is unavailable because no community nodes could be created.";
  }

  let invalidReason: string | null = null;
  grouped.forEachNode((nodeId, attrs) => {
    if (invalidReason) {
      return;
    }

    const nodeAttrs = attrs as NodeAttributes;
    if (!Number.isFinite(Number(nodeAttrs.x)) || !Number.isFinite(Number(nodeAttrs.y))) {
      invalidReason = `Grouped node ${nodeId} has invalid coordinates.`;
    }
  });

  if (invalidReason) {
    return invalidReason;
  }

  grouped.forEachEdge((edgeId, _attrs, sourceId, targetId) => {
    if (invalidReason) {
      return;
    }

    if (!grouped.hasNode(sourceId) || !grouped.hasNode(targetId)) {
      invalidReason = `Grouped edge ${edgeId} references a missing grouped node.`;
    }
  });

  return invalidReason;
}

export function buildPathEdgeSet(
  graphRef: GraphRef,
  path: string[],
  pathEdgeIds: string[] = [],
): Set<string> {
  if (pathEdgeIds.length > 0) {
    const requested = new Set(pathEdgeIds.map((edgeId) => String(edgeId)));
    const matched = new Set<string>();
    graphRef.forEachEdge((edgeId, attrs) => {
      const stableEdgeId = String(edgeId);
      if (requested.has(stableEdgeId)) {
        matched.add(stableEdgeId);
        return;
      }

      const rawEdgeIds = collectRawEdgeIds(attrs as EdgeAttributes, stableEdgeId);
      if (rawEdgeIds.some((rawEdgeId) => requested.has(rawEdgeId))) {
        matched.add(stableEdgeId);
      }
    });
    return matched;
  }

  const edgeIds = new Set<string>();
  for (let index = 0; index < path.length - 1; index += 1) {
    collectDirectedEdgeIdsBetween(graphRef, path[index], path[index + 1]).forEach((edgeId) => edgeIds.add(edgeId));
  }
  return edgeIds;
}

export function buildEdgeEndpointSet(
  graphRef: GraphRef,
  ...edgeIds: Array<string | null | undefined>
): Set<string> {
  const nodeIds = new Set<string>();

  edgeIds.forEach((edgeId) => {
    if (!edgeId || !graphRef.hasEdge(edgeId)) {
      return;
    }

    const [source, target] = graphRef.extremities(edgeId);
    nodeIds.add(source);
    nodeIds.add(target);
  });

  return nodeIds;
}

function collectFocusEdgeIds(
  graphRef: GraphRef,
  nodeIds: Set<string>,
): Set<string> {
  const edgeIds = new Set<string>();
  const ids = Array.from(nodeIds);

  for (let sourceIndex = 0; sourceIndex < ids.length; sourceIndex += 1) {
    const source = ids[sourceIndex];

    for (let targetIndex = 0; targetIndex < ids.length; targetIndex += 1) {
      const target = ids[targetIndex];
      if (source === target) {
        continue;
      }

      collectDirectedEdgeIdsBetween(graphRef, source, target).forEach((edgeId) => edgeIds.add(edgeId));
    }
  }

  return edgeIds;
}

function collectImpactedNodeIds(
  graphRef: typeof graph | Graph<NodeAttributes, EdgeAttributes>,
  interactionState: GraphInteractionState | null,
): Set<string> {
  if (!interactionState) {
    return new Set<string>();
  }

  const impacted = new Set<string>(interactionState.activePath);
  const primaryNodeId = interactionState.hoveredNodeId || interactionState.selectedNodeId;
  if (primaryNodeId && graphRef.hasNode(primaryNodeId)) {
    buildFocusSetInGraph(graphRef, primaryNodeId).forEach((nodeId) => impacted.add(nodeId));
  }

  buildEdgeEndpointSet(graphRef, interactionState.selectedEdgeId)
    .forEach((nodeId) => impacted.add(nodeId));

  return impacted;
}

function collectImpactedEdgeKeys(
  graphRef: typeof graph | Graph<NodeAttributes, EdgeAttributes>,
  interactionState: GraphInteractionState | null,
): Set<string> {
  if (!interactionState) {
    return new Set<string>();
  }

  const impacted = new Set<string>(buildPathEdgeSet(graphRef, interactionState.activePath, interactionState.activePathEdgeIds));
  const primaryNodeId = interactionState.hoveredNodeId || interactionState.selectedNodeId;
  if (primaryNodeId && graphRef.hasNode(primaryNodeId)) {
    collectFocusEdgeIds(graphRef, buildFocusSetInGraph(graphRef, primaryNodeId)).forEach((edgeId) => impacted.add(edgeId));
  }

  if (interactionState.selectedEdgeId) {
    impacted.add(interactionState.selectedEdgeId);
  }

  return impacted;
}

function resolveDisplayEdgeIds(
  graphRef: GraphRef,
  stableEdgeIds: Set<string>,
): string[] {
  const displayEdgeIds = new Set<string>();
  graphRef.forEachEdge((edgeId, attrs) => {
    const stableEdgeId = String(edgeId);
    if (stableEdgeIds.has(stableEdgeId)) {
      displayEdgeIds.add(stableEdgeId);
      return;
    }

    const rawEdgeIds = collectRawEdgeIds(attrs as EdgeAttributes, stableEdgeId);
    if (rawEdgeIds.some((rawEdgeId) => stableEdgeIds.has(rawEdgeId))) {
      displayEdgeIds.add(stableEdgeId);
    }
  });

  return Array.from(displayEdgeIds);
}

export function collectInteractionRefreshTargets(
  graphRef: typeof graph | Graph<NodeAttributes, EdgeAttributes>,
  previousState: GraphInteractionState | null,
  nextState: GraphInteractionState,
): { nodes: string[]; edges: string[] } {
  const nodeIds = new Set<string>();
  const edgeKeys = new Set<string>();

  collectImpactedNodeIds(graphRef, previousState).forEach((nodeId) => nodeIds.add(nodeId));
  collectImpactedNodeIds(graphRef, nextState).forEach((nodeId) => nodeIds.add(nodeId));
  collectImpactedEdgeKeys(graphRef, previousState).forEach((edgeId) => edgeKeys.add(edgeId));
  collectImpactedEdgeKeys(graphRef, nextState).forEach((edgeId) => edgeKeys.add(edgeId));

  return {
    nodes: Array.from(nodeIds).filter((nodeId) => graphRef.hasNode(nodeId)),
    edges: resolveDisplayEdgeIds(graphRef, edgeKeys),
  };
}

function logGroupedGraphSkip(kind: "focus" | "neighbors", graphRef: GraphRef, nodeId: string) {
  if (!DEBUG_GRAPH_SCENE_STATE || !nodeId.startsWith(COMMUNITY_NODE_PREFIX)) {
    return;
  }

  console.debug("[graphSceneState]", `${kind}-skipped-missing-display-node`, {
    nodeId,
    order: graphRef.order,
    size: graphRef.size,
  });
}

export function getEdgeWeightBetweenInGraph(graphRef: GraphRef, source: string, target: string): number {
  let weight = 0;

  forEachDirectedEdgeBetween(graphRef, source, target, (_edgeId, attrs) => {
    weight = Math.max(weight, Number(attrs?.weight ?? 0));
  });

  forEachDirectedEdgeBetween(graphRef, target, source, (_edgeId, attrs) => {
    weight = Math.max(weight, Number(attrs?.weight ?? 0));
  });

  return weight;
}

export function getEdgeWeightBetween(source: string, target: string): number {
  return getEdgeWeightBetweenInGraph(graph, source, target);
}

export function rankNeighborsInGraph(graphRef: GraphRef, nodeId: string): string[] {
  if (!nodeId || !graphRef.hasNode(nodeId)) {
    logGroupedGraphSkip("neighbors", graphRef, nodeId);
    return [];
  }

  return graphRef
    .neighbors(nodeId)
    .map((neighborId) => ({
      id: neighborId,
      weight: getEdgeWeightBetweenInGraph(graphRef, nodeId, neighborId),
      degree: graphRef.hasNode(neighborId) ? graphRef.degree(neighborId) : 0,
    }))
    .sort((left, right) => {
      if (right.weight !== left.weight) {
        return right.weight - left.weight;
      }
      if (right.degree !== left.degree) {
        return right.degree - left.degree;
      }
      return left.id.localeCompare(right.id);
    })
    .map((item) => item.id);
}

export function rankNeighbors(nodeId: string): string[] {
  return rankNeighborsInGraph(graph, nodeId);
}

export function buildFocusSetInGraph(graphRef: GraphRef, nodeId: string): Set<string> {
  if (!nodeId || !graphRef.hasNode(nodeId)) {
    logGroupedGraphSkip("focus", graphRef, nodeId);
    return new Set<string>();
  }

  const ranked = rankNeighborsInGraph(graphRef, nodeId).slice(0, MAX_FOCUS_NEIGHBORS);
  return new Set<string>([nodeId, ...ranked]);
}

export function buildFocusSet(nodeId: string): Set<string> {
  return buildFocusSetInGraph(graph, nodeId);
}

export function isEdgeInteractable(
  graphRef: GraphRef,
  interactionState: GraphInteractionState,
  edgeId: string,
  source: string,
  target: string,
  attrs: EdgeAttributes,
): boolean {
  const pathEdgeIds = buildPathEdgeSet(graphRef, interactionState.activePath, interactionState.activePathEdgeIds);
  if (pathEdgeIds.has(edgeId) || interactionState.selectedEdgeId === edgeId) {
    return true;
  }

  if (attrs.isAggregated && (interactionState.viewMode === "grouped" || interactionState.zoomTier === "inspection")) {
    return true;
  }

  const primaryNodeId = interactionState.selectedNodeId;
  if (primaryNodeId && graphRef.hasNode(primaryNodeId)) {
    if (source === primaryNodeId || target === primaryNodeId) {
      return true;
    }

    const focusIds = buildFocusSetInGraph(graphRef, primaryNodeId);
    return focusIds.has(source) && focusIds.has(target);
  }

  if (interactionState.zoomTier !== "inspection") {
    return false;
  }

  return Number(attrs.visualPriority ?? 0) >= GRAPH_THEME.zoomTiers[interactionState.zoomTier].edgePriorityThreshold;
}

function resolveNodeColor(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphNodeVisualState,
  attrs: NodeAttributes,
  cameraRatio: number,
  fallbackColor?: string,
) {
  const semanticColor = String(attrs.baseColor || fallbackColor || theme.palette.semantic[0]);
  const isCommunityGroup = Boolean(attrs.isCommunityGroup);
  const overviewTint = state === "neighbor"
    ? theme.palette.overview.nodeTintMix + 0.09
    : theme.palette.overview.nodeTintMix;
  const overviewCore = blendHex(
    theme.palette.overview.nodeCore,
    semanticColor,
    Math.min(0.74, theme.palette.overview.nodeCoreMix + overviewTint),
  );

  switch (theme.nodes.states[state].color) {
    case "selected":
      return theme.palette.accent.selected;
    case "hovered":
      return theme.palette.accent.hovered;
    case "path":
      return theme.palette.accent.path;
    case "muted":
      return zoomTier === "overview"
        ? withAlpha(theme.palette.overview.nodeMuted, 0.42)
        : String(attrs.mutedColor || withAlpha(semanticColor, theme.nodes.mutedAlpha));
    case "base":
    default:
      if (zoomTier === "overview") {
        const presenceBoost = getOverviewPresenceBoost(cameraRatio);
        const boostedCore = blendHex(overviewCore, semanticColor, 0.3 + 0.26 * presenceBoost);
        const overviewAlpha = Math.min(
          0.98,
          theme.palette.overview.nodeCoreAlpha + presenceBoost * 0.18,
        );
        return withAlpha(
          boostedCore,
          isCommunityGroup ? Math.min(overviewAlpha, theme.grouped.style.fillAlpha) : overviewAlpha,
        );
      }
      return isCommunityGroup ? withAlpha(semanticColor, theme.grouped.style.fillAlpha) : semanticColor;
  }
}

function resolveNodeShellColor(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphNodeVisualState,
  attrs: NodeAttributes,
  cameraRatio: number,
  fallbackColor?: string,
) {
  const semanticColor = String(attrs.baseColor || fallbackColor || theme.palette.semantic[0]);
  const isCommunityGroup = Boolean(attrs.isCommunityGroup);
  const presenceBoost = getOverviewPresenceBoost(cameraRatio);
  const overviewShell = blendHex(
    theme.palette.overview.nodeBase,
    semanticColor,
    (state === "neighbor" ? 0.02 : 0.012) + presenceBoost * 0.024,
  );

  if (zoomTier !== "overview") {
    return withAlpha(
      blendHex(theme.palette.overview.nodeBase, semanticColor, 0.26),
      isCommunityGroup ? theme.grouped.style.shellAlpha : 0.95,
    );
  }

  if (state === "selected") {
    return withAlpha(blendHex(theme.palette.overview.nodeBase, theme.palette.accent.selected, 0.05), 0.98);
  }

  if (state === "hovered") {
    return withAlpha(blendHex(theme.palette.overview.nodeBase, theme.palette.accent.hovered, 0.06), 0.98);
  }

  if (state === "path") {
    return withAlpha(blendHex(theme.palette.overview.nodeBase, theme.palette.accent.path, 0.06), 0.97);
  }

  if (state === "muted" || state === "inactive") {
    return withAlpha(theme.palette.overview.nodeMuted, 0.22);
  }

  return withAlpha(
    overviewShell,
    isCommunityGroup ? theme.grouped.style.shellAlpha : theme.palette.overview.nodeShellAlpha,
  );
}

function resolveNodeCoreScale(
  zoomTier: GraphZoomTier,
  state: GraphNodeVisualState,
  cameraRatio: number,
) {
  const presenceBoost = getOverviewPresenceBoost(cameraRatio);
  if (zoomTier === "overview") {
    switch (state) {
      case "selected":
        return 0.34 + presenceBoost * 0.08;
      case "hovered":
        return 0.32 + presenceBoost * 0.08;
      case "path":
        return 0.28 + presenceBoost * 0.07;
      case "neighbor":
        return 0.2 + presenceBoost * 0.06;
      case "muted":
      case "inactive":
        return 0.08 + presenceBoost * 0.03;
      case "default":
      default:
        return 0.16 + presenceBoost * 0.08;
    }
  }

  switch (state) {
    case "selected":
      return 0.52;
    case "hovered":
      return 0.48;
    case "path":
      return 0.44;
    case "neighbor":
      return 0.3;
    case "muted":
    case "inactive":
      return 0.1;
    case "default":
    default:
      return zoomTier === "structure" ? 0.22 : 0.28;
  }
}

function resolveEdgeColor(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphEdgeVisualState,
  attrs: EdgeAttributes,
  fallbackColor?: string,
) {
  const defaultInspectionColor = zoomTier === "overview"
    ? theme.palette.overview.edgeInspection
    : theme.palette.muted.edgeInspection;
  const baseColor = String(attrs.baseColor || fallbackColor || defaultInspectionColor);

  switch (theme.edges.states[state].color) {
    case "hover":
      return theme.palette.accent.hovered;
    case "path":
      return theme.palette.accent.path;
    case "backbone":
      return zoomTier === "overview"
        ? theme.palette.overview.edgeBackbone
        : theme.palette.muted.edgeFocus;
    case "focus":
      return theme.palette.muted.edgeFocus;
    case "overview":
      return theme.palette.muted.edgeOverview;
    case "structure":
      return zoomTier === "overview"
        ? theme.palette.overview.edgeStructure
        : theme.palette.muted.edgeStructure;
    case "inspection":
      return zoomTier === "overview"
        ? theme.palette.overview.edgeInspection
        : theme.palette.muted.edgeInspection;
    case "muted":
      return zoomTier === "overview"
        ? theme.palette.overview.edgeStructure
        : String(attrs.mutedColor || theme.palette.muted.edgeOverview);
    default:
      return baseColor;
  }
}

function resolveNodeRingColor(
  theme: GraphTheme,
  state: GraphNodeVisualState,
  attrs: NodeAttributes,
) {
  if (state === "selected") {
    return attrs.ringColor || theme.nodes.selectedRing.color;
  }
  if (state === "hovered") {
    return theme.palette.accent.hovered;
  }
  if (state === "path") {
    return theme.palette.accent.path;
  }

  return undefined;
}

function resolveNodeRingSize(
  theme: GraphTheme,
  state: GraphNodeVisualState,
  zoomTier: GraphZoomTier,
) {
  if (state === "selected" && zoomTierAtLeast(zoomTier, theme.nodes.selectedRing.visibleFrom)) {
    return theme.nodes.selectedRing.nativeSize;
  }
  if (state === "hovered") {
    return Math.max(1.45, theme.nodes.selectedRing.nativeSize - 0.35);
  }
  if (state === "path") {
    return Math.max(1.2, theme.nodes.selectedRing.nativeSize - 0.55);
  }

  return 0;
}

export function resolveNodeVisualState(
  nodeId: string,
  zoomTier: GraphZoomTier,
  hoveredNodeId: string | null,
  selectedNodeId: string,
  selectedEdgeId: string,
  focusIds: Set<string>,
  edgeEndpointIds: Set<string>,
  pathNodeIds: Set<string>,
): GraphNodeVisualState {
  if (hoveredNodeId && nodeId === hoveredNodeId) {
    return "hovered";
  }
  if (selectedNodeId && nodeId === selectedNodeId) {
    return "selected";
  }
  if (pathNodeIds.has(nodeId)) {
    return "path";
  }
  if (focusIds.has(nodeId)) {
    return "neighbor";
  }
  if (edgeEndpointIds.has(nodeId)) {
    return "neighbor";
  }
  if (hoveredNodeId || selectedNodeId || selectedEdgeId || pathNodeIds.size > 0) {
    if (zoomTier !== "inspection") {
      return "default";
    }
    return "muted";
  }
  return "default";
}

export function resolveEdgeVisualState(
  edgeId: string,
  source: string,
  target: string,
  zoomTier: GraphZoomTier,
  hoveredNodeId: string | null,
  selectedNodeId: string,
  selectedEdgeId: string,
  focusIds: Set<string>,
  pathEdgeIds: Set<string>,
  overviewBackboneEdgeIds: Set<string>,
): GraphEdgeVisualState {
  const primaryNodeId = hoveredNodeId || selectedNodeId;

  if (pathEdgeIds.has(edgeId)) {
    return "path";
  }

  if (selectedEdgeId && edgeId === selectedEdgeId) {
    return "selected";
  }

  if (primaryNodeId && (source === primaryNodeId || target === primaryNodeId)) {
    return hoveredNodeId ? "hovered" : "selected";
  }

  if (zoomTier !== "overview" && focusIds.has(source) && focusIds.has(target)) {
    return "neighbor";
  }

  if (zoomTier === "overview" && overviewBackboneEdgeIds.has(edgeId)) {
    return "backbone";
  }

  if (hoveredNodeId || selectedNodeId || selectedEdgeId || pathEdgeIds.size > 0) {
    return "muted";
  }

  if (zoomTier === "overview") {
    return "inactive";
  }

  return "default";
}

export function resolveNodeVariant(state: GraphNodeVisualState, attrs: NodeAttributes): GraphNodeShapeVariant {
  if (state === "selected") {
    return "selected";
  }

  return attrs.nodeShapeVariant || attrs.nodeVariant || "default";
}

export function resolveEdgeVariant(state: GraphEdgeVisualState, attrs: EdgeAttributes): GraphEdgeVariant {
  if (state === "path") {
    return "pathSignal";
  }

  if (attrs.bundleKind === "community") {
    return "line";
  }

  if ((attrs.parallelCount ?? 1) > 1) {
    return "parallelCurve";
  }

  if (attrs.edgeVariant) {
    return attrs.edgeVariant;
  }

  if (attrs.isBidirectional) {
    return "bidirectionalCurve";
  }

  if (attrs.arrowVisibilityPolicy === "contextual") {
    return "directional";
  }

  return "line";
}

export function shouldForceNodeLabel(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphNodeVisualState,
  attrs: NodeAttributes,
  labelPriority: number,
): boolean {
  const tierConfig = theme.zoomTiers[zoomTier];
  const forceVisibleState = theme.labels.forceVisibleStates.includes(state);
  const policy = attrs.labelVisibilityPolicy || "priority";

  if (forceVisibleState || theme.nodes.states[state].forceLabel) {
    return true;
  }

  switch (policy as GraphLabelVisibilityPolicy) {
    case "always":
      return true;
    case "local":
      return zoomTier !== "overview" && state !== "default" && state !== "muted" && state !== "inactive";
    case "priority":
      return labelPriority >= tierConfig.labelThreshold;
    case "none":
    default:
      return false;
  }
}

function resolveNodeBorderColor(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphNodeVisualState,
  variant: GraphNodeShapeVariant,
  attrs: NodeAttributes,
  baseColor: string,
) {
  if (state === "selected" || variant === "selected") {
    return attrs.ringColor || theme.nodes.selectedRing.color;
  }
  if (state === "hovered") {
    return theme.palette.accent.hovered;
  }
  if (state === "path") {
    return theme.palette.accent.path;
  }
  if (state === "muted" || state === "inactive") {
    return withAlpha(
      attrs.strokeColor || attrs.borderColor || theme.palette.overview.nodeBorder || theme.palette.background.nodeBorder,
      zoomTier === "overview" ? 0.26 : 0.7,
    );
  }

  if (variant === "temporal") {
    return theme.palette.accent.temporal;
  }
  if (variant === "provenance") {
    return theme.palette.accent.provenance;
  }
  if (variant === "inferred") {
    return theme.palette.accent.inferred;
  }

  if (zoomTier === "overview") {
    return withAlpha(
      blendHex(theme.palette.overview.nodeBorder, baseColor, state === "neighbor" ? 0.08 : 0.03),
      state === "neighbor" ? 0.24 : 0.06,
    );
  }

  return attrs.strokeColor || attrs.borderColor || theme.palette.background.nodeBorder || baseColor;
}

export function resolveNodeElementStyle(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphNodeVisualState,
  attrs: NodeAttributes,
  label: string,
  cameraRatio = 1,
): ResolvedNodeStyle {
  const tierConfig = theme.zoomTiers[zoomTier];
  const stateConfig = theme.nodes.states[state];
  const nodeVariant = resolveNodeVariant(state, attrs);
  const variantConfig = theme.nodes.variants[nodeVariant];
  const isCommunityGroup = Boolean(attrs.isCommunityGroup);
  const baseSize = Number(attrs.baseSize || attrs.size || 4);
  const labelPriority = Number(attrs.labelPriority ?? 0);
  const color = resolveNodeColor(theme, zoomTier, state, attrs, cameraRatio, attrs.color);
  const shellColor = resolveNodeShellColor(theme, zoomTier, state, attrs, cameraRatio, attrs.color);
  const sizeMultiplier = (state === "default" ? tierConfig.nodeScale : stateConfig.sizeMultiplier)
    * variantConfig.sizeMultiplier
    * (isCommunityGroup ? theme.grouped.style.nodeSizeScale : 1);
  const overviewPresence = zoomTier === "overview" ? 1 + getOverviewPresenceBoost(cameraRatio) * 1.2 : 1;
  const forceLabel = shouldForceNodeLabel(theme, zoomTier, state, attrs, labelPriority);
  const badgeKind = attrs.badgeKind || variantConfig.badgeKind;
  const forceVisibleState = theme.labels.forceVisibleStates.includes(state);
  const showBadge = Boolean(
    badgeKind
    && (forceVisibleState || (tierConfig.showBadges && zoomTierAtLeast(zoomTier, variantConfig.badgeVisibleFrom)))
    && state !== "muted"
    && state !== "inactive",
  );
  const ringSize = resolveNodeRingSize(theme, state, zoomTier);
  const ringColor = resolveNodeRingColor(theme, state, attrs);
  const showRing = ringSize > 0;
  const showHalo = state === "hovered" || state === "selected" || state === "path";
  const strokeBase = state === "muted" || state === "inactive"
    ? theme.nodes.strokeHierarchy[zoomTier].muted
    : forceVisibleState
      ? theme.nodes.strokeHierarchy[zoomTier].emphasis
      : theme.nodes.strokeHierarchy[zoomTier].base;

  return {
    color,
    shellColor,
    coreScale: resolveNodeCoreScale(zoomTier, state, cameraRatio),
    size: Math.max(baseSize * sizeMultiplier * overviewPresence, stateConfig.minSize),
    forceLabel,
    label: forceLabel ? label : "",
    zIndex: forceLabel && stateConfig.zIndex === 0 ? 1 : stateConfig.zIndex,
    hidden: false,
    borderColor: resolveNodeBorderColor(theme, zoomTier, state, nodeVariant, attrs, color),
    borderSize: Math.max(
      0.4,
      Number(attrs.borderSize ?? 0.85)
        + strokeBase
        + stateConfig.borderBoost
        + variantConfig.borderBoost
        + (isCommunityGroup ? theme.grouped.style.nodeBorderBoost : 0)
        - 0.8,
    ),
    nodeVariant,
    badgeKind,
    badgeCount: attrs.badgeCount,
    showBadge,
    showRing,
    ringColor,
    ringSize,
    showHalo,
    haloColor: attrs.haloColor || attrs.glowColor || withAlpha(
      color,
      (isCommunityGroup ? theme.grouped.style.glowAlpha : theme.overlays.hoverGlowAlpha) + variantConfig.haloBoost,
    ),
  };
}

function resolveStraightEdgeType(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphEdgeVisualState,
  variant: GraphEdgeVariant,
  attrs: EdgeAttributes,
): "line" | "arrow" {
  const variantConfig = theme.edges.variants[variant];

  if (theme.edges.states[state].forceArrow || variantConfig.arrowPolicy === "always") {
    return "arrow";
  }

  if (variantConfig.arrowPolicy === "contextual" && theme.zoomTiers[zoomTier].showContextualArrows) {
    return "arrow";
  }

  if (state !== "default") {
    return (attrs.type as "line" | "arrow" | undefined) || variantConfig.baseType;
  }

  return Number(attrs.visualPriority ?? 0) >= theme.zoomTiers[zoomTier].arrowPriorityThreshold && theme.zoomTiers[zoomTier].showContextualArrows
    ? "arrow"
    : "line";
}

function resolveEdgeCurvature(
  theme: GraphTheme,
  state: GraphEdgeVisualState,
  edgeVariant: GraphEdgeVariant,
  attrs: EdgeAttributes,
  sourceId: string | undefined,
  targetId: string | undefined,
) {
  const variantConfig = theme.edges.variants[edgeVariant];
  const baseCurvature = edgeVariant === "line" && state === "selected"
    ? Math.max(variantConfig.curveStrength, 0.14)
    : variantConfig.curveStrength;

  if (baseCurvature === 0) {
    return 0;
  }

  if (typeof attrs.parallelCount === "number" && attrs.parallelCount > 1 && typeof attrs.parallelIndex === "number") {
    const center = (attrs.parallelCount - 1) / 2;
    return (attrs.parallelIndex - center) * baseCurvature;
  }

  if ((edgeVariant === "bidirectionalCurve" || edgeVariant === "parallelCurve" || attrs.isBidirectional) && sourceId && targetId) {
    return sourceId.localeCompare(targetId) <= 0 ? baseCurvature : -baseCurvature;
  }

  return baseCurvature;
}

export function resolveEdgeElementStyle(
  theme: GraphTheme,
  zoomTier: GraphZoomTier,
  state: GraphEdgeVisualState,
  attrs: EdgeAttributes,
  sourceId?: string,
  targetId?: string,
): ResolvedEdgeStyle {
  const tierConfig = theme.zoomTiers[zoomTier];
  const stateConfig = theme.edges.states[state];
  const edgeVariant = resolveEdgeVariant(state, attrs);
  const variantConfig = theme.edges.variants[edgeVariant];
  const isCommunityBundle = attrs.bundleKind === "community";
  const baseSize = Number(attrs.baseSize || attrs.size || 0.9);
  const visualPriority = Number(attrs.visualPriority ?? 0);
  const belowPriorityThreshold = state === "default"
    && visualPriority < tierConfig.edgePriorityThreshold
    && edgeVariant === "line";

  if (stateConfig.hide || belowPriorityThreshold) {
    return {
      hidden: true,
      zIndex: 0,
      edgeVariant,
      arrowVisibilityPolicy: variantConfig.arrowPolicy,
      curveStrength: variantConfig.curveStrength,
      curvature: 0,
    };
  }

  const sizeMultiplier = (state === "default" ? tierConfig.edgeSizeScale : stateConfig.sizeMultiplier) * variantConfig.sizeMultiplier;
  const straightType = resolveStraightEdgeType(theme, zoomTier, state, edgeVariant, attrs);
  const useCurvedRenderer = tierConfig.showCurves
    && zoomTier !== "overview"
    && (
      edgeVariant === "pathSignal"
      || state === "selected"
      || ((state === "neighbor" || state === "hovered") && (edgeVariant === "bidirectionalCurve" || edgeVariant === "parallelCurve"))
    );
  const curvature = useCurvedRenderer
    ? resolveEdgeCurvature(theme, state, edgeVariant, attrs, sourceId, targetId)
    : 0;

  return {
    hidden: false,
    type: useCurvedRenderer
      ? (straightType === "arrow" ? "curvedArrow" : "curve")
      : straightType,
    color: isCommunityBundle
      ? withAlpha(resolveEdgeColor(theme, zoomTier, state, attrs, attrs.color), theme.grouped.style.edgeAlpha)
      : resolveEdgeColor(theme, zoomTier, state, attrs, attrs.color),
    size: Math.max(
      baseSize * sizeMultiplier * (isCommunityBundle ? theme.grouped.style.edgeSizeScale : 1),
      stateConfig.minSize,
    ),
    zIndex: stateConfig.zIndex,
    edgeVariant,
    arrowVisibilityPolicy: variantConfig.arrowPolicy,
    curveStrength: variantConfig.curveStrength,
    curvature,
  };
}

function addNodeIfMissing(targetGraph: GraphRef, nodeId: string, attrs: NodeAttributes) {
  if (!targetGraph.hasNode(nodeId)) {
    targetGraph.addNode(nodeId, attrs);
  }
}

function truncateGroupedLabel(label: string | null | undefined): string {
  const value = String(label || "").trim();
  if (value.length <= 22) {
    return value;
  }
  return `${value.slice(0, 21).trimEnd()}…`;
}

function estimateGroupedRingCapacity(radius: number): number {
  const circumference = 2 * Math.PI * Math.max(radius, 1);
  return Math.max(6, Math.floor(circumference / GRAPH_THEME.grouped.initialLayout.minNodeSpacing));
}

function getGroupedCommunityNodeSize(memberCount: number): number {
  return Math.max(16, 10 + Math.log2(memberCount + 1) * 4.6);
}

function assignGroupedCommunityPositions(
  communities: Array<{
    communityId: number;
    memberCount: number;
    centralityScore: number;
    connectivityWeight: number;
    radius: number;
  }>,
): Map<number, {
  x: number;
  y: number;
  labelPriority: number;
  visualPriority: number;
}> {
  const positioned = new Map<number, {
    x: number;
    y: number;
    labelPriority: number;
    visualPriority: number;
  }>();
  const ranked = communities
    .slice()
    .sort((left, right) => {
      const leftProminence = Math.log2(left.memberCount + 1) * 2.2 + Math.log2(left.connectivityWeight + 1) * 1.6 + left.centralityScore * 5;
      const rightProminence = Math.log2(right.memberCount + 1) * 2.2 + Math.log2(right.connectivityWeight + 1) * 1.6 + right.centralityScore * 5;
      if (rightProminence !== leftProminence) {
        return rightProminence - leftProminence;
      }
      return left.communityId - right.communityId;
    });

  if (ranked.length === 0) {
    return positioned;
  }

  const seeded = new Map<number, { x: number; y: number }>();

  const primaryLabelCount = Math.min(GRAPH_THEME.grouped.initialLayout.primaryLabelCount, ranked.length);
  const normalizedVisual = (index: number) => Math.max(0.24, 1.24 - index * 0.055);
  const normalizedLabel = (index: number) => (index < primaryLabelCount ? Math.max(1.02, 1.42 - index * 0.05) : 0.56);

  const centerPosition = {
    x: 0,
    y: 0,
  };
  seeded.set(ranked[0].communityId, centerPosition);
  positioned.set(ranked[0].communityId, {
    ...centerPosition,
    labelPriority: normalizedLabel(0),
    visualPriority: normalizedVisual(0),
  });

  let cursor = 1;
  let ring = 1;
  while (cursor < ranked.length) {
    const radius = GRAPH_THEME.grouped.initialLayout.innerRadius + (ring - 1) * GRAPH_THEME.grouped.initialLayout.ringSpacing;
    const capacity = estimateGroupedRingCapacity(radius);
    const count = Math.min(capacity, ranked.length - cursor);
    const angleOffset = ((hashString(`community-ring:${ring}`) % 360) * Math.PI) / 180;

    for (let index = 0; index < count; index += 1) {
      const entry = ranked[cursor + index];
      const angle = angleOffset + (Math.PI * 2 * index) / count;
      const seedPosition = {
        x: Number((radius * Math.cos(angle)).toFixed(3)),
        y: Number((radius * Math.sin(angle)).toFixed(3)),
      };
      seeded.set(entry.communityId, seedPosition);
      positioned.set(entry.communityId, {
        ...seedPosition,
        labelPriority: normalizedLabel(cursor + index),
        visualPriority: normalizedVisual(cursor + index),
      });
    }

    cursor += count;
    ring += 1;
  }

  for (let iteration = 0; iteration < GRAPH_THEME.grouped.initialLayout.overlapIterations; iteration += 1) {
    let moved = false;

    for (let leftIndex = 0; leftIndex < ranked.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < ranked.length; rightIndex += 1) {
        const leftCommunity = ranked[leftIndex];
        const rightCommunity = ranked[rightIndex];
        const leftPosition = positioned.get(leftCommunity.communityId);
        const rightPosition = positioned.get(rightCommunity.communityId);
        if (!leftPosition || !rightPosition) {
          continue;
        }

        let dx = rightPosition.x - leftPosition.x;
        let dy = rightPosition.y - leftPosition.y;
        let distance = Math.hypot(dx, dy);
        if (distance < 0.001) {
          const angle = ((hashString(`grouped-collision:${leftCommunity.communityId}:${rightCommunity.communityId}`) % 360) * Math.PI) / 180;
          dx = Math.cos(angle);
          dy = Math.sin(angle);
          distance = 1;
        }

        const minimumDistance = leftCommunity.radius + rightCommunity.radius + GRAPH_THEME.grouped.initialLayout.nodePadding;
        if (distance >= minimumDistance) {
          continue;
        }

        const overlap = minimumDistance - distance;
        const ux = dx / distance;
        const uy = dy / distance;
        const leftMobility = rightCommunity.radius / (leftCommunity.radius + rightCommunity.radius);
        const rightMobility = leftCommunity.radius / (leftCommunity.radius + rightCommunity.radius);

        leftPosition.x -= ux * overlap * 0.52 * leftMobility;
        leftPosition.y -= uy * overlap * 0.52 * leftMobility;
        rightPosition.x += ux * overlap * 0.52 * rightMobility;
        rightPosition.y += uy * overlap * 0.52 * rightMobility;
        moved = true;
      }
    }

    ranked.forEach((community) => {
      const position = positioned.get(community.communityId);
      const seedPosition = seeded.get(community.communityId);
      if (!position || !seedPosition) {
        return;
      }
      position.x += (seedPosition.x - position.x) * 0.08;
      position.y += (seedPosition.y - position.y) * 0.08;
    });

    if (!moved) {
      break;
    }
  }

  return positioned;
}

function buildCollapsedNeighborhoodState(
  nodeId: string,
  activePath: string[],
): Pick<GraphDisplayStateSnapshot, "selectedVisibleNeighborIds" | "selectedCollapsedNeighborIds"> {
  if (!nodeId || !graph.hasNode(nodeId)) {
    return {
      selectedVisibleNeighborIds: [],
      selectedCollapsedNeighborIds: [],
    };
  }

  const rankedNeighbors = rankNeighbors(nodeId);
  const forcedVisible = new Set(activePath.filter((candidateId) => candidateId !== nodeId && graph.hasNode(candidateId)));
  const visible = new Set<string>();
  rankedNeighbors.forEach((neighborId, index) => {
    if (index < COLLAPSE_VISIBLE_NEIGHBORS || forcedVisible.has(neighborId)) {
      visible.add(neighborId);
    }
  });

  return {
    selectedVisibleNeighborIds: Array.from(visible),
    selectedCollapsedNeighborIds: rankedNeighbors.filter((neighborId) => !visible.has(neighborId)),
  };
}

function createCollapsedNeighborhoodGraph(
  nodeId: string,
  activePath: string[],
): Graph<NodeAttributes, EdgeAttributes> {
  const collapsedState = buildCollapsedNeighborhoodState(nodeId, activePath);
  const hiddenNeighbors = new Set(collapsedState.selectedCollapsedNeighborIds);
  if (hiddenNeighbors.size === 0) {
    return graph.copy() as Graph<NodeAttributes, EdgeAttributes>;
  }

  const collapsedGraph = graph.copy() as Graph<NodeAttributes, EdgeAttributes>;
  hiddenNeighbors.forEach((neighborId) => {
    if (!collapsedGraph.hasNode(neighborId)) {
      return;
    }

    const incidentEdges = collapsedGraph.edges(neighborId).map((edgeId) => String(edgeId));
    incidentEdges.forEach((edgeId) => {
      if (!collapsedGraph.hasEdge(edgeId)) {
        return;
      }
      const [sourceId, targetId] = collapsedGraph.extremities(edgeId);
      const touchesSelectedPair =
        (sourceId === nodeId && targetId === neighborId)
        || (sourceId === neighborId && targetId === nodeId);
      if (touchesSelectedPair) {
        collapsedGraph.dropEdge(edgeId);
      }
    });

    if (collapsedGraph.hasNode(neighborId) && collapsedGraph.degree(neighborId) === 0) {
      collapsedGraph.dropNode(neighborId);
    }
  });

  return collapsedGraph;
}

type FocusedNeighborZone = "primary" | "secondary";

type FocusedNeighborEntry = {
  id: string;
  attrs: NodeAttributes;
  isPath: boolean;
  zone: FocusedNeighborZone;
  weight: number;
  degree: number;
  score: number;
  labelPriority: number;
  radius: number;
  x: number;
  y: number;
  size: number;
};

const FOCUS_PRIMARY_ANCHOR_DEGREES = [-90, -18, 42, 110, 180, -150, -72];
const FOCUS_SECONDARY_ANCHOR_DEGREES = [-56, -6, 54, 122, 174, -140, -92, -34, 90, 146];

function angleDegreesToRadians(angle: number) {
  return (angle * Math.PI) / 180;
}

function getAnchoredAngles(count: number, anchorDegrees: readonly number[]): number[] {
  if (count <= 0) {
    return [];
  }
  if (count <= anchorDegrees.length) {
    return anchorDegrees.slice(0, count).map(angleDegreesToRadians);
  }
  return Array.from({ length: count }, (_value, index) => ((Math.PI * 2 * index) / count) - Math.PI / 2);
}

function seedFocusedRing(
  entries: FocusedNeighborEntry[],
  radius: number,
  anchorDegrees: readonly number[],
) {
  const anchors = getAnchoredAngles(entries.length, anchorDegrees);
  entries.forEach((entry, index) => {
    const angle = anchors[index] ?? ((Math.PI * 2 * index) / Math.max(entries.length, 1)) - Math.PI / 2;
    entry.radius = radius;
    entry.x = Math.cos(angle) * radius;
    entry.y = Math.sin(angle) * radius;
  });
}

function relaxFocusedNeighborPositions(
  entries: FocusedNeighborEntry[],
  selectedRadius: number,
) {
  if (entries.length === 0) {
    return;
  }

  const iterations = GRAPH_THEME.focus.overlapIterations;
  const padding = GRAPH_THEME.focus.overlapPadding;
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    for (let leftIndex = 0; leftIndex < entries.length; leftIndex += 1) {
      const left = entries[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < entries.length; rightIndex += 1) {
        const right = entries[rightIndex];
        const dx = right.x - left.x;
        const dy = right.y - left.y;
        const distance = Math.hypot(dx, dy) || 0.001;
        const minimumDistance = (left.size / 2) + (right.size / 2) + padding;
        if (distance >= minimumDistance) {
          continue;
        }

        const overlap = minimumDistance - distance;
        const ux = dx / distance;
        const uy = dy / distance;
        const shift = overlap * 0.5;
        left.x -= ux * shift;
        left.y -= uy * shift;
        right.x += ux * shift;
        right.y += uy * shift;
      }
    }

    entries.forEach((entry) => {
      const distanceFromCenter = Math.hypot(entry.x, entry.y) || 0.001;
      const centerMinimum = selectedRadius + (entry.size / 2) + padding * 0.8;
      if (distanceFromCenter < centerMinimum) {
        const push = centerMinimum - distanceFromCenter;
        entry.x += (entry.x / distanceFromCenter) * push;
        entry.y += (entry.y / distanceFromCenter) * push;
      }

      const desiredRadius = entry.radius;
      if (desiredRadius > 0) {
        const drift = desiredRadius - Math.hypot(entry.x, entry.y);
        const currentDistance = Math.hypot(entry.x, entry.y) || 0.001;
        entry.x += (entry.x / currentDistance) * drift * 0.1;
        entry.y += (entry.y / currentDistance) * drift * 0.1;
      }
    });
  }
}

function buildFocusedNeighbors(
  nodeId: string,
  visibleNeighborIds: string[],
  rankedNeighbors: string[],
  pathNodeIds: Set<string>,
): FocusedNeighborEntry[] {
  const rankedIndex = new Map(rankedNeighbors.map((neighborId, index) => [neighborId, index]));
  const neighbors = visibleNeighborIds
    .map((neighborId) => {
      const attrs = graph.getNodeAttributes(neighborId) as NodeAttributes;
      const weight = getEdgeWeightBetween(nodeId, neighborId);
      const degree = graph.hasNode(neighborId) ? graph.degree(neighborId) : 0;
      const rank = rankedIndex.get(neighborId) ?? rankedNeighbors.length;
      const isPath = pathNodeIds.has(neighborId);
      const score = (isPath ? 10_000 : 0) + (weight * 100) + (degree * 2) + Math.max(0, MAX_FOCUS_NEIGHBORS - rank);
      return {
        id: neighborId,
        attrs,
        isPath,
        zone: "secondary" as FocusedNeighborZone,
        weight,
        degree,
        score,
        labelPriority: 0,
        radius: 0,
        x: 0,
        y: 0,
        size: Math.max(Number(attrs.baseSize ?? attrs.size ?? 4), 1),
      };
    })
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return left.id.localeCompare(right.id);
    });

  const primaryTarget = Math.min(
    GRAPH_THEME.focus.primaryRingSlots,
    Math.max(FOCUS_PRIMARY_LABELS, Math.ceil(neighbors.length * 0.45)),
  );
  let primaryCount = 0;
  neighbors.forEach((entry) => {
    if (primaryCount < primaryTarget || entry.isPath) {
      entry.zone = "primary";
      primaryCount += 1;
    }
  });

  const primaryEntries = neighbors.filter((entry) => entry.zone === "primary");
  const secondaryEntries = neighbors.filter((entry) => entry.zone === "secondary");
  seedFocusedRing(primaryEntries, GRAPH_THEME.focus.primaryRadius, FOCUS_PRIMARY_ANCHOR_DEGREES);
  seedFocusedRing(secondaryEntries, GRAPH_THEME.focus.secondaryRadius, FOCUS_SECONDARY_ANCHOR_DEGREES);

  neighbors.forEach((entry, index) => {
    const primaryLabelBoost = entry.zone === "primary" && index < FOCUS_PRIMARY_LABELS;
    entry.labelPriority = entry.isPath || primaryLabelBoost ? 1.15 : entry.zone === "primary" ? 0.7 : 0.35;
    entry.size = entry.isPath
      ? Math.max(Number(entry.attrs.baseSize ?? entry.attrs.size ?? 4) * 1.16, GRAPH_THEME.focus.primaryNeighborMinSize)
      : entry.zone === "primary"
        ? Math.max(Number(entry.attrs.baseSize ?? entry.attrs.size ?? 4) * 1.08, GRAPH_THEME.focus.primaryNeighborMinSize)
        : Math.max(Number(entry.attrs.baseSize ?? entry.attrs.size ?? 4) * 0.86, GRAPH_THEME.focus.secondaryNeighborMinSize);
  });

  relaxFocusedNeighborPositions(neighbors, GRAPH_THEME.focus.selectedMinSize);
  return neighbors;
}

function scoreFocusedSupportEdge(
  attrs: EdgeAttributes,
  sourceId: string,
  targetId: string,
  primaryNeighborIds: Set<string>,
) {
  const rawEdgeCount = collectRawEdgeIds(attrs).length;
  const weight = Number(attrs.representativeWeight ?? attrs.weight ?? 1);
  const primaryBoost = primaryNeighborIds.has(sourceId) && primaryNeighborIds.has(targetId) ? 1.5 : 0;
  return weight * 4 + rawEdgeCount + primaryBoost;
}

function aggregateDisplayGraph(graphRef: GraphRef): Graph<NodeAttributes, EdgeAttributes> {
  const aggregated = new Graph<NodeAttributes, EdgeAttributes>({
    type: "directed",
    multi: true,
    allowSelfLoops: false,
  });

  graphRef.forEachNode((nodeId, attrs) => {
    aggregated.addNode(nodeId, { ...(attrs as NodeAttributes) });
  });

  const groupedEdges = new Map<string, Array<{ edgeId: string; attrs: EdgeAttributes }>>();
  graphRef.forEachEdge((edgeId, attrs, sourceId, targetId) => {
    const key = `${sourceId}→${targetId}`;
    const bucket = groupedEdges.get(key) ?? [];
    bucket.push({ edgeId: String(edgeId), attrs: attrs as EdgeAttributes });
    groupedEdges.set(key, bucket);
  });

  groupedEdges.forEach((entries, key) => {
    const [sourceId, targetId] = key.split("→");
    if (entries.length === 1) {
      const [{ edgeId, attrs }] = entries;
      aggregated.mergeDirectedEdgeWithKey(edgeId, sourceId, targetId, {
        ...attrs,
        rawEdgeIds: collectRawEdgeIds(attrs, edgeId),
        isAggregated: isAggregatedEdgeAttributes(attrs),
        aggregateCount: attrs.aggregateCount ?? collectRawEdgeIds(attrs, edgeId).length,
        dominantEdgeType: attrs.dominantEdgeType ?? attrs.edgeType,
        representativeWeight: attrs.representativeWeight ?? Number(attrs.weight ?? 1),
      });
      return;
    }

    const sorted = entries
      .slice()
      .sort((left, right) => {
        const weightDelta = Number(right.attrs.weight ?? 0) - Number(left.attrs.weight ?? 0);
        if (weightDelta !== 0) {
          return weightDelta;
        }
        const priorityDelta = Number(right.attrs.visualPriority ?? 0) - Number(left.attrs.visualPriority ?? 0);
        if (priorityDelta !== 0) {
          return priorityDelta;
        }
        return left.edgeId.localeCompare(right.edgeId);
      });
    const representative = sorted[0];
    const rawEdgeIds = entries.flatMap(({ edgeId, attrs }) => collectRawEdgeIds(attrs, edgeId));
    const typeCounts = new Map<string, number>();
    entries.forEach(({ attrs }) => {
      const edgeType = String(attrs.edgeType ?? "related_to");
      typeCounts.set(edgeType, (typeCounts.get(edgeType) ?? 0) + 1);
    });
    const dominantEdgeType = [...typeCounts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? representative.attrs.edgeType ?? "related_to";
    const reverseKey = `${targetId}→${sourceId}`;
    const isBidirectionalBundle = groupedEdges.has(reverseKey);
    const syntheticEdgeId = `${AGGREGATED_EDGE_PREFIX}${sourceId}::${targetId}`;

    aggregated.mergeDirectedEdgeWithKey(syntheticEdgeId, sourceId, targetId, {
      ...representative.attrs,
      edgeId: syntheticEdgeId,
      familyId: syntheticEdgeId,
      sourceId,
      targetId,
      rawEdgeIds,
      isAggregated: true,
      aggregateCount: rawEdgeIds.length,
      dominantEdgeType: String(dominantEdgeType),
      representativeWeight: Number(representative.attrs.weight ?? 1),
      weight: Number(representative.attrs.weight ?? 1),
      edgeType: String(representative.attrs.edgeType ?? dominantEdgeType ?? "related_to"),
      parallelCount: rawEdgeIds.length,
      familySize: rawEdgeIds.length,
      bundleKind: isBidirectionalBundle ? "bidirectional" : "parallel",
      isBidirectional: isBidirectionalBundle,
    });
  });

  return aggregated;
}

function buildCommunityGroupedGraph(): GraphDisplayResult {
  const base = computeGraphAnalyticsBase(graph, {
    computeCommunities: true,
    computeCentrality: true,
  });
  const state = createEmptyDisplayState("", true);
  state.groupedViewAvailable = base.communitiesByNode.size > 0;
  if (base.communitiesByNode.size === 0) {
    state.groupedViewReason = "Grouped view is unavailable until communities can be detected.";
    return { graph: aggregateDisplayGraph(graph), state, meta: MIRRORED_DISPLAY_META };
  }

  const grouped = new Graph<NodeAttributes, EdgeAttributes>({
    type: "directed",
    multi: true,
    allowSelfLoops: false,
  });
  const communityMembers = new Map<number, string[]>();
  graph.forEachNode((nodeId) => {
    const communityId = base.communitiesByNode.get(nodeId);
    if (communityId === undefined) {
      return;
    }
    const bucket = communityMembers.get(communityId) ?? [];
    bucket.push(nodeId);
    communityMembers.set(communityId, bucket);
  });

  const communitySummaries = new Map<number, {
    memberIds: string[];
    rankedMembers: string[];
    anchorNodeId: string | null;
    anchorAttrs: NodeAttributes | null;
    dominantSemanticGroup: string;
    color: string;
    memberCount: number;
    centralityScore: number;
  }>();

  communityMembers.forEach((memberIds, communityId) => {
    const rankedMembers = memberIds
      .slice()
      .sort((left, right) => {
        const leftScore = base.centralityByNode.get(left)?.score ?? 0;
        const rightScore = base.centralityByNode.get(right)?.score ?? 0;
        if (rightScore !== leftScore) {
          return rightScore - leftScore;
        }
        return left.localeCompare(right);
      });
    const anchorNodeId = rankedMembers[0] ?? null;
    const anchorAttrs = anchorNodeId ? (graph.getNodeAttributes(anchorNodeId) as NodeAttributes) : null;
    const semanticCounts = new Map<string, number>();
    memberIds.forEach((memberId) => {
      const memberAttrs = graph.getNodeAttributes(memberId) as NodeAttributes;
      const semanticGroup = String(memberAttrs.semanticGroup || memberAttrs.nodeType || "entity");
      semanticCounts.set(semanticGroup, (semanticCounts.get(semanticGroup) ?? 0) + 1);
    });
    const dominantSemanticGroup = [...semanticCounts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? "entity";
    const color = anchorAttrs?.baseColor || anchorAttrs?.color || GRAPH_THEME.palette.semantic[communityId % GRAPH_THEME.palette.semantic.length];
    communitySummaries.set(communityId, {
      memberIds,
      rankedMembers,
      anchorNodeId,
      anchorAttrs,
      dominantSemanticGroup,
      color,
      memberCount: memberIds.length,
      centralityScore: anchorNodeId ? (base.centralityByNode.get(anchorNodeId)?.score ?? 0) : 0,
    });
  });

  const groupedEdges = new Map<string, {
    sourceId: string;
    targetId: string;
    rawEdgeIds: string[];
    weight: number;
    typeCounts: Map<string, number>;
  }>();

  graph.forEachEdge((edgeId, attrs, sourceId, targetId) => {
    const sourceCommunity = base.communitiesByNode.get(sourceId);
    const targetCommunity = base.communitiesByNode.get(targetId);
    if (sourceCommunity === undefined || targetCommunity === undefined || sourceCommunity === targetCommunity) {
      return;
    }

    const groupedSourceId = `${COMMUNITY_NODE_PREFIX}${sourceCommunity}`;
    const groupedTargetId = `${COMMUNITY_NODE_PREFIX}${targetCommunity}`;
    const key = `${groupedSourceId}→${groupedTargetId}`;
    const bucket = groupedEdges.get(key) ?? {
      sourceId: groupedSourceId,
      targetId: groupedTargetId,
      rawEdgeIds: [],
      weight: 0,
      typeCounts: new Map<string, number>(),
    };
    bucket.rawEdgeIds.push(String(edgeId));
    bucket.weight = Math.max(bucket.weight, Number((attrs as EdgeAttributes).weight ?? 1));
    const edgeType = String((attrs as EdgeAttributes).edgeType ?? "related_to");
    bucket.typeCounts.set(edgeType, (bucket.typeCounts.get(edgeType) ?? 0) + 1);
    groupedEdges.set(key, bucket);
  });

  const connectivityByCommunity = new Map<number, number>();
  groupedEdges.forEach((bundle) => {
    const sourceCommunityId = Number(bundle.sourceId.replace(COMMUNITY_NODE_PREFIX, ""));
    const targetCommunityId = Number(bundle.targetId.replace(COMMUNITY_NODE_PREFIX, ""));
    const weight = bundle.rawEdgeIds.length + bundle.weight * 0.35;
    connectivityByCommunity.set(sourceCommunityId, (connectivityByCommunity.get(sourceCommunityId) ?? 0) + weight);
    connectivityByCommunity.set(targetCommunityId, (connectivityByCommunity.get(targetCommunityId) ?? 0) + weight);
  });

  const groupedEdgeStrength = new Map<string, number>();
  const incidentEdgeStrengths = new Map<string, Array<{ key: string; strength: number }>>();
  let strongestGroupedEdge = 0;
  groupedEdges.forEach((bundle, key) => {
    const strength = bundle.rawEdgeIds.length + bundle.weight * 0.35;
    groupedEdgeStrength.set(key, strength);
    strongestGroupedEdge = Math.max(strongestGroupedEdge, strength);

    const sourceBucket = incidentEdgeStrengths.get(bundle.sourceId) ?? [];
    sourceBucket.push({ key, strength });
    incidentEdgeStrengths.set(bundle.sourceId, sourceBucket);

    const targetBucket = incidentEdgeStrengths.get(bundle.targetId) ?? [];
    targetBucket.push({ key, strength });
    incidentEdgeStrengths.set(bundle.targetId, targetBucket);
  });

  const visibleGroupedEdgeKeys = new Set<string>();
  const groupedEdgeStrengthCutoff = Math.max(1.25, strongestGroupedEdge * GRAPH_THEME.grouped.style.edgeVisibilityRatio);
  groupedEdges.forEach((_bundle, key) => {
    const strength = groupedEdgeStrength.get(key) ?? 0;
    if (strength >= groupedEdgeStrengthCutoff) {
      visibleGroupedEdgeKeys.add(key);
    }
  });
  incidentEdgeStrengths.forEach((entries) => {
    entries
      .slice()
      .sort((left, right) => right.strength - left.strength)
      .slice(0, GRAPH_THEME.grouped.style.topIncidentEdges)
      .forEach(({ key }) => visibleGroupedEdgeKeys.add(key));
  });
  if (visibleGroupedEdgeKeys.size === 0 && groupedEdges.size > 0) {
    const strongestKey = Array.from(groupedEdges.keys()).sort(
      (left, right) => (groupedEdgeStrength.get(right) ?? 0) - (groupedEdgeStrength.get(left) ?? 0),
    )[0];
    if (strongestKey) {
      visibleGroupedEdgeKeys.add(strongestKey);
    }
  }

  const groupedPositions = assignGroupedCommunityPositions(
    Array.from(communitySummaries.entries()).map(([communityId, summary]) => ({
      communityId,
      memberCount: summary.memberCount,
      centralityScore: summary.centralityScore,
      connectivityWeight: connectivityByCommunity.get(communityId) ?? 0,
      radius: getGroupedCommunityNodeSize(summary.memberCount) * GRAPH_THEME.grouped.style.nodeSizeScale * 0.92,
    })),
  );

  communitySummaries.forEach((summary, communityId) => {
    const communityNodeId = `${COMMUNITY_NODE_PREFIX}${communityId}`;
    const position = groupedPositions.get(communityId) ?? {
      x: 0,
      y: 0,
      labelPriority: 0.56,
      visualPriority: 0.42,
    };
    const size = getGroupedCommunityNodeSize(summary.memberCount);
    const anchorLabel = summary.anchorAttrs?.label || summary.anchorNodeId || `Community ${communityId}`;
    addNodeIfMissing(grouped, communityNodeId, {
      label: truncateGroupedLabel(anchorLabel),
      content: summary.anchorAttrs?.content || anchorLabel,
      x: position.x,
      y: position.y,
      size,
      baseSize: size,
      color: summary.color,
      baseColor: summary.color,
      mutedColor: withAlpha(summary.color, 0.22),
      glowColor: withAlpha(summary.color, GRAPH_THEME.grouped.style.glowAlpha),
      borderColor: withAlpha(summary.color, 0.74),
      nodeType: "community",
      semanticGroup: summary.dominantSemanticGroup,
      labelVisibilityPolicy: position.labelPriority > 0.9 ? "priority" : "none",
      properties: {
        __communityGroup: {
          communityId: String(communityId),
          memberCount: summary.memberCount,
          memberNodeIds: summary.memberIds,
          sampleNodeIds: summary.rankedMembers.slice(0, GROUP_SAMPLE_MEMBERS),
          anchorNodeId: summary.anchorNodeId,
          anchorLabel,
          dominantSemanticGroup: summary.dominantSemanticGroup,
          color: summary.color,
        },
      },
      isCommunityGroup: true,
      communityId: String(communityId),
      memberCount: summary.memberCount,
      anchorNodeId: summary.anchorNodeId,
      labelPriority: position.labelPriority,
      visualPriority: position.visualPriority,
    });
  });

  groupedEdges.forEach((bundle, key) => {
    if (!visibleGroupedEdgeKeys.has(key)) {
      return;
    }
    const dominantEdgeType = [...bundle.typeCounts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? "related_to";
    const reverseKey = `${bundle.targetId}→${bundle.sourceId}`;
    const syntheticEdgeId = `${AGGREGATED_EDGE_PREFIX}${key}`;
    const aggregateCount = bundle.rawEdgeIds.length;
    const baseSize = Math.max(0.9, 0.72 + Math.log2(aggregateCount + 1) * 0.2);
    grouped.mergeDirectedEdgeWithKey(syntheticEdgeId, bundle.sourceId, bundle.targetId, {
      edgeId: syntheticEdgeId,
      familyId: syntheticEdgeId,
      sourceId: bundle.sourceId,
      targetId: bundle.targetId,
      edgeType: dominantEdgeType,
      dominantEdgeType,
      weight: bundle.weight,
      representativeWeight: bundle.weight,
      properties: {},
      rawEdgeIds: bundle.rawEdgeIds,
      isAggregated: true,
      aggregateCount,
      familySize: aggregateCount,
      parallelCount: aggregateCount,
      isBidirectional: groupedEdges.has(reverseKey),
      bundleKind: "community",
      edgeVariant: "line",
      arrowVisibilityPolicy: "hidden",
      baseSize,
      size: baseSize,
      color: withAlpha("#9BB7D6", GRAPH_THEME.grouped.style.edgeAlpha),
      mutedColor: withAlpha("#9BB7D6", Math.max(0.14, GRAPH_THEME.grouped.style.edgeAlpha * 0.4)),
      visualPriority: Math.min(1.05, 0.38 + Math.log2(aggregateCount + 1) * 0.14),
    });
  });

  const groupedValidationError = validateGroupedDisplayGraph(grouped);
  if (groupedValidationError) {
    state.groupedViewAvailable = false;
    state.groupedViewReason = groupedValidationError;
    return {
      graph: aggregateDisplayGraph(graph),
      state,
      meta: MIRRORED_DISPLAY_META,
    };
  }

  return {
    graph: grouped,
    state: {
      aggregationEnabled: true,
      groupedViewAvailable: true,
      groupedViewReason: null,
      selectedRootNodeId: null,
      selectedVisibleNeighborIds: [],
      selectedCollapsedNeighborIds: [],
      selectedNodeKind: "none",
      canActivateFocused: false,
      resolvedFocusedNodeId: null,
      focusedUnavailableReason: null,
    },
    meta: OWNED_DISPLAY_META,
  };
}

export function resolveDisplayStateSnapshot(
  selectedNodeId: string,
  activePath: string[],
  viewMode: GraphViewMode,
  options?: {
    aggregationEnabled?: boolean;
    collapsedNeighborhoodNodeIds?: Iterable<string>;
    groupedViewAvailable?: boolean;
    groupedViewReason?: string | null;
    selectedNodeKind?: GraphSelectedNodeKind;
    resolvedFocusedNodeId?: string | null;
    focusedUnavailableReason?: string | null;
  },
): GraphDisplayStateSnapshot {
  const aggregationEnabled = options?.aggregationEnabled ?? true;
  const collapsedNeighborhoodNodeIds = new Set(
    Array.from(options?.collapsedNeighborhoodNodeIds ?? []).filter((nodeId) => typeof nodeId === "string"),
  );
  const displayState = createEmptyDisplayState(selectedNodeId, aggregationEnabled);
  displayState.selectedNodeKind = options?.selectedNodeKind ?? (selectedNodeId ? "unavailable" : "none");
  displayState.resolvedFocusedNodeId = options?.resolvedFocusedNodeId ?? null;
  displayState.canActivateFocused = Boolean(displayState.resolvedFocusedNodeId);
  displayState.focusedUnavailableReason = displayState.canActivateFocused
    ? null
    : (options?.focusedUnavailableReason ?? displayState.focusedUnavailableReason);
  displayState.groupedViewAvailable = options?.groupedViewAvailable ?? computeGraphAnalyticsBase(graph, {
    computeCommunities: true,
    computeCentrality: false,
  }).communitiesByNode.size > 0;
  displayState.groupedViewReason = options?.groupedViewReason
    ?? (displayState.groupedViewAvailable ? null : "Grouped view is unavailable until communities can be detected.");

  if (!selectedNodeId || !graph.hasNode(selectedNodeId)) {
    return displayState;
  }

  const shouldCollapseNeighborhood = Boolean(
    viewMode !== "grouped"
    && collapsedNeighborhoodNodeIds.has(selectedNodeId),
  );
  const collapsedState = shouldCollapseNeighborhood
    ? buildCollapsedNeighborhoodState(selectedNodeId, activePath)
    : {
        selectedVisibleNeighborIds: rankNeighbors(selectedNodeId),
        selectedCollapsedNeighborIds: [],
      };

  displayState.selectedRootNodeId = selectedNodeId;
  displayState.selectedVisibleNeighborIds = collapsedState.selectedVisibleNeighborIds;
  displayState.selectedCollapsedNeighborIds = collapsedState.selectedCollapsedNeighborIds;
  return displayState;
}

export function createFocusedGraph(
  nodeId: string,
  activePath: string[],
  activePathEdgeIds: string[] = [],
  collapseNeighborhood = false,
): Graph<NodeAttributes, EdgeAttributes> {
  const focused = new Graph<NodeAttributes, EdgeAttributes>({
    type: "directed",
    multi: true,
    allowSelfLoops: false,
  });

  const rankedNeighbors = rankNeighbors(nodeId).slice(0, MAX_FOCUS_NEIGHBORS);
  const collapsedState = collapseNeighborhood
    ? buildCollapsedNeighborhoodState(nodeId, activePath)
    : {
        selectedVisibleNeighborIds: rankedNeighbors,
        selectedCollapsedNeighborIds: [],
      };
  const visibleNeighborIds = rankedNeighbors.filter((neighborId) => collapsedState.selectedVisibleNeighborIds.includes(neighborId));
  const focusIds = new Set<string>([nodeId, ...visibleNeighborIds]);
  const pathNodeIds = new Set(activePath);
  const pathEdgeIds = buildPathEdgeSet(graph, activePath, activePathEdgeIds);
  const neighborEntries = buildFocusedNeighbors(nodeId, visibleNeighborIds, rankedNeighbors, pathNodeIds);
  const primaryNeighborIds = new Set(
    neighborEntries.filter((entry) => entry.zone === "primary").map((entry) => entry.id),
  );

  const addNode = (id: string, attrs: NodeAttributes) => {
    if (!focused.hasNode(id)) {
      focused.addNode(id, attrs);
    }
  };

  const selectedAttrs = graph.getNodeAttributes(nodeId) as NodeAttributes;
  const selectedState = resolveNodeElementStyle(
    GRAPH_THEME,
    "inspection",
    "selected",
    {
      ...selectedAttrs,
      labelPriority: 2,
      labelVisibilityPolicy: "always",
      haloColor: withAlpha(GRAPH_THEME.palette.accent.selected, 0.26),
    },
    selectedAttrs.label,
  );
  addNode(nodeId, {
    ...selectedAttrs,
    x: 0,
    y: 0,
    color: selectedState.color,
    size: Math.max(selectedState.size * 1.08, GRAPH_THEME.focus.selectedMinSize),
    baseColor: selectedState.color,
    baseSize: Math.max(selectedState.size * 1.08, GRAPH_THEME.focus.selectedMinSize),
    label: selectedState.label,
    labelPriority: 2,
    labelVisibilityPolicy: "always",
    ringColor: GRAPH_THEME.palette.accent.selected,
    haloColor: withAlpha(GRAPH_THEME.palette.accent.selected, 0.24),
  });

  neighborEntries.forEach((entry) => {
    const visualState: GraphNodeVisualState = entry.isPath
      ? "path"
      : entry.zone === "primary"
        ? "neighbor"
        : "default";
    const style = resolveNodeElementStyle(
      GRAPH_THEME,
      "inspection",
      visualState,
      {
        ...entry.attrs,
        labelPriority: entry.labelPriority,
        labelVisibilityPolicy: entry.isPath || entry.zone === "primary" ? "priority" : "none",
        haloColor: entry.isPath
          ? withAlpha(GRAPH_THEME.palette.accent.path, 0.16)
          : entry.zone === "primary"
            ? withAlpha(entry.attrs.color, 0.12)
            : withAlpha(entry.attrs.color, 0.06),
      },
      entry.attrs.label,
    );

    addNode(entry.id, {
      ...entry.attrs,
      x: entry.x,
      y: entry.y,
      color: style.color,
      size: Math.max(entry.size, style.size),
      baseColor: style.color,
      baseSize: Math.max(entry.size, style.size),
      label: style.label,
      labelPriority: entry.labelPriority,
      labelVisibilityPolicy: entry.isPath || entry.zone === "primary" ? "priority" : "none",
      haloColor: entry.isPath
        ? withAlpha(GRAPH_THEME.palette.accent.path, 0.16)
        : entry.zone === "primary"
          ? withAlpha(style.color, 0.1)
          : withAlpha(style.color, 0.05),
    });
  });

  const focusedEdgeIds = collectFocusEdgeIds(graph, focusIds);
  const retainedSupportEdgeIds = new Set(
    Array.from(focusedEdgeIds)
      .filter((edgeId) => {
        if (!graph.hasEdge(edgeId) || pathEdgeIds.has(edgeId)) {
          return false;
        }
        const [edgeSourceId, edgeTargetId] = graph.extremities(edgeId);
        return edgeSourceId !== nodeId && edgeTargetId !== nodeId;
      })
      .sort((leftEdgeId, rightEdgeId) => {
        const leftAttrs = graph.getEdgeAttributes(leftEdgeId) as EdgeAttributes;
        const rightAttrs = graph.getEdgeAttributes(rightEdgeId) as EdgeAttributes;
        const [leftSourceId, leftTargetId] = graph.extremities(leftEdgeId);
        const [rightSourceId, rightTargetId] = graph.extremities(rightEdgeId);
        const scoreDelta = scoreFocusedSupportEdge(
          rightAttrs,
          rightSourceId,
          rightTargetId,
          primaryNeighborIds,
        ) - scoreFocusedSupportEdge(
          leftAttrs,
          leftSourceId,
          leftTargetId,
          primaryNeighborIds,
        );
        if (scoreDelta !== 0) {
          return scoreDelta;
        }
        return leftEdgeId.localeCompare(rightEdgeId);
      })
      .slice(0, GRAPH_THEME.focus.supportEdgeBudget),
  );
  let loggedFocusedEdgeSkip = false;

  if (DEBUG_GRAPH_SCENE_STATE) {
    console.debug("[graphSceneState]", "focused-graph-build", {
      nodeId,
      focusedNodeCount: focusIds.size,
      focusedEdgeCount: focusedEdgeIds.size,
      retainedSupportEdgeCount: retainedSupportEdgeIds.size,
    });
  }

  focusedEdgeIds.forEach((edgeId) => {
    if (!graph.hasEdge(edgeId)) {
      return;
    }

    const [edgeSourceId, edgeTargetId] = graph.extremities(edgeId);
    if (!focusIds.has(edgeSourceId) || !focusIds.has(edgeTargetId)) {
      if (DEBUG_GRAPH_SCENE_STATE && !loggedFocusedEdgeSkip) {
        loggedFocusedEdgeSkip = true;
        console.debug("[graphSceneState]", "focused-edge-skipped-outside-focus", {
          nodeId,
          edgeId,
          edgeSourceId,
          edgeTargetId,
          focusedNodeCount: focusIds.size,
        });
      }
      return;
    }

    const attrs = graph.getEdgeAttributes(edgeId) as EdgeAttributes;
    const isPathEdge = pathEdgeIds.has(edgeId);
    const isSelectedIncidentEdge = edgeSourceId === nodeId || edgeTargetId === nodeId;
    if (!isPathEdge && !isSelectedIncidentEdge && !retainedSupportEdgeIds.has(edgeId)) {
      return;
    }
    const state: GraphEdgeVisualState = pathEdgeIds.has(edgeId)
      ? "path"
      : edgeSourceId === nodeId || edgeTargetId === nodeId
        ? "selected"
        : "neighbor";
    const style = resolveEdgeElementStyle(GRAPH_THEME, "inspection", state, attrs, edgeSourceId, edgeTargetId);
    const styledEdgeSize = Number(style.size ?? attrs.size ?? attrs.baseSize ?? 1);
    const styledEdgeColor = style.color ?? attrs.color ?? GRAPH_THEME.palette.muted.edgeFocus;
    const renderedSize = isSelectedIncidentEdge
      ? Math.max(styledEdgeSize, 2)
      : isPathEdge
        ? Math.max(styledEdgeSize, 2.4)
        : Math.max(styledEdgeSize * 0.62, 0.85);
    const renderedColor = isSelectedIncidentEdge
      ? styledEdgeColor
      : isPathEdge
        ? styledEdgeColor
        : withAlpha(styledEdgeColor, 0.34);
    focused.mergeDirectedEdgeWithKey(edgeId, edgeSourceId, edgeTargetId, {
      ...attrs,
      type: isSelectedIncidentEdge || isPathEdge ? style.type : "line",
      size: renderedSize,
      color: renderedColor,
      baseSize: renderedSize,
      baseColor: renderedColor,
      curvature: isSelectedIncidentEdge || isPathEdge ? style.curvature : 0,
      arrowVisibilityPolicy: isSelectedIncidentEdge || isPathEdge ? attrs.arrowVisibilityPolicy : "hidden",
      visualPriority: isPathEdge ? 1.5 : isSelectedIncidentEdge ? 1.2 : 0.34,
    });
  });

  return aggregateDisplayGraph(focused);
}

export function resolveDisplayGraph(
  selectedNodeId: string,
  activePath: string[],
  activePathEdgeIds: string[],
  viewMode: GraphViewMode,
  options?: {
    aggregationEnabled?: boolean;
    collapsedNeighborhoodNodeIds?: Iterable<string>;
    groupedViewAvailable?: boolean;
  },
): GraphDisplayResult {
  const aggregationEnabled = options?.aggregationEnabled ?? true;
  const collapsedNeighborhoodNodeIds = new Set(
    Array.from(options?.collapsedNeighborhoodNodeIds ?? []).filter((nodeId) => typeof nodeId === "string"),
  );
  const displayState = resolveDisplayStateSnapshot(selectedNodeId, activePath, viewMode, {
    aggregationEnabled,
    collapsedNeighborhoodNodeIds,
    groupedViewAvailable: options?.groupedViewAvailable,
  });
  const isFocusedView = viewMode === "focused" && Boolean(selectedNodeId) && graph.hasNode(selectedNodeId);
  const isGroupedView = viewMode === "grouped";
  const shouldCollapseNeighborhood = Boolean(selectedNodeId && collapsedNeighborhoodNodeIds.has(selectedNodeId));

  if (isGroupedView) {
    const grouped = buildCommunityGroupedGraph();
    return {
      graph: grouped.graph,
      state: {
        ...grouped.state,
        selectedRootNodeId: displayState.selectedRootNodeId,
        selectedVisibleNeighborIds: displayState.selectedVisibleNeighborIds,
        selectedCollapsedNeighborIds: displayState.selectedCollapsedNeighborIds,
        groupedViewReason: grouped.state.groupedViewReason,
        selectedNodeKind: displayState.selectedNodeKind,
        canActivateFocused: displayState.canActivateFocused,
        resolvedFocusedNodeId: displayState.resolvedFocusedNodeId,
        focusedUnavailableReason: displayState.focusedUnavailableReason,
      },
      meta: grouped.meta,
    };
  }

  if (isFocusedView && selectedNodeId) {
    return {
      graph: createFocusedGraph(selectedNodeId, activePath, activePathEdgeIds, shouldCollapseNeighborhood),
      state: displayState,
      meta: FOCUSED_DISPLAY_META,
    };
  }

  const baseGraph = shouldCollapseNeighborhood && selectedNodeId
    ? createCollapsedNeighborhoodGraph(selectedNodeId, activePath)
    : graph;

  return {
    graph: aggregationEnabled ? aggregateDisplayGraph(baseGraph) : baseGraph,
    state: displayState,
    meta: aggregationEnabled
      ? MIRRORED_DISPLAY_META
      : baseGraph === graph
        ? BASE_DISPLAY_META
        : MIRRORED_DISPLAY_META,
  };
}

export function createInteractionState(
  hoveredNodeId: string | null,
  selectedNodeId: string,
  focusedNodeId: string,
  selectedEdgeId: string,
  activePath: string[],
  activePathEdgeIds: string[],
  viewMode: GraphViewMode,
  zoomTier: GraphZoomTier,
  isLayoutRunning: boolean,
): GraphInteractionState {
  return {
    hoveredNodeId,
    selectedNodeId,
    selectedEdgeId,
    focusedNodeId,
    activePath,
    activePathEdgeIds,
    viewMode,
    zoomTier,
    isLayoutRunning,
  };
}
