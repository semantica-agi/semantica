import type { GraphBehavior } from "./types";

export const focusCameraBehavior: GraphBehavior = {
  id: "focus-camera",
  attach: () => {},
  detach: () => {},
  performAction: (context, action) => {
    if (action.type === "focusNode") {
      context.focusNodeInView(action.nodeId);
      return true;
    }

    if (action.type === "centerSelection") {
      context.centerSelectionInView(action.nodeId);
      return true;
    }

    if (action.type === "centerFocusedSelection") {
      context.centerFocusedSelectionInView(action.nodeId);
      return true;
    }

    if (action.type === "centerGroupedSelection") {
      context.centerGroupedSelectionInView(action.nodeId);
      return true;
    }

    return false;
  },
};
