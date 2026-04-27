import test from "node:test";
import assert from "node:assert/strict";

import {
  batchMergeEdges,
  batchMergeNodes,
  clearGraph,
  graph,
} from "../src/store/graphStore.ts";
import {
  buildGraphAnalyticsSnapshot,
  computeGraphAnalyticsBase,
} from "../src/workspaces/GraphWorkspace/graphAnalytics.ts";
import {
  classifyFullGraphEdge,
  checkGroupedViewAvailability,
  mapFullEdgeClassToVisualState,
  resolveEdgeElementStyle,
  resolveEdgeVisualState,
  resolveDisplayGraph,
  resolveGroupedDisplayNodeId,
  resolveGroupedDisplayStateSnapshot,
} from "../src/workspaces/GraphWorkspace/graphSceneState.ts";
import {
  buildGraphStructureCurveCache,
  evaluateGraphStructureLayerGate,
} from "../src/workspaces/GraphWorkspace/graphStructureLayer.ts";
import { GRAPH_THEME } from "../src/workspaces/GraphWorkspace/graphTheme.ts";
import type { GraphFullEdgeClass, GraphFullEdgeClassCounts } from "../src/workspaces/GraphWorkspace/types.ts";

function addNode(id: string, semanticGroup = "entity") {
  batchMergeNodes([
    {
      id,
      attributes: {
        label: id,
        content: id,
        x: 0,
        y: 0,
        size: 8,
        color: "#63E6FF",
        baseColor: "#63E6FF",
        nodeType: semanticGroup,
        semanticGroup,
        properties: {},
      },
    },
  ]);
}

function setNodePosition(id: string, x: number, y: number) {
  graph.mergeNodeAttributes(id, { x, y });
}

function addEdge(id: string, source: string, target: string, weight = 1) {
  batchMergeEdges([
    {
      id,
      source,
      target,
      attributes: {
        edgeType: "related_to",
        weight,
        properties: {},
      },
    },
  ]);
}

test.beforeEach(() => {
  clearGraph();
});

test.after(() => {
  clearGraph();
});

test("resolveEdgeVisualState caps selected-node incident edge promotion", () => {
  const uncappedState = resolveEdgeVisualState(
    "edge-1",
    "hub",
    "leaf",
    "inspection",
    null,
    "hub",
    "",
    new Set(["hub", "leaf"]),
    new Set(),
    new Set(),
  );
  assert.equal(uncappedState, "muted");

  const cappedState = resolveEdgeVisualState(
    "edge-1",
    "hub",
    "leaf",
    "inspection",
    null,
    "hub",
    "",
    new Set(["hub", "leaf"]),
    new Set(),
    new Set(["edge-1"]),
  );
  assert.equal(cappedState, "selected");
});

test("resolveEdgeElementStyle applies full-graph LOD to directional background edges", () => {
  const style = resolveEdgeElementStyle(
    GRAPH_THEME,
    "overview",
    "default",
    {
      edgeType: "related_to",
      weight: 1,
      properties: {},
      edgeVariant: "directional",
      visualPriority: 0.1,
      baseSize: 0.5,
    },
    "source",
    "target",
    "full",
    "directional-low-priority",
  );

  assert.equal(style.hidden, true);
});

test("classifyFullGraphEdge applies deterministic priority order", () => {
  const edgeClass = classifyFullGraphEdge(
    "edge-priority",
    "source",
    "target",
    "inspection",
    "source",
    "source",
    "edge-priority",
    new Set(["source", "target"]),
    new Set(["edge-priority"]),
    new Set(["edge-priority"]),
    new Set(["edge-priority"]),
    { label: "source", x: 0, y: 0, size: 1, color: "#fff", nodeType: "gene", content: "source", semanticGroup: "gene", properties: {} },
    { label: "target", x: 0, y: 0, size: 1, color: "#fff", nodeType: "disease", content: "target", semanticGroup: "disease", properties: {} },
  );

  assert.equal(edgeClass, "path");

  const selectedClass = classifyFullGraphEdge(
    "edge-priority",
    "source",
    "target",
    "inspection",
    "source",
    "source",
    "edge-priority",
    new Set(["source", "target"]),
    new Set(),
    new Set(["edge-priority"]),
  );

  assert.equal(selectedClass, "selected");
});

