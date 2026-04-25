export type GraphZoomTier = "overview" | "structure" | "inspection";
export type GraphNodeVisualState = "default" | "hovered" | "selected" | "neighbor" | "path" | "inactive" | "muted";
export type GraphEdgeVisualState = "default" | "backbone" | "hovered" | "selected" | "neighbor" | "path" | "inactive" | "muted";
export type GraphNodeShapeVariant = "default" | "temporal" | "inferred" | "provenance" | "selected";
export type GraphEdgeVariant = "line" | "directional" | "bidirectionalCurve" | "parallelCurve" | "pathSignal";
export type GraphArrowVisibilityPolicy = "hidden" | "contextual" | "always";
export type GraphLabelVisibilityPolicy = "none" | "priority" | "local" | "always";
export type GraphBadgeKind = "inferred" | "temporal" | "provenance";

type GraphNodeColorMode = "base" | "selected" | "hovered" | "path" | "muted";
type GraphEdgeColorMode = "overview" | "backbone" | "structure" | "inspection" | "hover" | "path" | "focus" | "muted";
const IS_DEV = Boolean((import.meta as { env?: { DEV?: boolean } }).env?.DEV);

export interface GraphTheme {
  palette: {
    semantic: string[];
    overview: {
      nodeBase: string;
      nodeCore: string;
      nodeMuted: string;
      nodeBorder: string;
      nodeTintMix: number;
      nodeCoreMix: number;
      nodeShellAlpha: number;
      nodeCoreAlpha: number;
      edgeBackbone: string;
      edgeStructure: string;
      edgeInspection: string;
    };
    accent: {
      selected: string;
      hovered: string;
      path: string;
      temporal: string;
      provenance: string;
      inferred: string;
    };
    muted: {
      fallback: string;
      nodeAlpha: number;
      edgeOverview: string;
      edgeStructure: string;
      edgeInspection: string;
      edgeFocus: string;
    };
    background: {
      canvas: string;
      shell: string;
      shellBorder: string;
      shellGlow: string;
      grid: string;
      vignette: string;
      nodeBorder: string;
    };
  };
  zoomTiers: Record<GraphZoomTier, {
    maxRatio: number;
    nodeScale: number;
    labelThreshold: number;
    labelBudget: number;
    edgePriorityThreshold: number;
    arrowPriorityThreshold: number;
    edgeSizeScale: number;
    showBadges: boolean;
    showCurves: boolean;
    showContextualArrows: boolean;
  }>;
  labels: {
    forceVisibleStates: readonly GraphNodeVisualState[];
    policies: Record<GraphLabelVisibilityPolicy, {
      minZoomTier: GraphZoomTier;
    }>;
    chip: {
      fontFamily: string;
      fontWeight: number;
      fontSize: number;
      maxFontSize: number;
      sizeScale: number;
      paddingX: number;
      paddingY: number;
      radius: number;
      offsetX: number;
      offsetY: number;
      background: string;
      borderColor: string;
      borderAlpha: number;
      textColor: string;
      shadowColor: string;
      shadowAlpha: number;
      shadowBlur: number;
    };
    hoverCard: {
      fontFamily: string;
      titleWeight: number;
      titleSize: number;
      metaWeight: number;
      metaSize: number;
      paddingX: number;
      paddingY: number;
      radius: number;
      offsetX: number;
      offsetY: number;
      metaGap: number;
      background: string;
      borderColor: string;
      borderAlpha: number;
      textColor: string;
      metaColor: string;
      shadowColor: string;
      shadowAlpha: number;
      shadowBlur: number;
    };
  };
  nodes: {
    backgroundScale: number;
    mutedAlpha: number;
    strokeHierarchy: Record<GraphZoomTier, {
      base: number;
      emphasis: number;
      muted: number;
    }>;
    states: Record<GraphNodeVisualState, {
      color: GraphNodeColorMode;
      sizeMultiplier: number;
      minSize: number;
      forceLabel: boolean;
      zIndex: number;
      borderBoost: number;
    }>;
    variants: Record<GraphNodeShapeVariant, {
      sizeMultiplier: number;
      borderBoost: number;
      haloBoost: number;
      badgeKind?: GraphBadgeKind;
      badgeVisibleFrom: GraphZoomTier;
    }>;
    selectedRing: {
      color: string;
      width: number;
      nativeSize: number;
      glowAlpha: number;
      visibleFrom: GraphZoomTier;
    };
    badges: Record<GraphBadgeKind, {
      color: string;
      label: string;
    }>;
    badge: {
      radius: number;
      offset: number;
      fontSize: number;
      textColor: string;
      background: string;
      stroke: string;
      glowAlpha: number;
    };
  };
  edges: {
    states: Record<GraphEdgeVisualState, {
      color: GraphEdgeColorMode;
      sizeMultiplier: number;
      minSize: number;
      zIndex: number;
      forceArrow: boolean;
      hide: boolean;
    }>;
    variants: Record<GraphEdgeVariant, {
      baseType: "line" | "arrow";
      arrowPolicy: GraphArrowVisibilityPolicy;
      curveStrength: number;
      sizeMultiplier: number;
      glowAlpha: number;
    }>;
  };
  overlays: {
    hoverGlowAlpha: number;
    pathGlowAlpha: number;
    glowRadiusMultiplier: number;
    minGlowRadius: number;
    pulseRadius: number;
    curveLineWidth: number;
    curveGlowWidth: number;
    badgeGlowRadius: number;
  };
  focus: {
    maxNeighbors: number;
    primaryLabels: number;
    primaryRingSlots: number;
    secondaryRingSlots: number;
    primaryRadius: number;
    secondaryRadius: number;
    overlapPadding: number;
    overlapIterations: number;
    ringAttractionStrength: number;
    selectedMinSize: number;
    primaryNeighborMinSize: number;
    secondaryNeighborMinSize: number;
    pathNodeSizeScale: number;
    primaryNodeSizeScale: number;
    secondaryNodeSizeScale: number;
    supportEdgeBudget: number;
    pathScoreBoost: number;
    weightScoreScale: number;
    degreeScoreScale: number;
    edgeWeightScoreScale: number;
    primaryEdgeBoost: number;
  };
  motion: {
    cameraMs: number;
  };
  grouped: {
    initialLayout: {
      innerRadius: number;
      ringSpacing: number;
      minNodeSpacing: number;
      nodePadding: number;
      overlapIterations: number;
      primaryLabelCount: number;
    };
    style: {
      nodeSizeScale: number;
      nodeBorderBoost: number;
      fillAlpha: number;
      shellAlpha: number;
      edgeSizeScale: number;
      edgeAlpha: number;
      glowAlpha: number;
      edgeVisibilityRatio: number;
      topIncidentEdges: number;
    };
    layout: {
      iterations: number;
      gravity: number;
      scalingRatio: number;
      edgeWeightInfluence: number;
      slowDown: number;
      settleMs: number;
    };
  };
  effects: {
    pathPulse: {
      minZoomTier: GraphZoomTier;
      maxSegments: number;
      speed: number;
      radius: number;
      glowAlpha: number;
    };
    pathFlow: {
      minZoomTier: GraphZoomTier;
      maxSegments: number;
      speed: number;
      spacing: number;
      opacity: number;
      radius: number;
    };
    lens: {
      minZoomTier: GraphZoomTier;
      radius: number;
      feather: number;
      glowAlpha: number;
      edgeAlpha: number;
      edgeLineWidth: number;
    };
    temporalEmphasis: {
      minZoomTier: GraphZoomTier;
      maxHighlights: number;
      radiusMultiplier: number;
      glowAlpha: number;
    };
    semanticRegions: {
      minZoomTier: GraphZoomTier;
      maxRegions: number;
      minVisibleSamples: number;
      fogResolutionScale: number;
      splatRadius: number;
      blurPasses: number;
      densityThreshold: number;
      contourThreshold: number;
      minMaskPixels: number;
      minOccupancyRatio: number;
      dominantMassRatio: number;
      outerContourMinMaskPixels: number;
      fogAlpha: number;
      innerContourAlpha: number;
      outerContourAlpha: number;
    };
    contours: {
      minZoomTier: GraphZoomTier;
      maxContours: number;
      baseRadius: number;
      glowAlpha: number;
    };
    legend: {
      maxGroups: number;
    };
    diagnostics: {
      enabledInDev: boolean;
    };
  };
}

