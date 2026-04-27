import type Graph from "graphology";
import Sigma from "sigma";

import { graph, type EdgeAttributes, type NodeAttributes } from "../../store/graphStore";
import { blendHex, GRAPH_THEME, withAlpha, zoomTierAtLeast } from "./graphTheme";
import type {
  GraphAnalyticsSnapshot,
  GraphEffectsState,
  GraphInteractionState,
  GraphTemporalState,
} from "./types";

type GraphRef = typeof graph | Graph<NodeAttributes, EdgeAttributes>;

export type ViewportPoint = { x: number; y: number };

export type PathSegmentOverlay = {
  sourceId: string;
  targetId: string;
  source: ViewportPoint;
  target: ViewportPoint;
  color: string;
  size: number;
};

export type VisibleNodeSample = {
  nodeId: string;
  point: ViewportPoint;
  size: number;
  attrs: NodeAttributes;
};

function isPointNearViewport(point: ViewportPoint, width: number, height: number, padding = 96) {
  return point.x >= -padding
    && point.y >= -padding
    && point.x <= width + padding
    && point.y <= height + padding;
}

function drawGlowHalo(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  color: string,
) {
  const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
  gradient.addColorStop(0, color);
  gradient.addColorStop(1, "rgba(0,0,0,0)");
  context.fillStyle = gradient;
  context.beginPath();
  context.arc(x, y, radius, 0, Math.PI * 2);
  context.fill();
}

function createScratchCanvas(width: number, height: number) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

function parseCssColor(color: string) {
  if (color.startsWith("#")) {
    const hex = color.slice(1);
    const normalized = hex.length === 3
      ? hex.split("").map((char) => `${char}${char}`).join("")
      : hex;
    if (normalized.length === 6) {
      return {
        r: Number.parseInt(normalized.slice(0, 2), 16),
        g: Number.parseInt(normalized.slice(2, 4), 16),
        b: Number.parseInt(normalized.slice(4, 6), 16),
      };
    }
  }

  const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (match) {
    return {
      r: Number.parseInt(match[1], 10),
      g: Number.parseInt(match[2], 10),
      b: Number.parseInt(match[3], 10),
    };
  }

  return { r: 130, g: 145, b: 165 };
}

function createThresholdMask(
  alphaValues: Uint8ClampedArray,
  width: number,
  height: number,
  threshold: number,
) {
  const mask = new Uint8Array(width * height);
  let count = 0;
  let sumX = 0;
  let sumY = 0;
  let sumWeight = 0;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x;
      const alpha = alphaValues[index];
      if (alpha < threshold) {
        continue;
      }

      mask[index] = 1;
      count += 1;
      sumX += x * alpha;
      sumY += y * alpha;
      sumWeight += alpha;
    }
  }

  const centroid = sumWeight > 0
    ? { x: sumX / sumWeight, y: sumY / sumWeight }
    : { x: width / 2, y: height / 2 };

  return { mask, count, centroid };
}

function blurAlphaValues(
  alphaValues: Uint8ClampedArray,
  width: number,
  height: number,
  passes: number,
) {
  if (passes <= 0) {
    return alphaValues;
  }

  let source = alphaValues;
  for (let pass = 0; pass < passes; pass += 1) {
    const next = new Uint8ClampedArray(width * height);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        let sum = 0;
        let samples = 0;
        for (let oy = -1; oy <= 1; oy += 1) {
          const sampleY = y + oy;
          if (sampleY < 0 || sampleY >= height) {
            continue;
          }
          for (let ox = -1; ox <= 1; ox += 1) {
            const sampleX = x + ox;
            if (sampleX < 0 || sampleX >= width) {
              continue;
            }
            sum += source[sampleY * width + sampleX];
            samples += 1;
          }
        }
        next[y * width + x] = Math.round(sum / Math.max(samples, 1));
      }
    }
    source = next;
  }

  return source;
}

