import test from "node:test";
import assert from "node:assert/strict";
import Graph from "graphology";

import { curveGroupForPair, pairRegistryKey } from "../src/store/edgePairKeys.js";

function normalizeParallelMetadataForPair(graph, source, target) {
  const edgeIds = [];
  graph.forEachDirectedEdge(source, target, (edgeId) => {
    edgeIds.push(String(edgeId));
  });

  const pairCount = edgeIds.length;
  const familyCounts = new Map();
  edgeIds.forEach((edgeId) => {
    const attrs = graph.getEdgeAttributes(edgeId);
    const familyId = String(attrs.familyId || edgeId);
    familyCounts.set(familyId, (familyCounts.get(familyId) ?? 0) + 1);
  });

  edgeIds
    .sort((left, right) => left.localeCompare(right))
    .forEach((edgeId, index) => {
      const attrs = graph.getEdgeAttributes(edgeId);
      const familyId = String(attrs.familyId || edgeId);
      graph.mergeEdgeAttributes(edgeId, {
        edgeId,
        familyId,
        sourceId: source,
        targetId: target,
        isParallelPair: pairCount > 1,
        parallelIndex: index,
        parallelCount: pairCount,
        familySize: familyCounts.get(familyId) ?? 1,
        curveGroup: curveGroupForPair(source, target),
      });
    });
}

function batchMergeEdges(graph, edges) {
  const touchedPairs = new Map();

  for (const { id, familyId, source, target, attributes } of edges) {
    const edgeId = String(attributes.edgeId || id);
    const resolvedFamilyId = String(attributes.familyId || familyId || edgeId);

    if (graph.hasNode(source) && graph.hasNode(target)) {
      graph.mergeDirectedEdgeWithKey(edgeId, source, target, {
        ...attributes,
        edgeId,
        familyId: resolvedFamilyId,
        sourceId: source,
        targetId: target,
      });
      touchedPairs.set(pairRegistryKey(source, target), { source, target });
    }
  }

  touchedPairs.forEach(({ source, target }) => {
    normalizeParallelMetadataForPair(graph, source, target);
  });
}

test("structured pair keys support node ids containing double colons", () => {
  const graph = new Graph({ type: "directed", multi: true, allowSelfLoops: false });

  graph.addNode("gene/protein::10");
  graph.addNode("gene/protein::472");
  graph.addNode("gene/protein::500");

  assert.doesNotThrow(() => {
    batchMergeEdges(graph, [
      {
        id: "edge-a",
        familyId: "family-1",
        source: "gene/protein::10",
        target: "gene/protein::472",
        attributes: { edgeType: "protein_protein", weight: 1, properties: {} },
      },
      {
        id: "edge-b",
        familyId: "family-2",
        source: "gene/protein::10",
        target: "gene/protein::472",
        attributes: { edgeType: "protein_protein", weight: 1, properties: {} },
      },
      {
        id: "edge-c",
        familyId: "family-3",
        source: "gene/protein::10",
        target: "gene/protein::500",
        attributes: { edgeType: "protein_protein", weight: 1, properties: {} },
      },
    ]);
  });

  const edgeA = graph.getEdgeAttributes("edge-a");
  const edgeB = graph.getEdgeAttributes("edge-b");
  const edgeC = graph.getEdgeAttributes("edge-c");

  assert.equal(edgeA.sourceId, "gene/protein::10");
  assert.equal(edgeA.targetId, "gene/protein::472");
  assert.equal(edgeA.parallelCount, 2);
  assert.equal(edgeB.parallelCount, 2);
  assert.equal(edgeA.isParallelPair, true);
  assert.equal(edgeB.isParallelPair, true);
  assert.equal(edgeC.parallelCount, 1);
  assert.equal(edgeC.isParallelPair, false);
  assert.equal(edgeA.curveGroup, JSON.stringify(["gene/protein::10", "gene/protein::472"]));
  assert.equal(edgeC.curveGroup, JSON.stringify(["gene/protein::10", "gene/protein::500"]));
});
