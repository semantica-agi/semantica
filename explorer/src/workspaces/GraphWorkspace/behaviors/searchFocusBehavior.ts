import type { GraphBehavior } from "./types";

export function createSearchFocusBehavior(): GraphBehavior {
  let lastSelectedNodeId = "";
  let lastViewMode = "";

  return {
    id: "search-focus",
    attach: () => {},
    detach: () => {
      lastSelectedNodeId = "";
      lastViewMode = "";
    },
    onStateChange: (context, interactionState) => {
      const nextSelectedNodeId = interactionState.selectedNodeId;
      const nextViewMode = interactionState.viewMode;
      if (nextViewMode !== lastViewMode) {
        lastViewMode = nextViewMode;
        lastSelectedNodeId = nextSelectedNodeId;
        return;
      }
      if (!nextSelectedNodeId || nextSelectedNodeId === lastSelectedNodeId) {
        lastSelectedNodeId = nextSelectedNodeId;
        lastViewMode = nextViewMode;
        return;
      }

      lastSelectedNodeId = nextSelectedNodeId;
      lastViewMode = nextViewMode;
      context.dispatchAction({
        type: nextViewMode === "grouped" ? "centerGroupedSelection" : "centerSelection",
        nodeId: nextSelectedNodeId,
      });
    },
  };
}
