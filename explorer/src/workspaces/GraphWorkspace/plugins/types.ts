import type { ReactNode } from "react";
import type Graph from "graphology";

import { graph, type EdgeAttributes, type NodeAttributes } from "../../../store/graphStore";
import type { GraphTheme } from "../graphTheme";
import type { GraphSceneRuntime } from "../scene";
import type {
  GraphAnalyticsSnapshot,
  GraphDisplayStateSnapshot,
  GraphDiagnosticsSnapshot,
  GraphEffectsState,
  GraphEffectToggle,
  GraphInteractionState,
  GraphLoadSummary,
  GraphSelectedNodeState,
  GraphTemporalState,
  GraphViewMode,
} from "../types";

export type { GraphTemporalState } from "../types";

export type GraphPluginId = string;
export type GraphPluginPanelPlacement = "side" | "bottom";

export interface GraphInspectorState {
  selectedNodeId: string | null;
  ownsSelectionDetails: boolean;
}

export type GraphPluginActionRequest =
  | { type: "fitView" }
  | { type: "focusNode"; nodeId: string }
  | { type: "selectNode"; nodeId: string }
  | { type: "setViewMode"; viewMode: GraphViewMode }
  | { type: "collapseNeighborhood" }
  | { type: "expandNeighborhood" }
  | { type: "toggleEffect"; effect: GraphEffectToggle }
  | { type: "setEffect"; effect: GraphEffectToggle; enabled: boolean }
  | { type: "togglePanel"; panelId: string }
  | { type: "openPanel"; panelId: string }
  | { type: "closePanel"; panelId: string };

export interface GraphPluginToolbarItem {
  id: string;
  label: string;
  title?: string;
  active?: boolean;
  order?: number;
  onClick: () => void;
}

export interface GraphPluginPanelDescriptor {
  id: string;
  title: string;
  placement: GraphPluginPanelPlacement;
  order?: number;
  defaultOpen?: boolean;
  preferredHeight?: number;
  preferredWidth?: number;
  content: ReactNode;
}

export interface GraphPluginOverlayDescriptor {
  id: string;
  layer?: number;
  order?: number;
  element: ReactNode;
}

export interface GraphPluginContext {
  readonly scene: GraphSceneRuntime | null;
  readonly graph: typeof graph | Graph<NodeAttributes, EdgeAttributes>;
  readonly displayGraph: typeof graph | Graph<NodeAttributes, EdgeAttributes>;
  readonly theme: GraphTheme;
  getInteractionState: () => GraphInteractionState;
  getSelectedNodeState: () => GraphSelectedNodeState | null;
  getInspectorState: () => GraphInspectorState;
  getGraphSummary: () => GraphLoadSummary | null;
  getTemporalState: () => GraphTemporalState | null;
  getEffectsState: () => GraphEffectsState;
  getDiagnosticsSnapshot: () => GraphDiagnosticsSnapshot | null;
  getAnalyticsSnapshot: () => GraphAnalyticsSnapshot | null;
  getDisplayState: () => GraphDisplayStateSnapshot;
  isPanelOpen: (panelId: string) => boolean;
  dispatchAction: (action: GraphPluginActionRequest) => void;
}

export interface GraphPlugin {
  id: GraphPluginId;
  mount: (context: GraphPluginContext) => void;
  unmount: (context: GraphPluginContext) => void;
  onStateChange: (context: GraphPluginContext, interactionState: GraphInteractionState) => void;
  renderOverlay?: (
    context: GraphPluginContext,
  ) => GraphPluginOverlayDescriptor | GraphPluginOverlayDescriptor[] | null;
  renderPanel?: (
    context: GraphPluginContext,
  ) => GraphPluginPanelDescriptor | GraphPluginPanelDescriptor[] | null;
  toolbarItems?: (context: GraphPluginContext) => GraphPluginToolbarItem[];
}

export interface GraphPluginRegistryEntry {
  plugin: GraphPlugin;
  enabled?: boolean;
}
