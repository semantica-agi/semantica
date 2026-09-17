import type { FocusedUnavailableReason, GroupedViewUnavailableReason } from "./types";

const GROUPED_VIEW_COPY = {
  "communities-undetected": "Grouped view is unavailable until communities can be detected.",
  "community-nodes-missing": "Grouped view is unavailable because no community nodes could be created.",
} as const;

const FOCUSED_MODE_COPY = {
  "no-selection": "Select a node to inspect in Focused mode.",
  "grouped-unresolvable": "Focused mode is unavailable for this grouped selection.",
  "not-in-graph": "Selected item is not available in the current graph.",
} as const;

export function groupedViewReasonText(
  reason: GroupedViewUnavailableReason | null | undefined,
): string | null {
  if (!reason) {
    return null;
  }

  switch (reason.code) {
    case "communities-undetected":
      return GROUPED_VIEW_COPY["communities-undetected"];
    case "community-nodes-missing":
      return GROUPED_VIEW_COPY["community-nodes-missing"];
    case "invalid-community-layout":
      return `Grouped node ${reason.nodeId} has invalid coordinates.`;
    case "missing-grouped-node":
      return `Grouped edge ${reason.edgeId} references a missing grouped node.`;
  }
}

export function focusedUnavailableReasonText(
  reason: FocusedUnavailableReason | null | undefined,
): string | null {
  if (!reason) {
    return null;
  }

  return FOCUSED_MODE_COPY[reason.code];
}
