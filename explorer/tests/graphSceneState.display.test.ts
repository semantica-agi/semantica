import test from "node:test";
import assert from "node:assert/strict";

import {
  batchMergeEdges,
  batchMergeNodes,
  clearGraph,
} from "../src/store/graphStore.ts";
import {
  checkGroupedViewAvailability,
  resolveDisplayGraph,
  resolveGroupedDisplayNodeId,
  resolveGroupedDisplayStateSnapshot,
} from "../src/workspaces/GraphWorkspace/graphSceneState.ts";

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
