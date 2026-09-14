import type { GraphViewMode } from "./types";

export function localGraphRequiresDraftConfirm(
  viewMode: GraphViewMode,
  selectedNodeId: string,
  resolvedNodeId: string,
): boolean {
  return viewMode !== "focused" || resolvedNodeId !== selectedNodeId;
}