function isolateDominantMask(
  mask: Uint8Array,
  width: number,
  height: number,
  alphaValues: Uint8ClampedArray,
) {
  const visited = new Uint8Array(mask.length);
  const queue = new Int32Array(mask.length);
  let bestPixels: number[] = [];
  let totalCount = 0;

  for (let index = 0; index < mask.length; index += 1) {
    if (!mask[index] || visited[index]) {
      continue;
    }

    let head = 0;
    let tail = 0;
    const component: number[] = [];
    visited[index] = 1;
    queue[tail++] = index;

    while (head < tail) {
      const current = queue[head++];
      component.push(current);

      const x = current % width;
      const y = Math.floor(current / width);
      const neighbors = [
        current - 1,
        current + 1,
        current - width,
        current + width,
      ];

      for (let n = 0; n < neighbors.length; n += 1) {
        const neighbor = neighbors[n];
        if (neighbor < 0 || neighbor >= mask.length || visited[neighbor] || !mask[neighbor]) {
          continue;
        }
        if ((n === 0 && x === 0) || (n === 1 && x === width - 1) || (n === 2 && y === 0) || (n === 3 && y === height - 1)) {
          continue;
        }
        visited[neighbor] = 1;
        queue[tail++] = neighbor;
      }
    }

    totalCount += component.length;
    if (component.length > bestPixels.length) {
      bestPixels = component;
    }
  }

  const dominantMask = new Uint8Array(mask.length);
  let sumX = 0;
  let sumY = 0;
  let sumWeight = 0;
  bestPixels.forEach((index) => {
    dominantMask[index] = 1;
    const alpha = alphaValues[index];
    const x = index % width;
    const y = Math.floor(index / width);
    sumX += x * alpha;
    sumY += y * alpha;
    sumWeight += alpha;
  });

  return {
    mask: dominantMask,
    count: bestPixels.length,
    centroid: sumWeight > 0
      ? { x: sumX / sumWeight, y: sumY / sumWeight }
      : { x: width / 2, y: height / 2 },
    occupancyRatio: bestPixels.length / Math.max(width * height, 1),
    dominantMassRatio: bestPixels.length / Math.max(totalCount, 1),
  };
}

function renderDensityField(
  samples: VisibleNodeSample[],
  width: number,
  height: number,
) {
  const scale = GRAPH_THEME.effects.semanticRegions.fogResolutionScale;
  const gridWidth = Math.max(72, Math.round(width * scale));
  const gridHeight = Math.max(72, Math.round(height * scale));
  const canvas = createScratchCanvas(gridWidth, gridHeight);
  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }

  context.clearRect(0, 0, gridWidth, gridHeight);
  context.globalCompositeOperation = "source-over";

  samples.forEach((sample) => {
    const x = sample.point.x * scale;
    const y = sample.point.y * scale;
    const radius = Math.max(
      2.5,
      (GRAPH_THEME.effects.semanticRegions.splatRadius + sample.size * 0.9) * scale,
    );
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, "rgba(255,255,255,0.05)");
    gradient.addColorStop(0.58, "rgba(255,255,255,0.02)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient;
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
  });

  const imageData = context.getImageData(0, 0, gridWidth, gridHeight);
  const alphaValues = new Uint8ClampedArray(gridWidth * gridHeight);
  let maxAlpha = 0;
  for (let index = 0; index < alphaValues.length; index += 1) {
    const alpha = imageData.data[index * 4 + 3];
    alphaValues[index] = alpha;
    if (alpha > maxAlpha) {
      maxAlpha = alpha;
    }
  }

  if (maxAlpha <= 0) {
    return null;
  }

  const blurredAlphaValues = blurAlphaValues(
    alphaValues,
    gridWidth,
    gridHeight,
    GRAPH_THEME.effects.semanticRegions.blurPasses,
  );
  const blurredMaxAlpha = blurredAlphaValues.reduce((value, alpha) => Math.max(value, alpha), 0);
  if (blurredMaxAlpha <= 0) {
    return null;
  }

  return { canvas, gridWidth, gridHeight, alphaValues: blurredAlphaValues, maxAlpha: blurredMaxAlpha, scale };
}

