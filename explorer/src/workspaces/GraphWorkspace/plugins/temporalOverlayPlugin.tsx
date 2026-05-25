import type { CSSProperties } from "react";

import type { GraphPlugin } from "./types";

const TEMPORAL_PANEL_ID = "temporal-panel";

function formatTemporalLabel(value: Date | null) {
  if (!value) {
    return "No time selected";
  }
  return `${value.getFullYear()}/${String(value.getMonth() + 1).padStart(2, "0")}`;
}

export const temporalOverlayPlugin: GraphPlugin = {
  id: "temporal-overlay",
  mount: () => {},
  unmount: () => {},
  onStateChange: () => {},
  toolbarItems: (context) => [
    {
      id: "temporal-toggle",
      label: "Temporal",
      title: "Toggle temporal context panel",
      active: context.isPanelOpen(TEMPORAL_PANEL_ID),
      order: 40,
      onClick: () => context.dispatchAction({ type: "togglePanel", panelId: TEMPORAL_PANEL_ID }),
    },
  ],
  renderOverlay: (context) => {
    const temporal = context.getTemporalState();
    if (!temporal?.currentTime) {
      return null;
    }

    const label = formatTemporalLabel(temporal.currentTime);
    return {
      id: "temporal-overlay-chip",
      layer: 1,
      order: 10,
      element: (
        <div
          style={{
            position: "absolute",
            left: 140,
            bottom: 26,
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 12px",
            borderRadius: 999,
            border: "1px solid rgba(127, 208, 255, 0.18)",
            background: "linear-gradient(135deg, rgba(6, 15, 27, 0.88), rgba(11, 22, 39, 0.76))",
            boxShadow: "0 12px 30px rgba(0, 0, 0, 0.28)",
            color: "#dce9f8",
            fontSize: 11,
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            pointerEvents: "none",
          }}
        >
          <span style={{ color: "#7fc6ff", fontWeight: 700 }}>Temporal</span>
          <span>{label}</span>
          {typeof temporal.activeNodeCount === "number" ? (
            <span style={{ color: "#8ea4be" }}>{temporal.activeNodeCount.toLocaleString()} active</span>
          ) : null}
        </div>
      ),
    };
  },
  renderPanel: (context) => {
    if (!context.isPanelOpen(TEMPORAL_PANEL_ID)) {
      return null;
    }

    const temporal = context.getTemporalState();
    return {
      id: TEMPORAL_PANEL_ID,
      title: "Temporal Context",
      placement: "bottom",
      order: 30,
      defaultOpen: false,
      preferredWidth: 320,
      preferredHeight: 220,
      content: (
        <div style={panelBodyStyle}>
          <div style={panelEyebrowStyle}>Current scrubber state</div>
          <div style={detailRowStyle}>
            <span style={detailLabelStyle}>Current</span>
            <span style={detailValueStyle}>{formatTemporalLabel(temporal?.currentTime ?? null)}</span>
          </div>
          <div style={detailRowStyle}>
            <span style={detailLabelStyle}>Bounds</span>
            <span style={detailValueStyle}>
              {(temporal?.minDate ?? "1970")} → {(temporal?.maxDate ?? "2030")}
            </span>
          </div>
          <div style={detailRowStyle}>
            <span style={detailLabelStyle}>Active nodes</span>
            <span style={detailValueStyle}>
              {typeof temporal?.activeNodeCount === "number" ? temporal.activeNodeCount.toLocaleString() : "All"}
            </span>
          </div>
        </div>
      ),
    };
  },
};

const panelBodyStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 10,
};

const panelEyebrowStyle: CSSProperties = {
  color: "#8ea4be",
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
};

const detailRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 16,
  padding: "8px 10px",
  borderRadius: 12,
  border: "1px solid rgba(255,255,255,0.06)",
  background: "rgba(255,255,255,0.025)",
};

const detailLabelStyle: CSSProperties = {
  color: "#8ea4be",
  fontSize: 12,
};

const detailValueStyle: CSSProperties = {
  color: "#f3f7fd",
  fontSize: 12,
  fontWeight: 600,
};
