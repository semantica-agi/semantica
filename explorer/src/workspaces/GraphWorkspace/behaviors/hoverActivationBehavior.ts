import type { GraphBehavior } from "./types";

export const hoverActivationBehavior: GraphBehavior = {
  id: "hover-activation",
  attach: () => {},
  detach: () => {},
  onNodeEnter: (context, nodeId) => {
    context.setHoveredNodeId(nodeId);
  },
  onNodeLeave: (context, nodeId) => {
    if (context.getInteractionState().hoveredNodeId === nodeId) {
      context.setHoveredNodeId(null);
    }
  },
};
