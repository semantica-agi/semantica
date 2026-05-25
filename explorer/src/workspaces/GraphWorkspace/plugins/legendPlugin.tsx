import type { CSSProperties } from "react";

import type { GraphPlugin } from "./types";

const LEGEND_PANEL_ID = "legend-panel";
const MAX_GROUPS = 8;

export const legendPlugin: GraphPlugin = {
  id: "legend",
  mount: () => {},
  unmount: () => {},
  onStateChange: () => {},
  toolbarItems: (context) => [
    {
      id: "legend-toggle",
      label: "Legend",
      title: "Toggle semantic legend",
      active: context.isPanelOpen(LEGEND_PANEL_ID),
      order: 20,
      onClick: () => context.dispatchAction({ type: "togglePanel", panelId: LEGEND_PANEL_ID }),
    },
  ],
  renderPanel: (context) => {
    if (!context.isPanelOpen(LEGEND_PANEL_ID)) {
      return null;
    }

    const groups = new Map<string, { count: number; color: string }>();
    context.graph.forEachNode((_nodeId, attrs) => {
      const semanticGroup = String(attrs.semanticGroup || attrs.nodeType || "entity");
      const color = String(attrs.baseColor || context.theme.palette.semantic[0]);
      const current = groups.get(semanticGroup);
      groups.set(semanticGroup, {
        count: (current?.count ?? 0) + 1,
        color,
      });
    });

    const items = [...groups.entries()]
      .map(([group, data]) => ({ group, ...data }))
      .sort((left, right) => right.count - left.count)
      .slice(0, MAX_GROUPS);

    return {
      id: LEGEND_PANEL_ID,
      title: "Legend",
      placement: "bottom",
      order: 10,
      defaultOpen: false,
      preferredWidth: 320,
      preferredHeight: 220,
      content: (
        <div style={panelBodyStyle}>
          <div style={panelEyebrowStyle}>Semantic groups</div>
          {items.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {items.map((item) => (
                <div key={item.group} style={legendRowStyle}>
                  <span
                    style={{
                      ...swatchStyle,
                      background: item.color,
                      boxShadow: `0 0 0 1px rgba(255,255,255,0.06), 0 0 18px ${item.color}44`,
                    }}
                  />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={rowTitleStyle}>{item.group}</div>
                    <div style={rowMetaStyle}>{item.count.toLocaleString()} nodes</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={emptyTextStyle}>Legend will populate when the graph metadata is available.</div>
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
  color: "#8ea4be",
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
};

const legendRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "8px 10px",
  borderRadius: 12,
  border: "1px solid rgba(255,255,255,0.06)",
  background: "rgba(255,255,255,0.025)",
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
