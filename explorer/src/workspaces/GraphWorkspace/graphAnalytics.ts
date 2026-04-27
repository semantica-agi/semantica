import type Graph from "graphology";
import louvain from "graphology-communities-louvain";
import { dijkstra } from "graphology-shortest-path";
import betweennessCentrality from "graphology-metrics/centrality/betweenness";
import {
  degreeCentrality,
  inDegreeCentrality,
  outDegreeCentrality,
} from "graphology-metrics/centrality/degree";

import { graph, type EdgeAttributes, type NodeAttributes } from "../../store/graphStore";
import { GRAPH_THEME, hashString } from "./graphTheme";
import type {
  GraphAnalyticsSnapshot,
  GraphDataSnapshot,
  GraphCentralityNodeSummary,
  GraphCommunitySummary,
  GraphInteractionState,
  GraphSemanticRegionSummary,
} from "./types";

type GraphRef = typeof graph | Graph<NodeAttributes, EdgeAttributes>;

type GraphCentralityRecord = {
  degree: number;
  inDegree: number;
  outDegree: number;
  betweenness: number;
  score: number;
};

type GraphAnalyticsBase = {
  communitiesByNode: Map<string, number>;
  communityCount: number;
  modularity: number | null;
  centralityByNode: Map<string, GraphCentralityRecord>;
  topNodeIds: string[];
  betweennessReady: boolean;
};

const MAX_BETWEENNESS_NODES = 1400;
const MAX_COMMUNITY_SUMMARIES = 6;
const MAX_REGION_SUMMARIES = 6;
const MAX_CENTRALITY_SUMMARIES = 6;
const CENTRALITY_ITERATIONS = 24;
const MAX_BACKBONE_ANCHORS = 4;
const MAX_BACKBONE_CENTRAL_LINKS = 36;
const MAX_BACKBONE_BRIDGES = 80;
const MAX_BACKBONE_TOTAL_EDGES = 128;
const MAX_BACKBONE_EDGES_PER_NODE = 5;
const MAX_BACKBONE_PARALLEL_PAIR_EDGES = 2;

type BackboneCandidate = {
  edgeId: string;
  source: string;
  target: string;
  score: number;
};

function getNodeLabel(graphRef: GraphRef, nodeId: string): string {
  const attrs = graphRef.getNodeAttributes(nodeId) as NodeAttributes;
  return String(attrs.label || attrs.content || nodeId);
}

function getNodeColor(graphRef: GraphRef, nodeId: string): string {
  const attrs = graphRef.getNodeAttributes(nodeId) as NodeAttributes;
  return String(attrs.baseColor || attrs.color || "#63E6FF");
}

function getNodeSemanticGroup(graphRef: GraphRef, nodeId: string): string {
  const attrs = graphRef.getNodeAttributes(nodeId) as NodeAttributes;
  return String(attrs.semanticGroup || attrs.nodeType || "entity");
}

function toVisibleNodeSet(graphRef: GraphRef, visibleNodeIds?: Iterable<string>): Set<string> {
  if (!visibleNodeIds) {
    return new Set(graphRef.nodes());
  }

  const visible = new Set<string>();
  for (const nodeId of visibleNodeIds) {
    if (graphRef.hasNode(nodeId)) {
      visible.add(nodeId);
    }
  }

  return visible.size ? visible : new Set(graphRef.nodes());
}

function buildCentralityRecords(
  graphRef: GraphRef,
  includeBetweenness: boolean,
): Pick<GraphAnalyticsBase, "centralityByNode" | "topNodeIds" | "betweennessReady"> {
  const degree = degreeCentrality(graphRef);
  const inDegree = inDegreeCentrality(graphRef);
  const outDegree = outDegreeCentrality(graphRef);
  const betweenness = includeBetweenness
    ? betweennessCentrality(graphRef, { normalized: true, getEdgeWeight: "weight" })
    : {};

  const centralityByNode = new Map<string, GraphCentralityRecord>();
  graphRef.forEachNode((nodeId) => {
    const degreeScore = Number(degree[nodeId] ?? 0);
    const betweennessScore = Number((betweenness as Record<string, number>)[nodeId] ?? 0);
    const inDegreeScore = Number(inDegree[nodeId] ?? 0);
    const outDegreeScore = Number(outDegree[nodeId] ?? 0);
    centralityByNode.set(nodeId, {
      degree: degreeScore,
      inDegree: inDegreeScore,
      outDegree: outDegreeScore,
      betweenness: betweennessScore,
      score: degreeScore * 0.7 + betweennessScore * 0.3,
    });
  });

  const topNodeIds = graphRef
    .nodes()
    .sort((left, right) => {
      const leftScore = centralityByNode.get(left)?.score ?? 0;
      const rightScore = centralityByNode.get(right)?.score ?? 0;
      if (rightScore !== leftScore) {
        return rightScore - leftScore;
      }
      return left.localeCompare(right);
    });

  return {
    centralityByNode,
    topNodeIds,
    betweennessReady: includeBetweenness,
  };
}