test("classifyFullGraphEdge separates capped local context from muted hub edges", () => {
  const mutedClass = classifyFullGraphEdge(
    "hub-edge",
    "hub",
    "leaf",
    "inspection",
    null,
    "hub",
    "",
    new Set(["hub", "leaf"]),
    new Set(),
    new Set(),
  );

  assert.equal(mutedClass, "muted");

  const localContextClass = classifyFullGraphEdge(
    "hub-edge",
    "hub",
    "leaf",
    "inspection",
    null,
    "hub",
    "",
    new Set(["hub", "leaf"]),
    new Set(),
    new Set(["hub-edge"]),
  );

  assert.equal(localContextClass, "local-context");
});

test("classifyFullGraphEdge marks curated bridge and backbone candidates", () => {
  const bridgeClass = classifyFullGraphEdge(
    "curated-bridge",
    "source",
    "target",
    "overview",
    null,
    "",
    "",
    new Set(),
    new Set(),
    new Set(),
    new Set(["curated-bridge"]),
    { label: "source", x: 0, y: 0, size: 1, color: "#fff", nodeType: "gene", content: "source", semanticGroup: "gene", properties: {} },
    { label: "target", x: 0, y: 0, size: 1, color: "#fff", nodeType: "disease", content: "target", semanticGroup: "disease", properties: {} },
  );

  assert.equal(bridgeClass, "bridge");

  const backboneClass = classifyFullGraphEdge(
    "curated-backbone",
    "source",
    "target",
    "overview",
    null,
    "",
    "",
    new Set(),
    new Set(),
    new Set(),
    new Set(["curated-backbone"]),
    { label: "source", x: 0, y: 0, size: 1, color: "#fff", nodeType: "gene", content: "source", semanticGroup: "gene", properties: {} },
    { label: "target", x: 0, y: 0, size: 1, color: "#fff", nodeType: "gene", content: "target", semanticGroup: "gene", properties: {} },
  );

  assert.equal(backboneClass, "backbone");
});

test("classifyFullGraphEdge hides ordinary full-graph overview edges", () => {
  const edgeClass = classifyFullGraphEdge(
    "ordinary-edge",
    "source",
    "target",
    "overview",
    null,
    "",
    "",
    new Set(),
    new Set(),
    new Set(),
  );

  assert.equal(edgeClass, "hidden");
});

test("mapFullEdgeClassToVisualState renders curated backbone and bridge as backbone", () => {
  assert.equal(
    mapFullEdgeClassToVisualState("backbone", { hoveredNodeId: null, hasActiveInteraction: false }),
    "backbone",
  );
  assert.equal(
    mapFullEdgeClassToVisualState("bridge", { hoveredNodeId: null, hasActiveInteraction: false }),
    "backbone",
  );
  assert.equal(
    mapFullEdgeClassToVisualState("hidden", { hoveredNodeId: null, hasActiveInteraction: false }),
    "inactive",
  );
});

test("resolveEdgeElementStyle renders curated full-graph backbone quietly", () => {
  const style = resolveEdgeElementStyle(
    GRAPH_THEME,
    "overview",
    "backbone",
    {
      edgeType: "related_to",
      weight: 2,
      properties: {},
      visualPriority: 0.9,
      baseSize: 0.8,
    },
    "source",
    "target",
    "full",
    "curated-backbone-edge",
    "backbone",
  );

  assert.equal(style.hidden, false);
  assert.equal(style.type, "line");
  assert.match(style.color ?? "", /rgba\(.+,\s*0\.08\)/);
  assert.ok(Number(style.size ?? 0) <= GRAPH_THEME.edges.fullGraphStructure.backboneMaxSize);
});

test("resolveEdgeElementStyle renders high-value bridge as a calm curved teal edge", () => {
  const style = resolveEdgeElementStyle(
    GRAPH_THEME,
    "overview",
    "backbone",
    {
      edgeType: "related_to",
      weight: 4,
      properties: {},
      visualPriority: 0.95,
      baseSize: 0.9,
      edgeVariant: "line",
    },
    "source",
    "target",
    "full",
    "curated-bridge-edge",
    "bridge",
  );

  assert.equal(style.hidden, false);
  assert.equal(style.type, "curve");
  assert.notEqual(style.type, "arrow");
  assert.match(style.color ?? "", /rgba\(.+,\s*0\.14\)/);
  assert.equal(style.curvature, GRAPH_THEME.edges.fullGraphStructure.bridgeCurveStrength);
  assert.ok(Number(style.size ?? 0) <= GRAPH_THEME.edges.fullGraphStructure.bridgeMaxSize);
});