function drawDensityFog(
  context: CanvasRenderingContext2D,
  densityField: ReturnType<typeof renderDensityField>,
  color: string,
  alpha: number,
) {
  if (!densityField) {
    return;
  }

  const { gridWidth, gridHeight, alphaValues } = densityField;
  const fogCanvas = createScratchCanvas(gridWidth, gridHeight);
  const fogContext = fogCanvas.getContext("2d");
  if (!fogContext) {
    return;
  }

  const imageData = fogContext.createImageData(gridWidth, gridHeight);
  const rgb = parseCssColor(color);
  for (let index = 0; index < alphaValues.length; index += 1) {
    const sourceAlpha = alphaValues[index] / 255;
    if (sourceAlpha <= 0) {
      continue;
    }

    const pixelIndex = index * 4;
    imageData.data[pixelIndex] = rgb.r;
    imageData.data[pixelIndex + 1] = rgb.g;
    imageData.data[pixelIndex + 2] = rgb.b;
    imageData.data[pixelIndex + 3] = Math.round(255 * Math.pow(sourceAlpha, 1.7) * alpha);
  }

  fogContext.putImageData(imageData, 0, 0);
  context.save();
  context.imageSmoothingEnabled = true;
  context.globalCompositeOperation = "lighter";
  context.drawImage(fogCanvas, 0, 0, context.canvas.width, context.canvas.height);
  context.restore();
}

function drawMaskContour(
  context: CanvasRenderingContext2D,
  mask: Uint8Array,
  gridWidth: number,
  gridHeight: number,
  color: string,
  alpha: number,
) {
  const contourCanvas = createScratchCanvas(gridWidth, gridHeight);
  const contourContext = contourCanvas.getContext("2d");
  if (!contourContext) {
    return;
  }

  const imageData = contourContext.createImageData(gridWidth, gridHeight);
  const rgb = parseCssColor(color);

  for (let y = 1; y < gridHeight - 1; y += 1) {
    for (let x = 1; x < gridWidth - 1; x += 1) {
      const index = y * gridWidth + x;
      if (!mask[index]) {
        continue;
      }

      const isEdge = !mask[index - 1]
        || !mask[index + 1]
        || !mask[index - gridWidth]
        || !mask[index + gridWidth];
      if (!isEdge) {
        continue;
      }

      const pixelIndex = index * 4;
      imageData.data[pixelIndex] = rgb.r;
      imageData.data[pixelIndex + 1] = rgb.g;
      imageData.data[pixelIndex + 2] = rgb.b;
      imageData.data[pixelIndex + 3] = Math.round(255 * alpha);
    }
  }

  contourContext.putImageData(imageData, 0, 0);
  context.save();
  context.imageSmoothingEnabled = true;
  context.drawImage(contourCanvas, 0, 0, context.canvas.width, context.canvas.height);
  context.restore();
}

function buildRegionRenderColors(color: string) {
  return {
    fogColor: blendHex("#0E1927", color, 0.46),
    innerContourColor: blendHex("#1C2C3F", color, 0.78),
    outerContourColor: blendHex("#132131", color, 0.6),
    labelBorderColor: blendHex("#2B3F57", color, 0.78),
  };
}

export function collectVisibleNodeSamples(
  sigma: Sigma,
  graphRef: GraphRef,
  viewportWidth: number,
  viewportHeight: number,
): VisibleNodeSample[] {
  const samples: VisibleNodeSample[] = [];

  graphRef.forEachNode((nodeId, attrs) => {
    const displayData = sigma.getNodeDisplayData(nodeId);
    if (!displayData) {
      return;
    }

    const point = sigma.graphToViewport({ x: displayData.x, y: displayData.y });
    if (!isPointNearViewport(point, viewportWidth, viewportHeight, 84)) {
      return;
    }

    samples.push({
      nodeId,
      point,
      size: displayData.size,
      attrs: attrs as NodeAttributes,
    });
  });

  return samples;
}