export function computeGraphAnalyticsBase(
  graphRef: GraphRef,
  options?: {
    computeCommunities?: boolean;
    computeCentrality?: boolean;
  },
): GraphAnalyticsBase {
  const shouldComputeCommunities = options?.computeCommunities ?? true;
  const shouldComputeCentrality = options?.computeCentrality ?? true;
  const communitiesByNode = new Map<string, number>();
  let communityCount = 0;
  let modularity: number | null = null;

  if (shouldComputeCommunities && graphRef.order > 1 && graphRef.size > 0) {
    try {
      const result = louvain.detailed(graphRef, { getEdgeWeight: "weight" });
      modularity = Number(result.modularity ?? 0);
      communityCount = Number(result.count ?? 0);
      Object.entries(result.communities).forEach(([nodeId, communityId]) => {
        communitiesByNode.set(nodeId, Number(communityId));
      });
    } catch (error) {
      console.error("[GraphAnalytics] community detection failed", error);
    }
  }

  if (!shouldComputeCentrality || graphRef.order === 0) {
    return {
      communitiesByNode,
      communityCount,
      modularity,
      centralityByNode: new Map<string, GraphCentralityRecord>(),
      topNodeIds: [],
      betweennessReady: false,
    };
  }

  const includeBetweenness = graphRef.order <= MAX_BETWEENNESS_NODES;
  const centrality = buildCentralityRecords(graphRef, includeBetweenness);

  return {
    communitiesByNode,
    communityCount,
    modularity,
    ...centrality,
  };
}

function buildCommunitySummaries(
  graphRef: GraphRef,
  visibleNodeIds: Set<string>,
  base: GraphAnalyticsBase,
): GraphCommunitySummary[] {
  const grouped = new Map<number, {
    nodeCount: number;
    visibleNodeCount: number;
    semanticCounts: Map<string, number>;
    anchorNodeId: string | null;
    prominence: number;
    color: string;
  }>();

  graphRef.forEachNode((nodeId) => {
    const communityId = base.communitiesByNode.get(nodeId);
    if (communityId === undefined) {
      return;
    }

    const entry = grouped.get(communityId) ?? {
      nodeCount: 0,
      visibleNodeCount: 0,
      semanticCounts: new Map<string, number>(),
      anchorNodeId: null,
      prominence: 0,
      color: getNodeColor(graphRef, nodeId),
    };

    entry.nodeCount += 1;
    if (visibleNodeIds.has(nodeId)) {
      entry.visibleNodeCount += 1;
    }

    const semanticGroup = getNodeSemanticGroup(graphRef, nodeId);
    entry.semanticCounts.set(semanticGroup, (entry.semanticCounts.get(semanticGroup) ?? 0) + 1);

    const nodeScore = base.centralityByNode.get(nodeId)?.score ?? 0;
    if (!entry.anchorNodeId || nodeScore > (base.centralityByNode.get(entry.anchorNodeId)?.score ?? -1)) {
      entry.anchorNodeId = nodeId;
      entry.color = getNodeColor(graphRef, nodeId);
    }
    entry.prominence += visibleNodeIds.has(nodeId) ? 1 + nodeScore : nodeScore * 0.15;

    grouped.set(communityId, entry);
  });

  return [...grouped.entries()]
    .map(([communityId, data]) => {
      const dominantSemanticGroup = [...data.semanticCounts.entries()]
        .sort((left, right) => right[1] - left[1])[0]?.[0] ?? "entity";
      return {
        communityId: String(communityId),
        nodeCount: data.nodeCount,
        visibleNodeCount: data.visibleNodeCount,
        dominantSemanticGroup,
        color: data.color,
        anchorNodeId: data.anchorNodeId,
        anchorLabel: data.anchorNodeId ? getNodeLabel(graphRef, data.anchorNodeId) : "Community anchor",
        prominence: data.prominence,
      };
    })
    .filter((summary) => summary.visibleNodeCount > 0)
    .sort((left, right) => right.prominence - left.prominence)
    .slice(0, MAX_COMMUNITY_SUMMARIES);
}