export const GRAPH_THEME: GraphTheme = {
  palette: {
    semantic: [
      "#3E79F2",
      "#149287",
      "#2F9F61",
      "#555FD6",
      "#8A56D8",
      "#B65473",
      "#C9922E",
    ],
    overview: {
      nodeBase: "#0B1320",
      nodeCore: "#5A7A9E",
      nodeMuted: "#121927",
      nodeBorder: "#7A92AE",
      nodeTintMix: 0.14,
      nodeCoreMix: 0.72,
      nodeShellAlpha: 0.97,
      nodeCoreAlpha: 1,
      edgeBackbone: "rgba(100, 148, 210, 0.38)",
      edgeStructure: "rgba(88, 140, 200, 0.28)",
      edgeInspection: "rgba(110, 165, 230, 0.48)",
    },
    accent: {
      selected: "#F2D288",
      hovered: "#8FE7FF",
      path: "#D79056",
      temporal: "#49D7FF",
      provenance: "#C9A5FF",
      inferred: "#D07B4D",
    },
    muted: {
      fallback: "rgba(96, 112, 136, 0.18)",
      nodeAlpha: 0.12,
      edgeOverview: "rgba(82, 100, 124, 0.12)",
      edgeStructure: "rgba(92, 112, 138, 0.18)",
      edgeInspection: "rgba(124, 148, 176, 0.26)",
      edgeFocus: "rgba(160, 186, 218, 0.42)",
    },
    background: {
      canvas: "#07101A",
      shell: "rgba(8, 15, 26, 0.8)",
      shellBorder: "rgba(118, 162, 207, 0.14)",
      shellGlow: "rgba(48, 88, 140, 0.14)",
      grid: "rgba(92, 126, 170, 0.034)",
      vignette: "rgba(2, 5, 11, 0.84)",
      nodeBorder: "#0C1522",
    },
  },
  zoomTiers: {
    overview: {
      maxRatio: Number.POSITIVE_INFINITY,
      nodeScale: 0.72,
      labelThreshold: 0.995,
      labelBudget: 4,
      edgePriorityThreshold: 0.72,
      arrowPriorityThreshold: Number.POSITIVE_INFINITY,
      edgeSizeScale: 0.62,
      showBadges: false,
      showCurves: false,
      showContextualArrows: false,
    },
    structure: {
      maxRatio: 1.2,
      nodeScale: 0.94,
      labelThreshold: 0.93,
      labelBudget: 18,
      edgePriorityThreshold: 0.4,
      arrowPriorityThreshold: 0.75,
      edgeSizeScale: 0.92,
      showBadges: false,
      showCurves: false,
      showContextualArrows: false,
    },
    inspection: {
      maxRatio: 0.5,
      nodeScale: 1,
      labelThreshold: 0.8,
      labelBudget: 40,
      edgePriorityThreshold: 0,
      arrowPriorityThreshold: 0.45,
      edgeSizeScale: 1.18,
      showBadges: true,
      showCurves: true,
      showContextualArrows: true,
    },
  },
  labels: {
    forceVisibleStates: ["hovered", "selected", "path"],
    policies: {
      none: { minZoomTier: "inspection" },
      priority: { minZoomTier: "overview" },
      local: { minZoomTier: "structure" },
      always: { minZoomTier: "overview" },
    },
    chip: {
      fontFamily: "\"IBM Plex Sans\", Inter, system-ui, sans-serif",
      fontWeight: 500,
      fontSize: 10,
      maxFontSize: 11,
      sizeScale: 0.25,
      paddingX: 6,
      paddingY: 3,
      radius: 6,
      offsetX: 12,
      offsetY: 10,
      background: "rgba(8, 14, 24, 0.9)",
      borderColor: "rgba(154, 181, 212, 0.16)",
      borderAlpha: 0.28,
      textColor: "#EAF3FF",
      shadowColor: "rgba(0, 0, 0, 0.6)",
      shadowAlpha: 0.26,
      shadowBlur: 12,
    },
    hoverCard: {
      fontFamily: "\"IBM Plex Sans\", Inter, system-ui, sans-serif",
      titleWeight: 700,
      titleSize: 13,
      metaWeight: 500,
      metaSize: 10,
      paddingX: 10,
      paddingY: 7,
      radius: 12,
      offsetX: 16,
      offsetY: 16,
      metaGap: 5,
      background: "rgba(8, 14, 24, 0.94)",
      borderColor: "rgba(154, 181, 212, 0.18)",
      borderAlpha: 0.32,
      textColor: "#F6FBFF",
      metaColor: "rgba(184, 214, 255, 0.58)",
      shadowColor: "rgba(0, 0, 0, 0.62)",
      shadowAlpha: 0.34,
      shadowBlur: 15,
    },
  },
  nodes: {
    backgroundScale: 0.52,
    mutedAlpha: 0.16,
    strokeHierarchy: {
      overview: { base: 0.05, emphasis: 0.34, muted: 0.02 },
      structure: { base: 1.05, emphasis: 1.45, muted: 0.55 },
      inspection: { base: 1.2, emphasis: 1.7, muted: 0.6 },
    },
    states: {
      default: { color: "base", sizeMultiplier: 0.72, minSize: 0.68, forceLabel: false, zIndex: 0, borderBoost: -0.42 },
      hovered: { color: "hovered", sizeMultiplier: 1.1, minSize: 10.8, forceLabel: true, zIndex: 4, borderBoost: 0.18 },
      selected: { color: "selected", sizeMultiplier: 1.02, minSize: 9.4, forceLabel: true, zIndex: 3, borderBoost: 0.18 },
      neighbor: { color: "base", sizeMultiplier: 0.78, minSize: 4.2, forceLabel: false, zIndex: 2, borderBoost: -0.12 },
      path: { color: "path", sizeMultiplier: 0.97, minSize: 5.8, forceLabel: true, zIndex: 2, borderBoost: 0.06 },
      inactive: { color: "muted", sizeMultiplier: 0.52, minSize: 0.58, forceLabel: false, zIndex: 0, borderBoost: -0.42 },
      muted: { color: "muted", sizeMultiplier: 0.52, minSize: 0.58, forceLabel: false, zIndex: 0, borderBoost: -0.42 },
    },
    variants: {
      default: { sizeMultiplier: 1, borderBoost: 0, haloBoost: 0, badgeVisibleFrom: "inspection" },
      temporal: { sizeMultiplier: 1.02, borderBoost: 0.12, haloBoost: 0.1, badgeKind: "temporal", badgeVisibleFrom: "inspection" },
      inferred: { sizeMultiplier: 1.05, borderBoost: 0.16, haloBoost: 0.14, badgeKind: "inferred", badgeVisibleFrom: "inspection" },
      provenance: { sizeMultiplier: 1.03, borderBoost: 0.14, haloBoost: 0.12, badgeKind: "provenance", badgeVisibleFrom: "inspection" },
      selected: { sizeMultiplier: 1.06, borderBoost: 0.22, haloBoost: 0.16, badgeVisibleFrom: "overview" },
    },
    selectedRing: {
      color: "#E7C57C",
      width: 1.9,
      nativeSize: 2.2,
      glowAlpha: 0.2,
      visibleFrom: "overview",
    },
    badges: {
      inferred: { color: "#C98658", label: "I" },
      temporal: { color: "#52CDEF", label: "T" },
      provenance: { color: "#A289D0", label: "P" },
    },
    badge: {
      radius: 7,
      offset: 3,
      fontSize: 8,
      textColor: "#08111d",
      background: "rgba(8, 17, 29, 0.84)",
      stroke: "rgba(255,255,255,0.14)",
      glowAlpha: 0.24,
    },
  },
  edges: {
    states: {
      default: { color: "structure", sizeMultiplier: 0.96, minSize: 0.9, zIndex: 0, forceArrow: false, hide: false },
      backbone: { color: "backbone", sizeMultiplier: 1.0, minSize: 1.0, zIndex: 1, forceArrow: false, hide: false },
      hovered: { color: "hover", sizeMultiplier: 1.6, minSize: 2.2, zIndex: 3, forceArrow: true, hide: false },
      selected: { color: "hover", sizeMultiplier: 1.6, minSize: 2.2, zIndex: 3, forceArrow: true, hide: false },
      neighbor: { color: "focus", sizeMultiplier: 1.1, minSize: 1.2, zIndex: 1, forceArrow: false, hide: false },
      path: { color: "path", sizeMultiplier: 1.7, minSize: 2.4, zIndex: 4, forceArrow: true, hide: false },
      inactive: { color: "muted", sizeMultiplier: 0.6, minSize: 0.5, zIndex: 0, forceArrow: false, hide: false },
      muted: { color: "muted", sizeMultiplier: 0.6, minSize: 0.5, zIndex: 0, forceArrow: false, hide: false },
    },
    variants: {
      line: { baseType: "line", arrowPolicy: "hidden", curveStrength: 0, sizeMultiplier: 1, glowAlpha: 0 },
      directional: { baseType: "line", arrowPolicy: "contextual", curveStrength: 0, sizeMultiplier: 1.04, glowAlpha: 0.08 },
      bidirectionalCurve: { baseType: "line", arrowPolicy: "contextual", curveStrength: 0.18, sizeMultiplier: 1.08, glowAlpha: 0.1 },
      parallelCurve: { baseType: "line", arrowPolicy: "contextual", curveStrength: 0.24, sizeMultiplier: 1.1, glowAlpha: 0.12 },
      pathSignal: { baseType: "arrow", arrowPolicy: "always", curveStrength: 0.16, sizeMultiplier: 1.18, glowAlpha: 0.2 },
    },
  },
  overlays: {
    hoverGlowAlpha: 0.18,
    pathGlowAlpha: 0.16,
    glowRadiusMultiplier: 4.8,
    minGlowRadius: 16,
    pulseRadius: 11,
    curveLineWidth: 1.7,
    curveGlowWidth: 6,
    badgeGlowRadius: 14,
  },
  focus: {
    maxNeighbors: 16,
    primaryLabels: 6,
    primaryRingSlots: 7,
    secondaryRingSlots: 10,
    primaryRadius: 170,
    secondaryRadius: 310,
    overlapPadding: 18,
    overlapIterations: 18,
    ringAttractionStrength: 0.1,
    selectedMinSize: 24,
    primaryNeighborMinSize: 11.5,
    secondaryNeighborMinSize: 7.2,
    pathNodeSizeScale: 1.16,
    primaryNodeSizeScale: 1.08,
    secondaryNodeSizeScale: 0.86,
    supportEdgeBudget: 10,
    pathScoreBoost: 10_000,
    weightScoreScale: 100,
    degreeScoreScale: 2,
    edgeWeightScoreScale: 4,
    primaryEdgeBoost: 1.5,
  },
  motion: {
    cameraMs: 380,
  },
  grouped: {
    initialLayout: {
      innerRadius: 92,
      ringSpacing: 138,
      minNodeSpacing: 112,
      nodePadding: 28,
      overlapIterations: 18,
      primaryLabelCount: 6,
    },
    style: {
      nodeSizeScale: 0.9,
      nodeBorderBoost: 0.42,
      fillAlpha: 0.68,
      shellAlpha: 0.28,
      edgeSizeScale: 0.62,
      edgeAlpha: 0.32,
      glowAlpha: 0.14,
      edgeVisibilityRatio: 0.18,
      topIncidentEdges: 2,
    },
    layout: {
      iterations: 18,
      gravity: 0.06,
      scalingRatio: 18,
      edgeWeightInfluence: 0.08,
      slowDown: 34,
      settleMs: 1500,
    },
  },
  effects: {
    pathPulse: {
      minZoomTier: "structure",
      maxSegments: 18,
      speed: 0.22,
      radius: 11,
      glowAlpha: 0.92,
    },
    pathFlow: {
      minZoomTier: "structure",
      maxSegments: 14,
      speed: 0.36,
      spacing: 0.26,
      opacity: 0.92,
      radius: 3.8,
    },
    lens: {
      minZoomTier: "structure",
      radius: 136,
      feather: 78,
      glowAlpha: 0.18,
      edgeAlpha: 0.42,
      edgeLineWidth: 1.8,
    },
    temporalEmphasis: {
      minZoomTier: "structure",
      maxHighlights: 48,
      radiusMultiplier: 4.2,
      glowAlpha: 0.12,
    },
    semanticRegions: {
      minZoomTier: "overview",
      maxRegions: 3,
      minVisibleSamples: 14,
      fogResolutionScale: 0.22,
      splatRadius: 13,
      blurPasses: 2,
      densityThreshold: 0.16,
      contourThreshold: 0.28,
      minMaskPixels: 170,
      minOccupancyRatio: 0.0022,
      dominantMassRatio: 0.62,
      outerContourMinMaskPixels: 240,
      fogAlpha: 0.11,
      innerContourAlpha: 0.16,
      outerContourAlpha: 0.045,
    },
    contours: {
      minZoomTier: "overview",
      maxContours: 3,
      baseRadius: 88,
      glowAlpha: 0.055,
    },
    legend: {
      maxGroups: 8,
    },
    diagnostics: {
      enabledInDev: IS_DEV,
    },
  },
};

