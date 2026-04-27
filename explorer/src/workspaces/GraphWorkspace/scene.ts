import type { ForwardRefExoticComponent, ReactNode, RefAttributes } from "react";
import type Graph from "graphology";

import { graph, type EdgeAttributes, type NodeAttributes } from "../../store/graphStore";
import type {
  GraphAnalyticsSnapshot,
  GraphCameraState,
  GraphDisplayMeta,
  GraphDisplayStateSnapshot,
  GraphEffectsState,
  GraphInteractionState,
  GraphLayoutSource,
  GraphLayoutStatus,
  GraphRuntimeDiagnosticsSnapshot,
  GraphTemporalState,
  GraphViewMode,
} from "./types";

export type GraphSceneGraph = typeof graph | Graph<NodeAttributes, EdgeAttributes>;
export type GraphSceneRenderer = "sigma";

export interface GraphSceneRuntime {
  renderer: GraphSceneRenderer;
  scene: unknown;
  graph: GraphSceneGraph;
  displayGraph: GraphSceneGraph;
  graphVersion: number;
  layoutMode?: GraphDisplayMeta["layoutMode"];
  requestRender: () => void;
  getCameraState: () => GraphCameraState | null;
}

export interface GraphSceneEventMap {
  onNodeSelect?: (nodeId: string) => void;
  onEdgeSelect?: (edgeId: string) => void;
  onInteractionStateChange?: (interactionState: GraphInteractionState) => void;
  onCameraStateChange?: (cameraState: GraphCameraState) => void;
  onDiagnosticsChange?: (diagnostics: GraphRuntimeDiagnosticsSnapshot) => void;
  onAnalyticsChange?: (analytics: GraphAnalyticsSnapshot | null) => void;
  onRuntimeChange?: (runtime: GraphSceneRuntime | null) => void;
}

export interface GraphSceneProps extends GraphSceneEventMap {
  graphVersion: number;
  graphReady: boolean;
  displayGraph: GraphSceneGraph;
  displayMeta: GraphDisplayMeta;
  displayState?: GraphDisplayStateSnapshot;
  selectedNodeId: string;
  focusedNodeId: string;
  selectedEdgeId: string;
  activePath?: string[];
  activePathEdgeIds?: string[];
  effectsState: GraphEffectsState;
  temporalState?: GraphTemporalState | null;
  isLayoutRunning: boolean;
  onLayoutRunningChange?: (running: boolean) => void;
  layoutSource?: GraphLayoutSource;
  onLayoutStatusChange?: (status: GraphLayoutStatus) => void;
  viewMode: GraphViewMode;
  className?: string;
  showFitViewButton?: boolean;
  pluginOverlays?: ReactNode[];
}

export interface GraphSceneHandle {
  fitView: () => void;
  focusNode: (nodeId: string) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  getRuntime: () => GraphSceneRuntime | null;
  setLayoutRunning?: (running: boolean) => void;
}

export type GraphSceneAdapter = ForwardRefExoticComponent<
  GraphSceneProps & RefAttributes<GraphSceneHandle>
>;