function buildSemanticRegionSummaries(
  graphRef: GraphRef,
  visibleNodeIds: Set<string>,
  base: GraphAnalyticsBase,
): GraphSemanticRegionSummary[] {
  const grouped = new Map<string, {
    nodeCount: number;
    visibleNodeCount: number;
    communityCounts: Map<string, number>;
    anchorNodeId: string | null;
    prominence: number;
    color: string;
  }>();

  graphRef.forEachNode((nodeId) => {
    const semanticGroup = getNodeSemanticGroup(graphRef, nodeId);
    const entry = grouped.get(semanticGroup) ?? {
      nodeCount: 0,
      visibleNodeCount: 0,
      communityCounts: new Map<string, number>(),
      anchorNodeId: null,
      prominence: 0,
      color: getNodeColor(graphRef, nodeId),
    };

    entry.nodeCount += 1;
    if (visibleNodeIds.has(nodeId)) {
      entry.visibleNodeCount += 1;
    }

    const communityId = base.communitiesByNode.get(nodeId);
    if (communityId !== undefined) {
      const communityKey = String(communityId);
      entry.communityCounts.set(communityKey, (entry.communityCounts.get(communityKey) ?? 0) + 1);
    }

    const nodeScore = base.centralityByNode.get(nodeId)?.score ?? 0;
    if (!entry.anchorNodeId || nodeScore > (base.centralityByNode.get(entry.anchorNodeId)?.score ?? -1)) {
      entry.anchorNodeId = nodeId;
      entry.color = getNodeColor(graphRef, nodeId);
    }
    entry.prominence += visibleNodeIds.has(nodeId) ? 1 + nodeScore : nodeScore * 0.1;

    grouped.set(semanticGroup, entry);
  });

  return [...grouped.entries()]
    .map(([semanticGroup, data]) => ({
      semanticGroup,
      nodeCount: data.nodeCount,
      visibleNodeCount: data.visibleNodeCount,
      color: data.color,
      anchorNodeId: data.anchorNodeId,
      anchorLabel: data.anchorNodeId ? getNodeLabel(graphRef, data.anchorNodeId) : semanticGroup,
      dominantCommunityId: [...data.communityCounts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? null,
      prominence: data.prominence,
    }))
    .filter((summary) => summary.visibleNodeCount > 0)
    .sort((left, right) => right.prominence - left.prominence)
    .slice(0, MAX_REGION_SUMMARIES);
}

function buildCentralitySummaries(
  graphRef: GraphRef,
  visibleNodeIds: Set<string>,
  base: GraphAnalyticsBase,
): GraphCentralityNodeSummary[] {
  const candidateIds = base.topNodeIds.filter((nodeId) => visibleNodeIds.has(nodeId));
  const rankedIds = (candidateIds.length ? candidateIds : base.topNodeIds).slice(0, MAX_CENTRALITY_SUMMARIES);

  return rankedIds.map((nodeId) => {
    const record = base.centralityByNode.get(nodeId) ?? {
      degree: 0,
      betweenness: 0,
      score: 0,
    };
    return {
      id: nodeId,
      label: getNodeLabel(graphRef, nodeId),
      semanticGroup: getNodeSemanticGroup(graphRef, nodeId),
      color: getNodeColor(graphRef, nodeId),
      degree: Number(record.degree ?? 0),
      betweenness: Number(record.betweenness ?? 0),
      score: Number(record.score ?? 0),
    };
  });
}

function collectNodeIncidentEdges(
  graphRef: GraphRef,
  nodeId: string,
  visibleNodeIds: Set<string>,
): Array<{ edgeId: string; source: string; target: string; attrs: EdgeAttributes }> {
  const edges: Array<{ edgeId: string; source: string; target: string; attrs: EdgeAttributes }> = [];

  graphRef.forEachOutEdge(nodeId, (edgeId, attrs, source, target) => {
    if (!visibleNodeIds.has(target)) {
      return;
    }
    edges.push({ edgeId: String(edgeId), source, target, attrs: attrs as EdgeAttributes });
  });

  graphRef.forEachInEdge(nodeId, (edgeId, attrs, source, target) => {
    if (!visibleNodeIds.has(source)) {
      return;
    }
    edges.push({ edgeId: String(edgeId), source, target, attrs: attrs as EdgeAttributes });
  });

  return edges;
}

function scoreBackboneEdge(
  attrs: EdgeAttributes,
  sourceId: string,
  targetId: string,
  base: GraphAnalyticsBase,
) {
  const sourceScore = base.centralityByNode.get(sourceId)?.score ?? 0;
  const targetScore = base.centralityByNode.get(targetId)?.score ?? 0;
  const weight = Number(attrs.weight ?? 0);
  const priority = Number(attrs.visualPriority ?? 0);
  const parallelBoost = Number(attrs.parallelCount ?? 1) > 1 ? 0.14 : 0;
  const bidirectionalBoost = attrs.isBidirectional ? 0.18 : 0;

  return weight * 1.4 + (sourceScore + targetScore) * 2.4 + priority * 0.6 + parallelBoost + bidirectionalBoost;
}

function upsertBackboneCandidate(
  candidates: Map<string, BackboneCandidate>,
  key: string,
  candidate: BackboneCandidate,
) {
  const current = candidates.get(key);
  if (
    !current
    || candidate.score > current.score
    || (candidate.score === current.score && candidate.edgeId.localeCompare(current.edgeId) < 0)
  ) {
    candidates.set(key, candidate);
  }
}

function addRankedBackboneCandidates(
  selected: BackboneCandidate[],
  selectedEdgeIds: Set<string>,
  nodeUseCounts: Map<string, number>,
  pairUseCounts: Map<string, number>,
  candidates: Iterable<BackboneCandidate>,
  maxToAdd: number,
) {
  const ranked = [...candidates].sort((left, right) => {
    if (right.score !== left.score) {
      return right.score - left.score;
    }
    return left.edgeId.localeCompare(right.edgeId);
  });

  for (const candidate of ranked) {
    if (selected.length >= MAX_BACKBONE_TOTAL_EDGES || maxToAdd <= 0 || selectedEdgeIds.has(candidate.edgeId)) {
      continue;
    }

    const pairKey = [candidate.source, candidate.target].sort().join("::");
    if ((nodeUseCounts.get(candidate.source) ?? 0) >= MAX_BACKBONE_EDGES_PER_NODE) {
      continue;
    }
    if ((nodeUseCounts.get(candidate.target) ?? 0) >= MAX_BACKBONE_EDGES_PER_NODE) {
      continue;
    }
    if ((pairUseCounts.get(pairKey) ?? 0) >= MAX_BACKBONE_PARALLEL_PAIR_EDGES) {
      continue;
    }

    selected.push(candidate);
    selectedEdgeIds.add(candidate.edgeId);
    nodeUseCounts.set(candidate.source, (nodeUseCounts.get(candidate.source) ?? 0) + 1);
    nodeUseCounts.set(candidate.target, (nodeUseCounts.get(candidate.target) ?? 0) + 1);
    pairUseCounts.set(pairKey, (pairUseCounts.get(pairKey) ?? 0) + 1);
    maxToAdd -= 1;
  }
}

function buildOverviewBackboneSnapshot(
  graphRef: GraphRef,
  visibleNodeIds: Set<string>,
  base: GraphAnalyticsBase,
  semanticRegionSummaries: GraphSemanticRegionSummary[],
  centralitySummaries: GraphCentralityNodeSummary[],
): GraphAnalyticsSnapshot["overviewBackbone"] {
  if (visibleNodeIds.size === 0) {
    return {
      ready: false,
      reason: "No visible nodes are available for overview backbone selection.",
      edgeIds: [],
    };
  }

  const selected: BackboneCandidate[] = [];
  const selectedEdgeIds = new Set<string>();
  const nodeUseCounts = new Map<string, number>();
  const pairUseCounts = new Map<string, number>();
  const regionByNode = new Map<string, string>();
  visibleNodeIds.forEach((nodeId) => {
    regionByNode.set(nodeId, getNodeSemanticGroup(graphRef, nodeId));
  });
  const topRegionIds = new Set(semanticRegionSummaries.slice(0, 3).map((summary) => summary.semanticGroup));
  const backboneCoreNodeIds = new Set(
    centralitySummaries
      .slice(0, MAX_BACKBONE_ANCHORS * 2)
      .map((summary) => summary.id)
      .filter((nodeId) => visibleNodeIds.has(nodeId)),
  );

  const anchorIds = centralitySummaries
    .slice(0, MAX_BACKBONE_ANCHORS)
    .map((summary) => summary.id)
    .filter((nodeId) => visibleNodeIds.has(nodeId));

  const coreLinkCandidates = new Map<string, BackboneCandidate>();
  anchorIds.forEach((anchorId) => {
    collectNodeIncidentEdges(graphRef, anchorId, visibleNodeIds)
      .filter((entry) => {
        const otherNodeId = entry.source === anchorId ? entry.target : entry.source;
        if (!backboneCoreNodeIds.has(otherNodeId)) {
          return false;
        }
        const sourceRegion = regionByNode.get(entry.source);
        const targetRegion = regionByNode.get(entry.target);
        return Boolean(sourceRegion && targetRegion && (topRegionIds.has(sourceRegion) || topRegionIds.has(targetRegion)));
      })
      .forEach((entry) => {
        const pairKey = [entry.source, entry.target].sort().join("::");
        const sourceRegion = regionByNode.get(entry.source);
        const targetRegion = regionByNode.get(entry.target);
        const bridgeBoost = sourceRegion && targetRegion && sourceRegion !== targetRegion ? 0.28 : 0;
        const score = scoreBackboneEdge(entry.attrs, entry.source, entry.target, base) + bridgeBoost;
        upsertBackboneCandidate(coreLinkCandidates, pairKey, {
          edgeId: entry.edgeId,
          source: entry.source,
          target: entry.target,
          score,
        });
      });
  });

  const bridgeCandidates = new Map<string, BackboneCandidate>();
  const structuralCandidates = new Map<string, BackboneCandidate>();
  graphRef.forEachEdge((edgeId, attrs, source, target) => {
    if (!visibleNodeIds.has(source) || !visibleNodeIds.has(target)) {
      return;
    }

    const edgeKey = String(edgeId);
    const sourceId = String(source);
    const targetId = String(target);
    const sourceRegion = regionByNode.get(sourceId);
    const targetRegion = regionByNode.get(targetId);
    const sourceCommunity = base.communitiesByNode.get(sourceId);
    const targetCommunity = base.communitiesByNode.get(targetId);
    const crossesSemanticRegion = Boolean(sourceRegion && targetRegion && sourceRegion !== targetRegion);
    const crossesCommunity = sourceCommunity !== undefined && targetCommunity !== undefined && sourceCommunity !== targetCommunity;
    const sourceCentrality = base.centralityByNode.get(sourceId)?.score ?? 0;
    const targetCentrality = base.centralityByNode.get(targetId)?.score ?? 0;

    const baseScore = scoreBackboneEdge(attrs as EdgeAttributes, sourceId, targetId, base);
    const semanticBoost = crossesSemanticRegion ? 0.5 : 0;
    const communityBoost = crossesCommunity ? 0.36 : 0;
    const topRegionBoost = sourceRegion && targetRegion && (topRegionIds.has(sourceRegion) || topRegionIds.has(targetRegion)) ? 0.32 : 0;
    const centralityBalance = Math.min(sourceCentrality, targetCentrality) * 1.2;
    const score = baseScore + semanticBoost + communityBoost + topRegionBoost + centralityBalance;
    const candidate = {
      edgeId: edgeKey,
      source: sourceId,
      target: targetId,
      score,
    };

    if (crossesSemanticRegion || crossesCommunity) {
      const bridgeKey = [
        sourceRegion ?? `community:${sourceCommunity ?? sourceId}`,
        targetRegion ?? `community:${targetCommunity ?? targetId}`,
        Math.min(sourceCentrality, targetCentrality).toFixed(4),
      ].sort().join("::");
      upsertBackboneCandidate(bridgeCandidates, bridgeKey, candidate);
    }

    const pairKey = [sourceId, targetId].sort().join("::");
    upsertBackboneCandidate(structuralCandidates, pairKey, candidate);
  });

  addRankedBackboneCandidates(
    selected,
    selectedEdgeIds,
    nodeUseCounts,
    pairUseCounts,
    bridgeCandidates.values(),
    MAX_BACKBONE_BRIDGES,
  );
  addRankedBackboneCandidates(
    selected,
    selectedEdgeIds,
    nodeUseCounts,
    pairUseCounts,
    coreLinkCandidates.values(),
    MAX_BACKBONE_CENTRAL_LINKS,
  );
  addRankedBackboneCandidates(
    selected,
    selectedEdgeIds,
    nodeUseCounts,
    pairUseCounts,
    structuralCandidates.values(),
    MAX_BACKBONE_TOTAL_EDGES - selected.length,
  );

  const edgeIds = selected
    .map((entry) => entry.edgeId)
    .filter((edgeId) => graphRef.hasEdge(edgeId));

  return {
    ready: edgeIds.length > 0,
    reason: edgeIds.length > 0
      ? "Ready"
      : "No overview backbone edges met the current visibility thresholds.",
    edgeIds,
  };
}

function buildDirectedPathSnapshot(
  graphRef: GraphRef,
  interactionState: GraphInteractionState,
): GraphAnalyticsSnapshot["directedPath"] {
  if (interactionState.activePath.length < 2) {
    return {
      ready: false,
      reason: "Trace a path to compare it against local strict directed shortest pathfinding.",
      sourceId: interactionState.selectedNodeId || null,
      targetId: null,
      path: [],
      length: null,
      verifiedAgainstActivePath: false,
    };
  }

  const sourceId = interactionState.activePath[0] ?? null;
  const targetId = interactionState.activePath[interactionState.activePath.length - 1] ?? null;
  if (!sourceId || !targetId || !graphRef.hasNode(sourceId) || !graphRef.hasNode(targetId)) {
    return {
      ready: false,
      reason: "Active path endpoints are not available in the current graph view.",
      sourceId,
      targetId,
      path: [],
      length: null,
      verifiedAgainstActivePath: false,
    };
  }

  try {
    const path = dijkstra.bidirectional(graphRef, sourceId, targetId, "weight") ?? [];
    return {
      ready: path.length > 1,
      reason: path.length > 1
        ? "Ready"
        : "No strict directed shortest path found in the current graph view.",
      sourceId,
      targetId,
      path,
      length: path.length > 1 ? path.length - 1 : null,
      verifiedAgainstActivePath: path.join("::") === interactionState.activePath.join("::"),
    };
  } catch (error) {
    console.error("[GraphAnalytics] directed pathfinding failed", error);
    return {
      ready: false,
      reason: "Directed pathfinding failed for the current graph snapshot.",
      sourceId,
      targetId,
      path: [],
      length: null,
      verifiedAgainstActivePath: false,
    };
  }
}

export function buildGraphAnalyticsSnapshot(params: {
  graphRef: GraphRef;
  interactionState: GraphInteractionState;
  base: GraphAnalyticsBase;
  visibleNodeIds?: Iterable<string>;
}): GraphAnalyticsSnapshot {
  const { graphRef, interactionState, base } = params;
  const visibleNodeIds = toVisibleNodeSet(graphRef, params.visibleNodeIds);
  const directedPath = buildDirectedPathSnapshot(graphRef, interactionState);
  const communitySummaries = base.communitiesByNode.size
    ? buildCommunitySummaries(graphRef, visibleNodeIds, base)
    : [];
  const semanticRegionSummaries = buildSemanticRegionSummaries(graphRef, visibleNodeIds, base);
  const centralitySummaries = buildCentralitySummaries(graphRef, visibleNodeIds, base);
  const overviewBackbone = buildOverviewBackboneSnapshot(
    graphRef,
    visibleNodeIds,
    base,
    semanticRegionSummaries,
    centralitySummaries,
  );

  return {
    generatedAt: Date.now(),
    directedPath,
    communities: {
      ready: communitySummaries.length > 0,
      reason: communitySummaries.length > 0
        ? "Ready"
        : base.communitiesByNode.size > 0
          ? "No visible communities in the current graph context."
          : "Community detection has not produced summaries yet.",
      count: base.communityCount,
      modularity: base.modularity,
      summaries: communitySummaries,
    },
    centrality: {
      ready: centralitySummaries.length > 0,
      reason: centralitySummaries.length > 0
        ? base.betweennessReady
          ? "Ready"
          : "Ready (degree-biased while betweenness is bounded for large graphs)."
        : "Centrality ranking is waiting for graph data.",
      topNodes: centralitySummaries,
    },
    semanticRegions: {
      ready: semanticRegionSummaries.length > 0,
      reason: semanticRegionSummaries.length > 0
        ? "Ready"
        : "No semantic regions are visible in the current graph context.",
      summaries: semanticRegionSummaries,
    },
    overviewBackbone,
  };
}

export function colorForNodeKey(key: string): string {
  const palette = GRAPH_THEME.palette.semantic;
  return palette[hashString(key) % palette.length];
}

export function chooseColorAccessor(
  nodes: Array<{ id: string; attributes: Pick<NodeAttributes, "nodeType" | "content"> }>,
) {
  return (id: string, attributes: Pick<NodeAttributes, "nodeType" | "content">) => {
    const semanticKey = String(attributes.nodeType || attributes.content || id);
    const node = nodes.find((entry) => entry.id === id);
    const fallbackKey = String(node?.attributes.nodeType || node?.attributes.content || semanticKey);
    return `${fallbackKey}:${id}`;
  };
}

export function deterministicPosition(nodeId: string, index: number, totalNodes: number) {
  const angle = (hashString(nodeId) % 360) * (Math.PI / 180);
  const ring = Math.floor(index / Math.max(12, Math.ceil(Math.sqrt(Math.max(totalNodes, 1)))));
  const radius = 120 + ring * 90 + (hashString(`${nodeId}:radius`) % 46);
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
  };
}