const ZOOM_TIER_ORDER: GraphZoomTier[] = ["overview", "structure", "inspection"];

export function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function clamp(min: number, value: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function withAlpha(color: string | undefined, alpha: number): string {
  if (!color) {
    return `rgba(130, 145, 165, ${alpha})`;
  }

  if (color.startsWith("#")) {
    const hex = color.slice(1);
    const normalized = hex.length === 3
      ? hex.split("").map((char) => `${char}${char}`).join("")
      : hex;

    if (normalized.length === 6) {
      const red = Number.parseInt(normalized.slice(0, 2), 16);
      const green = Number.parseInt(normalized.slice(2, 4), 16);
      const blue = Number.parseInt(normalized.slice(4, 6), 16);
      return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
    }
  }

  if (color.startsWith("rgba(")) {
    return color.replace(/rgba\(([^)]+),\s*[\d.]+\)/, `rgba($1, ${alpha})`);
  }

  if (color.startsWith("rgb(")) {
    return color.replace("rgb(", "rgba(").replace(")", `, ${alpha})`);
  }

  return `rgba(130, 145, 165, ${alpha})`;
}

export function darkenHex(hexColor: string, amount: number): string {
  if (!hexColor.startsWith("#")) {
    return hexColor;
  }

  const hex = hexColor.slice(1);
  const normalized = hex.length === 3
    ? hex.split("").map((char) => `${char}${char}`).join("")
    : hex;

  if (normalized.length !== 6) {
    return hexColor;
  }

  const clampChannel = (value: number) => clamp(0, value, 255);
  const red = clampChannel(Number.parseInt(normalized.slice(0, 2), 16) - amount);
  const green = clampChannel(Number.parseInt(normalized.slice(2, 4), 16) - amount);
  const blue = clampChannel(Number.parseInt(normalized.slice(4, 6), 16) - amount);

  return `#${[red, green, blue].map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

export function blendHex(baseColor: string, tintColor: string, amount: number): string {
  if (!baseColor.startsWith("#") || !tintColor.startsWith("#")) {
    return tintColor || baseColor;
  }

  const normalize = (value: string) => {
    const hex = value.slice(1);
    return hex.length === 3
      ? hex.split("").map((char) => `${char}${char}`).join("")
      : hex;
  };

  const base = normalize(baseColor);
  const tint = normalize(tintColor);
  if (base.length !== 6 || tint.length !== 6) {
    return tintColor || baseColor;
  }

  const mix = clamp(0, amount, 1);
  const mixChannel = (left: number, right: number) => Math.round(left + (right - left) * mix);
  const channels = [0, 2, 4].map((offset) => {
    const left = Number.parseInt(base.slice(offset, offset + 2), 16);
    const right = Number.parseInt(tint.slice(offset, offset + 2), 16);
    return mixChannel(left, right).toString(16).padStart(2, "0");
  });

  return `#${channels.join("")}`;
}

export function getZoomTier(ratio: number): GraphZoomTier {
  if (ratio <= GRAPH_THEME.zoomTiers.inspection.maxRatio) {
    return "inspection";
  }
  if (ratio <= GRAPH_THEME.zoomTiers.structure.maxRatio) {
    return "structure";
  }
  return "overview";
}

export function zoomTierAtLeast(current: GraphZoomTier, minimum: GraphZoomTier): boolean {
  return ZOOM_TIER_ORDER.indexOf(current) >= ZOOM_TIER_ORDER.indexOf(minimum);
}