test("resolveEdgeElementStyle keeps low-priority bridge straight", () => {
  const style = resolveEdgeElementStyle(
    GRAPH_THEME,
    "overview",
    "backbone",
    {
      edgeType: "related_to",
      weight: 1,
      properties: {},
      visualPriority: 0.2,
      baseSize: 0.9,
      edgeVariant: "line",
    },
    "source",
    "target",
    "full",
    "low-value-bridge-edge",
    "bridge",
  );

  assert.equal(style.hidden, false);
  assert.equal(style.type, "line");
  assert.equal(style.curvature, 0);
});

test("evaluateGraphStructureLayerGate enables only sparse settled full-graph structure", () => {
  const counts: GraphFullEdgeClassCounts = {
    hidden: 20,
    backbone: 6,
    bridge: 4,
    "local-context": 0,
    selected: 0,
    path: 0,
    muted: 0,
  };

  assert.deepEqual(
    evaluateGraphStructureLayerGate({
      mode: "auto",
      viewMode: "grouped",
      isLayoutRunning: false,
      edgeDiagnostics: {
        mode: "grouped",
        zoomTier: "overview",
        totalEdges: 30,
        visibleEdges: 10,
        counts,
        updatedAt: 1,
      },
      minimumLiteralEdges: 24,
    }),
    { enabled: false, disabledReason: "non-full-mode" },
  );

  assert.deepEqual(
    evaluateGraphStructureLayerGate({
      mode: "auto",
      viewMode: "full",
      isLayoutRunning: true,
      edgeDiagnostics: {
        mode: "full",
        zoomTier: "overview",
        totalEdges: 30,
        visibleEdges: 10,
        counts,
        updatedAt: 1,
      },
      minimumLiteralEdges: 24,
    }),
    { enabled: false, disabledReason: "layout-running" },
  );

  assert.deepEqual(
    evaluateGraphStructureLayerGate({
      mode: "auto",
      viewMode: "full",
      isLayoutRunning: false,
      edgeDiagnostics: {
        mode: "full",
        zoomTier: "overview",
        totalEdges: 30,
        visibleEdges: 24,
        counts: { ...counts, backbone: 18, bridge: 6 },
        updatedAt: 1,
      },
      minimumLiteralEdges: 24,
    }),
    { enabled: false, disabledReason: "enough-literal-edges" },
  );

  assert.deepEqual(
    evaluateGraphStructureLayerGate({
      mode: "auto",
      viewMode: "full",
      isLayoutRunning: false,
      edgeDiagnostics: {
        mode: "full",
        zoomTier: "overview",
        totalEdges: 30,
        visibleEdges: 10,
        counts,
        updatedAt: 1,
      },
      minimumLiteralEdges: 24,
    }),
    { enabled: true, disabledReason: null },
  );
});

