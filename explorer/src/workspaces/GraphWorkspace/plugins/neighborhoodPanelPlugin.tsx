import type { CSSProperties } from "react";

import type { GraphPlugin } from "./types";

const NEIGHBORHOOD_PANEL_ID = "neighborhood-panel";
const MAX_NEIGHBORS = 10;

function maxWeightBetween(graphRef: any, sourceId: string, targetId: string): number {
  let weight = 0;
  graphRef.forEachDirectedEdge(sourceId, targetId, (_edgeId: string, attrs: { weight?: number }) => {
    weight = Math.max(weight, Number(attrs.weight ?? 0));
  });
  return weight;
}

function formatNeighborMeta(neighbor: { nodeType: string; degree: number; weight: number }) {
  const parts = [neighbor.nodeType, `degree ${neighbor.degree}`];
  if (neighbor.weight > 0) {
    parts.push(`weight ${neighbor.weight.toFixed(2)}`);
  }
  return parts.join(" · ");
}

export const neighborhoodPanelPlugin: GraphPlugin = {
  id: "neighborhood-panel",
  mount: () => {},
  unmount: () => {},
  onStateChange: () => {},
  toolbarItems: (context) => [
    {
      id: "neighborhood-toggle",
      label: "Neighbors",
      title: "Toggle neighborhood panel",
      active: context.isPanelOpen(NEIGHBORHOOD_PANEL_ID),
      order: 30,
      onClick: () => context.dispatchAction({ type: "togglePanel", panelId: NEIGHBORHOOD_PANEL_ID }),
    },
  ],
  renderPanel: (context) => {
    if (!context.isPanelOpen(NEIGHBORHOOD_PANEL_ID)) {
      return null;
    }

    const selected = context.getSelectedNodeState();
    const displayState = context.getDisplayState();
    if (!selected) {
      return {
        id: NEIGHBORHOOD_PANEL_ID,
        title: "Neighborhood",
        placement: "bottom",
        order: 20,
        defaultOpen: false,
        preferredWidth: 360,
        preferredHeight: 260,
        content: <div style={emptyTextStyle}>Select a node to inspect its local neighborhood.</div>,
      };
    }

    const neighbors = context.graph
      .neighbors(selected.id)
      .map((neighborId) => {
        const attrs = context.graph.getNodeAttributes(neighborId);
        const weight = Math.max(
          maxWeightBetween(context.graph, selected.id, neighborId),
          maxWeightBetween(context.graph, neighborId, selected.id),
        );
        return {
          id: neighborId,
          label: String(attrs.label || neighborId),
          nodeType: String(attrs.nodeType || "Entity"),
          color: String(attrs.baseColor || attrs.color || context.theme.palette.semantic[0]),
          weight,
          degree: context.graph.degree(neighborId),
        };
      })
      .sort((left, right) => {
        if (right.weight !== left.weight) {
          return right.weight - left.weight;
        }
        if (right.degree !== left.degree) {
          return right.degree - left.degree;
        }
        return left.label.localeCompare(right.label);
      })
      .slice(0, MAX_NEIGHBORS);
    const hiddenNeighborCount = displayState.selectedCollapsedNeighborIds.length;
    const aggregatedEdgeCount = context.displayGraph
      .edges()
      .map((edgeId) => context.displayGraph.getEdgeAttributes(edgeId) as { isAggregated?: boolean })
      .filter((attrs) => attrs.isAggregated).length;

    return {
      id: NEIGHBORHOOD_PANEL_ID,
      title: "Neighborhood",
      placement: "bottom",
      order: 20,
      defaultOpen: false,
      preferredWidth: 360,
      preferredHeight: 260,
      content: (
        <div style={panelBodyStyle}>
          <div style={panelEyebrowStyle}>{selected.label}</div>
          <div style={summaryStyle}>
            {selected.neighborCount.toLocaleString()} direct neighbors in the full graph
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => context.dispatchAction({ type: "collapseNeighborhood" })}
              disabled={!selected.canCollapseNeighborhood || selected.isNeighborhoodCollapsed}
              style={controlButtonStyle}
            >
              Collapse Neighborhood
            </button>
            <button
              type="button"
              onClick={() => context.dispatchAction({ type: "expandNeighborhood" })}
              disabled={!selected.isNeighborhoodCollapsed}
              style={controlButtonStyle}
            >
              Expand Neighborhood
            </button>
          </div>
          {hiddenNeighborCount > 0 ? (
            <div style={summaryStyle}>
              {hiddenNeighborCount.toLocaleString()} lower-priority neighbors are collapsed in the current view.
            </div>
          ) : null}
          {aggregatedEdgeCount > 0 ? (
            <div style={summaryStyle}>
              {aggregatedEdgeCount.toLocaleString()} aggregated structural bundle{aggregatedEdgeCount === 1 ? "" : "s"} visible.
            </div>
          ) : null}
          {neighbors.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {neighbors.map((neighbor) => (
                <button
                  key={neighbor.id}
                  type="button"
                  onClick={() => context.dispatchAction({ type: "selectNode", nodeId: neighbor.id })}
                  style={neighborButtonStyle}
                >
                  <span
                    style={{
                      ...swatchStyle,
                      background: neighbor.color,
                      boxShadow: `0 0 16px ${neighbor.color}40`,
                    }}
                  />
                  <div style={{ minWidth: 0, flex: 1, textAlign: "left" }}>
                    <div style={rowTitleStyle}>{neighbor.label}</div>
                    <div style={rowMetaStyle}>{formatNeighborMeta(neighbor)}</div>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div style={emptyTextStyle}>No direct neighbors are available for this node.</div>
          )}
        </div>
      ),
    };
  },
};

const panelBodyStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 12,
};

const panelEyebrowStyle: CSSProperties = {
  color: "#f3f7fd",
  fontSize: 14,
  fontWeight: 700,
};

const summaryStyle: CSSProperties = {
  color: "#8ea4be",
  fontSize: 12,
  lineHeight: 1.5,
};

const neighborButtonStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  width: "100%",
  padding: "8px 10px",
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.06)",
  borderRadius: 12,
  cursor: "pointer",
};

const controlButtonStyle: CSSProperties = {
  padding: "7px 10px",
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  color: "#dce7f4",
  cursor: "pointer",
  fontSize: 12,
};

const swatchStyle: CSSProperties = {
  width: 10,
  height: 10,
  borderRadius: 999,
  flexShrink: 0,
};

const rowTitleStyle: CSSProperties = {
  color: "#f3f7fd",
  fontSize: 13,
  fontWeight: 600,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const rowMetaStyle: CSSProperties = {
  color: "#8ea4be",
  fontSize: 12,
};

const emptyTextStyle: CSSProperties = {
  color: "#8ea4be",
  fontSize: 12,
  lineHeight: 1.5,
};
