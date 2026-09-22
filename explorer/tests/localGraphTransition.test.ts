import assert from "node:assert/strict";
import test from "node:test";

import { localGraphRequiresDraftConfirm } from "../src/workspaces/GraphWorkspace/localGraphTransition.ts";
import type { GraphViewMode } from "../src/workspaces/GraphWorkspace/types.ts";

test("localGraphRequiresDraftConfirm prompts when enterLocalGraph would change mode or Markdown resource", () => {
  const cases: Array<{
    viewMode: GraphViewMode;
    selectedNodeId: string;
    resolvedNodeId: string;
    expected: boolean;
  }> = [
    { viewMode: "focused", selectedNodeId: "n1", resolvedNodeId: "n1", expected: false },
    { viewMode: "focused", selectedNodeId: "n1", resolvedNodeId: "n2", expected: true },
    { viewMode: "focused", selectedNodeId: "", resolvedNodeId: "n1", expected: true },
    { viewMode: "full", selectedNodeId: "n1", resolvedNodeId: "n1", expected: true },
    { viewMode: "full", selectedNodeId: "n1", resolvedNodeId: "n2", expected: true },
    { viewMode: "grouped", selectedNodeId: "community-1", resolvedNodeId: "n1", expected: true },
    { viewMode: "grouped", selectedNodeId: "n1", resolvedNodeId: "n1", expected: true },
  ];

  for (const row of cases) {
    assert.equal(
      localGraphRequiresDraftConfirm(row.viewMode, row.selectedNodeId, row.resolvedNodeId),
      row.expected,
      JSON.stringify(row),
    );
  }
});