test("buildGraphStructureCurveCache prefers bridges, caps curves, and skips invalid endpoints", () => {
  addNode("a", "gene");
  addNode("b", "disease");
  addNode("c", "gene");
  addNode("d", "compound");
  setNodePosition("a", 0, 0);
  setNodePosition("b", 100, 0);
  setNodePosition("c", 0, 100);
  setNodePosition("d", Number.NaN, 100);

  addEdge("backbone-1", "a", "c", 1);
  graph.mergeEdgeAttributes("backbone-1", { visualPriority: 1 });
  addEdge("bridge-1", "a", "b", 0.2);
  graph.mergeEdgeAttributes("bridge-1", { visualPriority: 0.1 });
  addEdge("selected-1", "b", "c", 1);
  graph.mergeEdgeAttributes("selected-1", { visualPriority: 1 });
  addEdge("invalid-bridge", "a", "d", 1);
  graph.mergeEdgeAttributes("invalid-bridge", { visualPriority: 1 });

  const edgeClasses = new Map<string, GraphFullEdgeClass>([
    ["backbone-1", "backbone"],
    ["bridge-1", "bridge"],
    ["selected-1", "selected"],
    ["invalid-bridge", "bridge"],
  ]);

  const capped = buildGraphStructureCurveCache({
    graphRef: graph,
    cacheKey: "test-cache",
    classifyEdge: (edgeId) => edgeClasses.get(edgeId) ?? "hidden",
    maxCurves: 1,
    curveStrength: 0.12,
  });

  assert.equal(capped.curves.length, 1);
  assert.equal(capped.curves[0].edgeId, "bridge-1");
  assert.equal(capped.bridgeCurveCount, 1);
  assert.equal(capped.backboneCurveCount, 0);

  const uncapped = buildGraphStructureCurveCache({
    graphRef: graph,
    cacheKey: "test-cache-all",
    classifyEdge: (edgeId) => edgeClasses.get(edgeId) ?? "hidden",
    maxCurves: 10,
    curveStrength: 0.12,
  });

  assert.deepEqual(
    uncapped.curves.map((curve) => curve.edgeId).sort(),
    ["backbone-1", "bridge-1"],
  );
});

test("resolveEdgeVisualState suppresses automatic overview backbone in clean baseline", () => {
  const state = resolveEdgeVisualState(
    "overview-backbone-high-priority",
    "source",
    "target",
    "overview",
    null,
    "",
    "",
    new Set(),
    new Set(),
  );

  assert.equal(state, "inactive");
});

test("resolveEdgeElementStyle keeps full-graph selected and path edges controlled", () => {
  const selectedStyle = resolveEdgeElementStyle(
    GRAPH_THEME,
    "inspection",
    "selected",
    {
      edgeType: "related_to",
      weight: 2,
      properties: {},
      visualPriority: 0.9,
      baseSize: 0.8,
    },
    "source",
    "target",
    "full",
    "selected-context-edge",
  );
  const pathStyle = resolveEdgeElementStyle(
    GRAPH_THEME,
    "inspection",
    "path",
    {
      edgeType: "causes",
      weight: 2,
      properties: {},
      visualPriority: 0.9,
      baseSize: 0.8,
    },
    "source",
    "target",
    "full",
    "path-context-edge",
  );

  assert.equal(selectedStyle.hidden, false);
  assert.match(selectedStyle.color ?? "", /rgba\(.+,\s*0\.6\)/);
  assert.equal(pathStyle.hidden, false);
  assert.match(pathStyle.color ?? "", /rgba\(.+,\s*0\.76\)/);
});

test("buildGraphAnalyticsSnapshot emits a readable capped overview backbone", () => {
  const semanticGroups = ["gene/protein", "disease", "drug", "pathway"];
  for (let index = 0; index < 16; index += 1) {
    addNode(`n${index}`, semanticGroups[index % semanticGroups.length]);
  }

  let edgeIndex = 0;
  for (let sourceIndex = 0; sourceIndex < 16; sourceIndex += 1) {
    for (let offset = 1; offset <= 3; offset += 1) {
      const targetIndex = (sourceIndex + offset * 3) % 16;
      if (sourceIndex === targetIndex) {
        continue;
      }
      addEdge(`ambient-edge-${edgeIndex}`, `n${sourceIndex}`, `n${targetIndex}`, 1 + (edgeIndex % 5));
      edgeIndex += 1;
    }
  }

  const base = computeGraphAnalyticsBase(graph, {
    computeCommunities: false,
    computeCentrality: true,
  });
  const analytics = buildGraphAnalyticsSnapshot({
    graphRef: graph,
    interactionState: {
      hoveredNodeId: null,
      selectedNodeId: "",
      selectedEdgeId: "",
      focusedNodeId: "",
      activePath: [],
      activePathEdgeIds: [],
      viewMode: "full",
      zoomTier: "overview",
      isLayoutRunning: false,
    },
    base,
    visibleNodeIds: graph.nodes(),
  });

  assert.equal(analytics.overviewBackbone.ready, true);
  assert.ok(analytics.overviewBackbone.edgeIds.length > 6);
  assert.ok(analytics.overviewBackbone.edgeIds.length <= 128);
});

