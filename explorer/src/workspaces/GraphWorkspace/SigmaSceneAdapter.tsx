import { forwardRef, useImperativeHandle, useRef } from "react";

import { GraphCanvas, type GraphCanvasHandle } from "./GraphCanvas";
import type { GraphSceneAdapter, GraphSceneHandle, GraphSceneProps, GraphSceneRuntime } from "./scene";

export const SigmaSceneAdapter = forwardRef<GraphSceneHandle, GraphSceneProps>(
  function SigmaSceneAdapter(
    {
      onNodeSelect,
      onEdgeSelect,
      onInteractionStateChange,
      onCameraStateChange,
      onDiagnosticsChange,
      onAnalyticsChange,
      onRuntimeChange,
      onLayoutRunningChange,
      ...sceneProps
    },
    ref,
  ) {
    const canvasRef = useRef<GraphCanvasHandle>(null);
    const runtimeRef = useRef<GraphSceneRuntime | null>(null);

    useImperativeHandle(ref, () => ({
      fitView: () => canvasRef.current?.fitView(),
      focusNode: (nodeId: string) => canvasRef.current?.focusNode(nodeId),
      zoomIn: () => canvasRef.current?.zoomIn(),
      zoomOut: () => canvasRef.current?.zoomOut(),
      getRuntime: () => runtimeRef.current,
      setLayoutRunning: onLayoutRunningChange
        ? (running: boolean) => {
            onLayoutRunningChange(running);
          }
        : undefined,
    }), [onLayoutRunningChange]);

    return (
      <GraphCanvas
        ref={canvasRef}
        onNodeClick={onNodeSelect ?? (() => {})}
        onEdgeClick={onEdgeSelect}
        onInteractionStateChange={onInteractionStateChange}
        onCameraStateChange={onCameraStateChange}
        onDiagnosticsChange={onDiagnosticsChange}
        onAnalyticsChange={onAnalyticsChange}
        onSceneRuntimeChange={(runtime) => {
          runtimeRef.current = runtime;
          onRuntimeChange?.(runtime);
        }}
        onLayoutRunningChange={onLayoutRunningChange}
        {...sceneProps}
      />
    );
  },
) as GraphSceneAdapter;
