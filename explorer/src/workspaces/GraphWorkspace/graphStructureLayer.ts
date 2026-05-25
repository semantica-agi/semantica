import type Graph from "graphology";
import type Sigma from "sigma";

import type { EdgeAttributes, NodeAttributes } from "../../store/graphStore";
import { GRAPH_THEME, withAlpha } from "./graphTheme";
import type {
  GraphFullEdgeClass,
  GraphFullEdgeClassDiagnostics,
  GraphInteractionState,
  GraphStructureLayerDiagnostics,
  GraphStructureLayerDisabledReason,
  GraphViewMode,
} from "./types";

type GraphRef = Graph;

type StructureLayerMode = typeof GRAPH_THEME.edges.fullGraphStructureLayer.mode;

export type GraphStructureCurve = {
  edgeId: string;
  sourceId: string;
  targetId: string;
  source: { x: number; y: number };
  target: { x: number; y: number };
  edgeClass: Extract<GraphFullEdgeClass, "backbone" | "bridge">;
  priority: number;
  curvature: number;
};

export type GraphStructureCurveCache = {
  cacheKey: string;
  curves: GraphStructureCurve[];
  bridgeCurveCount: number;
  backboneCurveCount: number;
};

export type GraphStructureLayerGateInput = {
  mode: StructureLayerMode;
  viewMode: GraphViewMode;
  isLayoutRunning: boolean;
  edgeDiagnostics?: GraphFullEdgeClassDiagnostics;
  minimumLiteralEdges: number;
};

export type GraphStructureLayerGate = {
  enabled: boolean;
  disabledReason: GraphStructureLayerDisabledReason | null;
};

export function evaluateGraphStructureLayerGate({
  mode,
  viewMode,
  isLayoutRunning,
  edgeDiagnostics,
  minimumLiteralEdges,
}: GraphStructureLayerGateInput): GraphStructureLayerGate {
  if (mode === "off") {
    return { enabled: false, disabledReason: "disabled" };
  }

  if (viewMode !== "full") {
    return { enabled: false, disabledReason: "non-full-mode" };
  }

  if (isLayoutRunning) {
    return { enabled: false, disabledReason: "layout-running" };
  }

  if (mode === "auto") {
    const literalEdges = (edgeDiagnostics?.counts.backbone ?? 0) + (edgeDiagnostics?.counts.bridge ?? 0);
    if (literalEdges >= minimumLiteralEdges) {
      return { enabled: false, disabledReason: "enough-literal-edges" };
    }
  }

  return { enabled: true, disabledReason: null };
}

function isFinitePoint(attrs: NodeAttributes) {
  return Number.isFinite(Number(attrs.x)) && Number.isFinite(Number(attrs.y));
}

function getEdgePriority(attrs: EdgeAttributes) {
  return Math.max(0, Math.min(1, Number(attrs.visualPriority ?? attrs.weight ?? 0)));
}

function getCurveSortRank(edgeClass: GraphFullEdgeClass, priority: number) {
  return (edgeClass === "bridge" ? 2 : 1) + priority;
}

function getDeterministicCurveSign(sourceId: string, targetId: string, edgeId: string) {
  const seed = `${sourceId}|${targetId}|${edgeId}`;
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) | 0;
  }
  return hash % 2 === 0 ? 1 : -1;
}

export function createGraphStructureCacheKey({
  graphVersion,
  zoomTier,
  layoutSettledEpoch,
  overviewBackboneEdgeIds,
}: {
  graphVersion: number;
  zoomTier: GraphInteractionState["zoomTier"];
  layoutSettledEpoch: number;
  overviewBackboneEdgeIds: Set<string>;
}) {
  return [
    graphVersion,
    zoomTier,
    layoutSettledEpoch,
    Array.from(overviewBackboneEdgeIds).sort().join(","),
  ].join("|");
}

export function buildGraphStructureCurveCache({
  graphRef,
  cacheKey,
  classifyEdge,
  maxCurves,
  curveStrength,
}: {
  graphRef: GraphRef;
  cacheKey: string;
  classifyEdge: (edgeId: string) => GraphFullEdgeClass;
  maxCurves: number;
  curveStrength: number;
}): GraphStructureCurveCache {
  const candidates: Array<GraphStructureCurve & { rank: number }> = [];

  graphRef.forEachEdge((edgeId, attrs, source, target) => {
    const stableEdgeId = String(edgeId);
    const edgeClass = classifyEdge(stableEdgeId);
    if (edgeClass !== "bridge" && edgeClass !== "backbone") {
      return;
    }

    const sourceId = String(source);
    const targetId = String(target);
    if (!graphRef.hasNode(sourceId) || !graphRef.hasNode(targetId)) {
      return;
    }

    const sourceAttrs = graphRef.getNodeAttributes(sourceId) as NodeAttributes;
    const targetAttrs = graphRef.getNodeAttributes(targetId) as NodeAttributes;
    if (!isFinitePoint(sourceAttrs) || !isFinitePoint(targetAttrs)) {
      return;
    }

    const priority = getEdgePriority(attrs as EdgeAttributes);
    candidates.push({
      edgeId: stableEdgeId,
      sourceId,
      targetId,
      source: { x: Number(sourceAttrs.x), y: Number(sourceAttrs.y) },
      target: { x: Number(targetAttrs.x), y: Number(targetAttrs.y) },
      edgeClass,
      priority,
      curvature: getDeterministicCurveSign(sourceId, targetId, stableEdgeId) * curveStrength,
      rank: getCurveSortRank(edgeClass, priority),
    });
  });

  candidates.sort((left, right) => {
    if (right.rank !== left.rank) {
      return right.rank - left.rank;
    }
    return left.edgeId.localeCompare(right.edgeId);
  });

  const curves = candidates.slice(0, maxCurves).map(({ rank: _rank, ...curve }) => curve);
  return {
    cacheKey,
    curves,
    bridgeCurveCount: curves.filter((curve) => curve.edgeClass === "bridge").length,
    backboneCurveCount: curves.filter((curve) => curve.edgeClass === "backbone").length,
  };
}