test("resolveDisplayGraph bundles parallel edges in full view", () => {
  addNode("a");
  addNode("b");
  addEdge("e1", "a", "b", 1);
  addEdge("e2", "a", "b", 2);

  const { graph } = resolveDisplayGraph("", [], [], "full", { aggregationEnabled: true });
  assert.equal(graph.size, 1);

  const edgeId = graph.edges()[0];
  const attrs = graph.getEdgeAttributes(edgeId) as {
    isAggregated?: boolean;
    aggregateCount?: number;
    rawEdgeIds?: string[];
    bundleKind?: string;
  };

  assert.equal(attrs.isAggregated, true);
  assert.equal(attrs.aggregateCount, 2);
  assert.deepEqual(new Set(attrs.rawEdgeIds ?? []), new Set(["e1", "e2"]));
  assert.equal(attrs.bundleKind, "parallel");
});

test("resolveDisplayGraph collapse keeps path neighbor visible", () => {
  addNode("center");
  for (let index = 0; index < 10; index += 1) {
    const neighbor = `n${index}`;
    addNode(neighbor);
    addEdge(`edge-${index}`, "center", neighbor, 1);
  }

  const { state } = resolveDisplayGraph("center", ["center", "n9"], [], "full", {
    aggregationEnabled: false,
    collapsedNeighborhoodNodeIds: ["center"],
  });

  assert.equal(state.selectedRootNodeId, "center");
  assert.equal(state.selectedVisibleNeighborIds.includes("n9"), true);
  assert.equal(state.selectedVisibleNeighborIds.length, 9);
  assert.equal(state.selectedCollapsedNeighborIds.length, 1);
});

test("resolveDisplayGraph grouped view emits community nodes and edges", () => {
  const left = ["a1", "a2", "a3", "a4"];
  const right = ["b1", "b2", "b3", "b4"];

  [...left, ...right].forEach((nodeId, index) => {
    addNode(nodeId, index < left.length ? "left" : "right");
  });

  let edgeIndex = 0;
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < left.length; j += 1) {
      if (i !== j) {
        addEdge(`l-${edgeIndex++}`, left[i], left[j], 3);
      }
    }
  }

  for (let i = 0; i < right.length; i += 1) {
    for (let j = 0; j < right.length; j += 1) {
      if (i !== j) {
        addEdge(`r-${edgeIndex++}`, right[i], right[j], 3);
      }
    }
  }

  addEdge("bridge-1", "a1", "b1", 0.1);
  addEdge("bridge-2", "a2", "b2", 0.1);

  const { graph, state } = resolveDisplayGraph("", [], [], "grouped", { aggregationEnabled: true });

  assert.equal(state.groupedViewAvailable, true);

  const communityNodes = graph.nodes().filter((nodeId) => nodeId.startsWith("__community__"));
  assert.ok(communityNodes.length >= 2);

  const hasCommunityEdge = graph
    .edges()
    .map((edgeId) => graph.getEdgeAttributes(edgeId) as { bundleKind?: string; isAggregated?: boolean; aggregateCount?: number })
    .some((attrs) => attrs.bundleKind === "community" && attrs.isAggregated === true && Number(attrs.aggregateCount ?? 0) > 0);

  assert.equal(hasCommunityEdge, true);
});

// ── resolveGroupedDisplayNodeId ──────────────────────────────────────────────

test("resolveGroupedDisplayNodeId returns null for empty nodeId", () => {
  const { graph: displayGraph } = resolveDisplayGraph("", [], [], "full", { aggregationEnabled: false });
  assert.equal(resolveGroupedDisplayNodeId(displayGraph, ""), null);
});

test("resolveGroupedDisplayNodeId returns nodeId when it exists directly in display graph", () => {
  addNode("x");
  const { graph: displayGraph } = resolveDisplayGraph("", [], [], "full", { aggregationEnabled: false });
  assert.equal(resolveGroupedDisplayNodeId(displayGraph, "x"), "x");
});