function drawRegionLabel(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  color: string,
) {
  const label = text.length > 22 ? `${text.slice(0, 21)}…` : text;
  context.save();
  context.font = `600 11px "IBM Plex Sans", Inter, system-ui, sans-serif`;
  context.textBaseline = "middle";
  const width = context.measureText(label).width + 14;
  const height = 22;
  const left = x - width / 2;
  const top = y - height / 2;

  context.fillStyle = "rgba(8, 14, 24, 0.84)";
  context.strokeStyle = withAlpha(color, 0.24);
  context.lineWidth = 1;
  context.beginPath();
  context.roundRect(left, top, width, height, 999);
  context.fill();
  context.stroke();

  context.fillStyle = "rgba(235, 244, 255, 0.88)";
  context.fillText(label, left + 7, y);
  context.restore();
}

export function drawSemanticRegionsLayer(
  context: CanvasRenderingContext2D,
  analytics: GraphAnalyticsSnapshot | null,
  visibleNodes: VisibleNodeSample[],
  interactionState: GraphInteractionState,
  effectsState: GraphEffectsState,
) {
  if (!effectsState.semanticRegionsEnabled || !analytics?.semanticRegions.ready) {
    return;
  }

  if (!zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.semanticRegions.minZoomTier)) {
    return;
  }

  const visibleByGroup = new Map<string, VisibleNodeSample[]>();
  visibleNodes.forEach((sample) => {
    const group = String(sample.attrs.semanticGroup || sample.attrs.nodeType || "entity");
    const entry = visibleByGroup.get(group);
    if (entry) {
      entry.push(sample);
    } else {
      visibleByGroup.set(group, [sample]);
    }
  });

  const summaries = analytics.semanticRegions.summaries
    .slice(0, GRAPH_THEME.effects.semanticRegions.maxRegions);
  const maxProminence = summaries.reduce((value, summary) => Math.max(value, summary.prominence), 1);
  const semanticConfig = GRAPH_THEME.effects.semanticRegions;

  summaries.forEach((summary) => {
    const samples = visibleByGroup.get(summary.semanticGroup);
    if (!samples || samples.length < semanticConfig.minVisibleSamples) {
      return;
    }

    const densityField = renderDensityField(samples, context.canvas.width, context.canvas.height);
    if (!densityField) {
      return;
    }

    const prominenceRatio = 0.52 + (summary.prominence / maxProminence) * 0.48;
    const densityThreshold = Math.max(18, densityField.maxAlpha * semanticConfig.densityThreshold);
    const contourThreshold = Math.max(28, densityField.maxAlpha * semanticConfig.contourThreshold);
    const outerContourThreshold = Math.max(18, contourThreshold * 0.72);

    const densityMask = createThresholdMask(
      densityField.alphaValues,
      densityField.gridWidth,
      densityField.gridHeight,
      densityThreshold,
    );
    const dominantDensityMask = isolateDominantMask(
      densityMask.mask,
      densityField.gridWidth,
      densityField.gridHeight,
      densityField.alphaValues,
    );
    if (
      dominantDensityMask.count < semanticConfig.minMaskPixels
      || dominantDensityMask.occupancyRatio < semanticConfig.minOccupancyRatio
      || dominantDensityMask.dominantMassRatio < semanticConfig.dominantMassRatio
    ) {
      return;
    }

    const contourMask = createThresholdMask(
      densityField.alphaValues,
      densityField.gridWidth,
      densityField.gridHeight,
      contourThreshold,
    );
    const outerContourMask = createThresholdMask(
      densityField.alphaValues,
      densityField.gridWidth,
      densityField.gridHeight,
      outerContourThreshold,
    );
    const dominantContourMask = isolateDominantMask(
      contourMask.mask,
      densityField.gridWidth,
      densityField.gridHeight,
      densityField.alphaValues,
    );
    const dominantOuterContourMask = isolateDominantMask(
      outerContourMask.mask,
      densityField.gridWidth,
      densityField.gridHeight,
      densityField.alphaValues,
    );

    const colors = buildRegionRenderColors(summary.color);
    drawDensityFog(
      context,
      densityField,
      colors.fogColor,
      semanticConfig.fogAlpha * prominenceRatio,
    );
    if (
      dominantOuterContourMask.count >= semanticConfig.outerContourMinMaskPixels
      && dominantOuterContourMask.dominantMassRatio >= semanticConfig.dominantMassRatio
    ) {
      drawMaskContour(
        context,
        dominantOuterContourMask.mask,
        densityField.gridWidth,
        densityField.gridHeight,
        colors.outerContourColor,
        semanticConfig.outerContourAlpha * prominenceRatio,
      );
    }
    drawMaskContour(
      context,
      dominantContourMask.mask,
      densityField.gridWidth,
      densityField.gridHeight,
      colors.innerContourColor,
      semanticConfig.innerContourAlpha * prominenceRatio,
    );

    if (summary.visibleNodeCount >= 18) {
      const labelX = dominantDensityMask.centroid.x / densityField.scale;
      const labelY = dominantDensityMask.centroid.y / densityField.scale - 18;
      drawRegionLabel(
        context,
        labelX,
        labelY,
        summary.semanticGroup,
        colors.labelBorderColor,
      );
    }
  });
}