export function computeDegreeMap(
  nodes: GraphDataSnapshot["nodes"],
  edges: GraphDataSnapshot["edges"],
) {
  const degreeByNode = new Map<string, number>();
  nodes.forEach((node) => degreeByNode.set(node.id, 0));
  edges.forEach((edge) => {
    degreeByNode.set(edge.source, (degreeByNode.get(edge.source) ?? 0) + 1);
    degreeByNode.set(edge.target, (degreeByNode.get(edge.target) ?? 0) + 1);
  });
  return degreeByNode;
}

export function computePageRank(
  nodes: GraphDataSnapshot["nodes"],
  edges: GraphDataSnapshot["edges"],
) {
  const pageRank = new Map<string, number>();
  const outbound = new Map<string, string[]>();
  const inbound = new Map<string, string[]>();
  const nodeCount = Math.max(nodes.length, 1);

  nodes.forEach((node) => {
    pageRank.set(node.id, 1 / nodeCount);
    outbound.set(node.id, []);
    inbound.set(node.id, []);
  });

  edges.forEach((edge) => {
    outbound.set(edge.source, [...(outbound.get(edge.source) ?? []), edge.target]);
    inbound.set(edge.target, [...(inbound.get(edge.target) ?? []), edge.source]);
  });

  for (let iteration = 0; iteration < CENTRALITY_ITERATIONS; iteration += 1) {
    const next = new Map<string, number>();
    nodes.forEach((node) => {
      const incoming = inbound.get(node.id) ?? [];
      let sum = 0;
      incoming.forEach((sourceId) => {
        const outDegree = (outbound.get(sourceId) ?? []).length || nodeCount;
        sum += (pageRank.get(sourceId) ?? 0) / outDegree;
      });
      next.set(node.id, 0.15 / nodeCount + 0.85 * sum);
    });
    next.forEach((value, nodeId) => pageRank.set(nodeId, value));
  }

  return pageRank;
}

export function computeNodeSize(
  nodeId: string,
  degreeByNode: Map<string, number>,
  pageRankByNode: Map<string, number>,
) {
  const degree = degreeByNode.get(nodeId) ?? 0;
  const pageRank = pageRankByNode.get(nodeId) ?? 0;
  return 5.5 + Math.min(16, degree * 0.18 + pageRank * 160);
}

export function computeEdgeSize(weight: number) {
  return Math.max(0.8, Math.min(3.2, 0.9 + Math.log2(Math.max(weight, 1) + 1) * 0.36));
}