test("resolveGroupedDisplayNodeId resolves base node to its community node", () => {
  const left = ["a1", "a2", "a3", "a4"];
  const right = ["b1", "b2", "b3", "b4"];
  [...left, ...right].forEach((nodeId, index) => addNode(nodeId, index < left.length ? "left" : "right"));

  let edgeIndex = 0;
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < left.length; j += 1) {
      if (i !== j) addEdge(`l-${edgeIndex++}`, left[i], left[j], 3);
    }
  }
  for (let i = 0; i < right.length; i += 1) {
    for (let j = 0; j < right.length; j += 1) {
      if (i !== j) addEdge(`r-${edgeIndex++}`, right[i], right[j], 3);
    }
  }
  addEdge("bridge-1", "a1", "b1", 0.1);

  const { graph: displayGraph } = resolveDisplayGraph("", [], [], "grouped", { aggregationEnabled: true });
  const communityNodes = displayGraph.nodes().filter((n) => n.startsWith("__community__"));
  assert.ok(communityNodes.length >= 2, "expected community nodes");

  const resolved = resolveGroupedDisplayNodeId(displayGraph, "a1");
  assert.ok(resolved !== null, "should resolve a1 to a community node");
  assert.ok(resolved!.startsWith("__community__"), "resolved id should be a community node");
});

// ── resolveGroupedDisplayStateSnapshot ──────────────────────────────────────

test("resolveGroupedDisplayStateSnapshot returns none-kind when no node selected", () => {
  addNode("p");
  addNode("q");
  addEdge("e1", "p", "q");
  const { graph: displayGraph } = resolveDisplayGraph("", [], [], "full", { aggregationEnabled: false });
  const state = resolveGroupedDisplayStateSnapshot(displayGraph, "", {
    groupedViewAvailable: true,
    groupedViewReason: null,
  });
  assert.equal(state.selectedNodeKind, "none");
  assert.equal(state.selectedRootNodeId, null);
});

test("resolveGroupedDisplayStateSnapshot maps selected base node to community in grouped graph", () => {
  const left = ["c1", "c2", "c3", "c4"];
  const right = ["d1", "d2", "d3", "d4"];
  [...left, ...right].forEach((nodeId, index) => addNode(nodeId, index < left.length ? "left" : "right"));

  let edgeIndex = 0;
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < left.length; j += 1) {
      if (i !== j) addEdge(`lc-${edgeIndex++}`, left[i], left[j], 3);
    }
  }
  for (let i = 0; i < right.length; i += 1) {
    for (let j = 0; j < right.length; j += 1) {
      if (i !== j) addEdge(`rc-${edgeIndex++}`, right[i], right[j], 3);
    }
  }
  addEdge("bridge-c1", "c1", "d1", 0.1);
  addEdge("bridge-c2", "c2", "d2", 0.1);

  const { graph: displayGraph } = resolveDisplayGraph("", [], [], "grouped", { aggregationEnabled: true });
  const state = resolveGroupedDisplayStateSnapshot(displayGraph, "c1", {
    groupedViewAvailable: true,
    groupedViewReason: null,
    selectedNodeKind: "grouped",
  });

  assert.ok(state.selectedRootNodeId !== null, "should resolve to a community node");
  assert.ok(state.selectedRootNodeId!.startsWith("__community__"), "root should be a community node");
  assert.equal(state.groupedViewAvailable, true);
});

// ── checkGroupedViewAvailability ─────────────────────────────────────────────

test("checkGroupedViewAvailability returns unavailable on empty graph", () => {
  const result = checkGroupedViewAvailability();
  assert.equal(result.available, false);
  assert.ok(typeof result.reason === "string" && result.reason.length > 0);
});

test("checkGroupedViewAvailability returns available when communities exist", () => {
  const left = ["e1", "e2", "e3", "e4"];
  const right = ["f1", "f2", "f3", "f4"];
  [...left, ...right].forEach((nodeId, index) => addNode(nodeId, index < left.length ? "left" : "right"));

  let edgeIndex = 0;
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < left.length; j += 1) {
      if (i !== j) addEdge(`le-${edgeIndex++}`, left[i], left[j], 3);
    }
  }
  for (let i = 0; i < right.length; i += 1) {
    for (let j = 0; j < right.length; j += 1) {
      if (i !== j) addEdge(`re-${edgeIndex++}`, right[i], right[j], 3);
    }
  }
  addEdge("bridge-e1", "e1", "f1", 0.1);

  const result = checkGroupedViewAvailability();
  assert.equal(result.available, true);
  assert.equal(result.reason, null);
});