export function drawContourLayer(
  context: CanvasRenderingContext2D,
  analytics: GraphAnalyticsSnapshot | null,
  visibleNodes: VisibleNodeSample[],
  interactionState: GraphInteractionState,
  effectsState: GraphEffectsState,
) {
  if (!effectsState.contoursEnabled || !analytics?.centrality.ready) {
    return;
  }

  if (!zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.contours.minZoomTier)) {
    return;
  }

  const visibleById = new Map(visibleNodes.map((sample) => [sample.nodeId, sample] as const));

  analytics.centrality.topNodes.slice(0, GRAPH_THEME.effects.contours.maxContours).forEach((node) => {
    const sample = visibleById.get(node.id);
    if (!sample) {
      return;
    }

    drawGlowHalo(
      context,
      sample.point.x,
      sample.point.y,
      GRAPH_THEME.effects.contours.baseRadius + sample.size * 3.2,
      withAlpha(node.color, GRAPH_THEME.effects.contours.glowAlpha),
    );
  });
}

function isTemporalNodeActive(attrs: NodeAttributes, currentTime: Date | null) {
  if (!currentTime || (!attrs.valid_from && !attrs.valid_until)) {
    return false;
  }

  const time = currentTime.getTime();
  const from = attrs.valid_from ? new Date(attrs.valid_from).getTime() : Number.NEGATIVE_INFINITY;
  const until = attrs.valid_until ? new Date(attrs.valid_until).getTime() : Number.POSITIVE_INFINITY;
  return time >= from && time <= until;
}

export function drawTemporalEmphasisLayer(
  context: CanvasRenderingContext2D,
  visibleNodes: VisibleNodeSample[],
  temporalState: GraphTemporalState | null | undefined,
  interactionState: GraphInteractionState,
  effectsState: GraphEffectsState,
) {
  if (!effectsState.temporalEmphasisEnabled || !temporalState?.currentTime) {
    return;
  }

  if (!zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.temporalEmphasis.minZoomTier)) {
    return;
  }

  visibleNodes
    .filter((sample) => isTemporalNodeActive(sample.attrs, temporalState.currentTime))
    .slice(0, GRAPH_THEME.effects.temporalEmphasis.maxHighlights)
    .forEach((sample) => {
      drawGlowHalo(
        context,
        sample.point.x,
        sample.point.y,
        Math.max(sample.size * GRAPH_THEME.effects.temporalEmphasis.radiusMultiplier, 14),
        withAlpha(GRAPH_THEME.palette.accent.temporal, GRAPH_THEME.effects.temporalEmphasis.glowAlpha),
      );
    });
}