export function getGraphStructureLayerDiagnostics({
  gate,
  cache,
  minimumCurves,
  canvasAvailable,
  lastDrawAt,
}: {
  gate: GraphStructureLayerGate;
  cache: GraphStructureCurveCache | null;
  minimumCurves: number;
  canvasAvailable: boolean;
  lastDrawAt: number | null;
}): GraphStructureLayerDiagnostics {
  if (!gate.enabled) {
    return {
      enabled: false,
      disabledReason: gate.disabledReason,
      curveCount: 0,
      bridgeCurveCount: 0,
      backboneCurveCount: 0,
      cacheKey: cache?.cacheKey ?? "",
      lastDrawAt,
    };
  }

  if (!canvasAvailable) {
    return {
      enabled: false,
      disabledReason: "invalid-layer",
      curveCount: 0,
      bridgeCurveCount: 0,
      backboneCurveCount: 0,
      cacheKey: cache?.cacheKey ?? "",
      lastDrawAt,
    };
  }

  if (!cache || cache.curves.length === 0) {
    return {
      enabled: false,
      disabledReason: "no-eligible-edges",
      curveCount: 0,
      bridgeCurveCount: 0,
      backboneCurveCount: 0,
      cacheKey: cache?.cacheKey ?? "",
      lastDrawAt,
    };
  }

  if (cache.curves.length < minimumCurves) {
    return {
      enabled: false,
      disabledReason: "cache-empty",
      curveCount: cache.curves.length,
      bridgeCurveCount: cache.bridgeCurveCount,
      backboneCurveCount: cache.backboneCurveCount,
      cacheKey: cache.cacheKey,
      lastDrawAt,
    };
  }

  return {
    enabled: true,
    disabledReason: null,
    curveCount: cache.curves.length,
    bridgeCurveCount: cache.bridgeCurveCount,
    backboneCurveCount: cache.backboneCurveCount,
    cacheKey: cache.cacheKey,
    lastDrawAt,
  };
}

export function clearGraphStructureLayer(canvas: HTMLCanvasElement | null) {
  if (!canvas) {
    return;
  }
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.clearRect(0, 0, canvas.width, canvas.height);
}

export function drawGraphStructureLayer({
  sigma,
  canvas,
  cache,
}: {
  sigma: Sigma;
  canvas: HTMLCanvasElement;
  cache: GraphStructureCurveCache;
}) {
  const context = canvas.getContext("2d");
  if (!context) {
    return false;
  }

  const { width, height } = sigma.getDimensions();
  const pixelRatio = window.devicePixelRatio || 1;
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.clearRect(0, 0, width, height);
  context.lineCap = "round";
  context.lineJoin = "round";

  let drawn = 0;
  for (const curve of cache.curves) {
    const sourceData = sigma.getNodeDisplayData(curve.sourceId);
    const targetData = sigma.getNodeDisplayData(curve.targetId);
    if (!sourceData || !targetData || sourceData.hidden || targetData.hidden) {
      continue;
    }

    const sourcePoint = sigma.graphToViewport(curve.source);
    const targetPoint = sigma.graphToViewport(curve.target);
    if (
      !Number.isFinite(sourcePoint.x)
      || !Number.isFinite(sourcePoint.y)
      || !Number.isFinite(targetPoint.x)
      || !Number.isFinite(targetPoint.y)
    ) {
      continue;
    }

    const dx = targetPoint.x - sourcePoint.x;
    const dy = targetPoint.y - sourcePoint.y;
    const distance = Math.hypot(dx, dy);
    if (distance <= 0) {
      continue;
    }

    const nx = -dy / distance;
    const ny = dx / distance;
    const offset = distance * curve.curvature;
    const controlX = (sourcePoint.x + targetPoint.x) / 2 + nx * offset;
    const controlY = (sourcePoint.y + targetPoint.y) / 2 + ny * offset;
    const layerTheme = GRAPH_THEME.edges.fullGraphStructureLayer;

    context.beginPath();
    context.strokeStyle = curve.edgeClass === "bridge"
      ? withAlpha(GRAPH_THEME.palette.muted.edgeFocus, layerTheme.bridgeAlpha)
      : withAlpha(GRAPH_THEME.palette.muted.edgeStructure, layerTheme.backboneAlpha);
    context.lineWidth = curve.edgeClass === "bridge"
      ? layerTheme.bridgeLineWidth
      : layerTheme.backboneLineWidth;
    context.moveTo(sourcePoint.x, sourcePoint.y);
    context.quadraticCurveTo(controlX, controlY, targetPoint.x, targetPoint.y);
    context.stroke();
    drawn += 1;
  }

  return drawn > 0;
}
