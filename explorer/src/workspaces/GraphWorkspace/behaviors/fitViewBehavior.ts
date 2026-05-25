import type { GraphBehavior } from "./types";

export const fitViewBehavior: GraphBehavior = {
  id: "fit-view",
  attach: () => {},
  detach: () => {},
  performAction: (context, action) => {
    if (action.type !== "fitView") {
      return false;
    }

    context.fitCurrentView();
    return true;
  },
};