export function drawLensLayer(
  context: CanvasRenderingContext2D,
  sigma: Sigma,
  primaryNodeId: string,
  focusIds: Set<string>,
) {
  const primaryData = sigma.getNodeDisplayData(primaryNodeId);
  if (!primaryData) {
    return;
  }

  const center = sigma.graphToViewport({ x: primaryData.x, y: primaryData.y });
  drawGlowHalo(
    context,
    center.x,
    center.y,
    GRAPH_THEME.effects.lens.radius,
    withAlpha(GRAPH_THEME.palette.accent.hovered, GRAPH_THEME.effects.lens.glowAlpha),
  );

  focusIds.forEach((neighborId) => {
    if (neighborId === primaryNodeId || !graph.hasNode(neighborId)) {
      return;
    }

    if (
      !graph.hasDirectedEdge(primaryNodeId, neighborId)
      && !graph.hasDirectedEdge(neighborId, primaryNodeId)
    ) {
      return;
    }

    const neighborData = sigma.getNodeDisplayData(neighborId);
    if (!neighborData) {
      return;
    }

    const neighborPoint = sigma.graphToViewport({ x: neighborData.x, y: neighborData.y });
    context.strokeStyle = withAlpha(GRAPH_THEME.palette.accent.hovered, GRAPH_THEME.effects.lens.edgeAlpha * 0.38);
    context.lineWidth = GRAPH_THEME.effects.lens.edgeLineWidth + 3.2;
    context.lineCap = "round";
    context.beginPath();
    context.moveTo(center.x, center.y);
    context.lineTo(neighborPoint.x, neighborPoint.y);
    context.stroke();

    context.strokeStyle = withAlpha(GRAPH_THEME.palette.accent.hovered, GRAPH_THEME.effects.lens.edgeAlpha);
    context.lineWidth = GRAPH_THEME.effects.lens.edgeLineWidth;
    context.beginPath();
    context.moveTo(center.x, center.y);
    context.lineTo(neighborPoint.x, neighborPoint.y);
    context.stroke();
  });
}

export function drawPathEffectsLayer(
  context: CanvasRenderingContext2D,
  segments: PathSegmentOverlay[],
  effectsState: GraphEffectsState,
  effectAvailability: {
    pathPulse: { available: boolean };
    pathFlow: { available: boolean };
  },
  now: number,
) {
  if (effectsState.pathFlowEnabled && effectAvailability.pathFlow.available) {
    segments.forEach((segment, index) => {
      const t = ((now * GRAPH_THEME.effects.pathFlow.speed) + index * GRAPH_THEME.effects.pathFlow.spacing) % 1;
      const headX = segment.source.x + (segment.target.x - segment.source.x) * t;
      const headY = segment.source.y + (segment.target.y - segment.source.y) * t;
      const tailT = Math.max(0, t - 0.08);
      const tailX = segment.source.x + (segment.target.x - segment.source.x) * tailT;
      const tailY = segment.source.y + (segment.target.y - segment.source.y) * tailT;

      context.strokeStyle = withAlpha(segment.color, 0.28);
      context.lineWidth = Math.max(segment.size + 3.6, 4.6);
      context.lineCap = "round";
      context.beginPath();
      context.moveTo(tailX, tailY);
      context.lineTo(headX, headY);
      context.stroke();

      context.strokeStyle = withAlpha(GRAPH_THEME.palette.accent.selected, GRAPH_THEME.effects.pathFlow.opacity);
      context.lineWidth = Math.max(segment.size + 1.3, 2.4);
      context.beginPath();
      context.moveTo(tailX, tailY);
      context.lineTo(headX, headY);
      context.stroke();
    });
  }

  if (effectsState.pathPulseEnabled && effectAvailability.pathPulse.available) {
    segments.forEach((segment, index) => {
      const t = ((now * GRAPH_THEME.effects.pathPulse.speed) + index * 0.17) % 1;
      const x = segment.source.x + (segment.target.x - segment.source.x) * t;
      const y = segment.source.y + (segment.target.y - segment.source.y) * t;
      const glow = context.createRadialGradient(x, y, 0, x, y, GRAPH_THEME.effects.pathPulse.radius);
      glow.addColorStop(0, withAlpha(GRAPH_THEME.palette.accent.path, GRAPH_THEME.effects.pathPulse.glowAlpha));
      glow.addColorStop(1, "rgba(0,0,0,0)");
      context.fillStyle = glow;
      context.beginPath();
      context.arc(x, y, GRAPH_THEME.effects.pathPulse.radius, 0, Math.PI * 2);
      context.fill();
    });
  }
}
