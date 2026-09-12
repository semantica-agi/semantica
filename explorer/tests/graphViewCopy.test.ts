import assert from "node:assert/strict";
import test from "node:test";

import {
  focusedUnavailableReasonText,
  groupedViewReasonText,
} from "../src/workspaces/GraphWorkspace/graphViewCopy.ts";

test("groupedViewReasonText owns grouped-view copy for every reason code", () => {
  assert.equal(
    groupedViewReasonText({ code: "communities-undetected" }),
    "Grouped view is unavailable until communities can be detected.",
  );
  assert.equal(
    groupedViewReasonText({ code: "community-nodes-missing" }),
    "Grouped view is unavailable because no community nodes could be created.",
  );
  assert.equal(
    groupedViewReasonText({ code: "invalid-community-layout", nodeId: "community-a" }),
    "Grouped node community-a has invalid coordinates.",
  );
  assert.equal(
    groupedViewReasonText({ code: "missing-grouped-node", edgeId: "edge-1" }),
    "Grouped edge edge-1 references a missing grouped node.",
  );
  assert.equal(groupedViewReasonText(null), null);
});

test("focusedUnavailableReasonText owns focused-mode copy for every reason code", () => {
  assert.equal(
    focusedUnavailableReasonText({ code: "no-selection" }),
    "Select a node to inspect in Focused mode.",
  );
  assert.equal(
    focusedUnavailableReasonText({ code: "grouped-unresolvable" }),
    "Focused mode is unavailable for this grouped selection.",
  );
  assert.equal(
    focusedUnavailableReasonText({ code: "not-in-graph" }),
    "Selected item is not available in the current graph.",
  );
  assert.equal(focusedUnavailableReasonText(null), null);
});
