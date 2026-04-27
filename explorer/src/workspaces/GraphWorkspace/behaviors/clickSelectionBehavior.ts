import type { GraphBehavior } from "./types";

export const clickSelectionBehavior: GraphBehavior = {
  id: "click-selection",
  attach: () => {},
  detach: () => {},
  onNodeClick: (context, nodeId) => {
    context.setHoveredNodeId(nodeId);
    context.onEdgeSelectionChange("");
    if (context.getInteractionState().selectedNodeId === nodeId) {
      context.onNodeSelectionChange("");
    } else {
      context.onNodeSelectionChange(nodeId);
    }
  },
  onEdgeClick: (context, edgeId) => {
    context.setHoveredNodeId(null);
    if (context.getInteractionState().selectedEdgeId === edgeId) {
      context.onEdgeSelectionChange("");
    } else {
      context.onEdgeSelectionChange(edgeId);
    }
  },
  onStageClick: (context) => {
    context.setHoveredNodeId(null);
    context.onEdgeSelectionChange("");
    context.onNodeSelectionChange("");
  },
};
