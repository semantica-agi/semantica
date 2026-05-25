export const GRAPH_THEME = {
  background: {
    canvas: "#050816",
    shell: "#0A1021",
    panel: "#10182C",
    grid: "rgba(93, 124, 168, 0.08)",
    vignette: "rgba(2, 4, 10, 0.88)",
  },
  nodes: {
    palette: [
      "#3CE7FF",
      "#23D7C8",
      "#5DA9FF",
      "#9B6BFF",
      "#FF4FD8",
      "#FF9A3C",
      "#B9FF3B",
    ],
    selected: "#FFC857",
    selectedGlow: "rgba(255, 200, 87, 0.36)",
    hoverGlow: "rgba(60, 231, 255, 0.32)",
    border: "#07111C",
    subduedAlpha: 0.1,
  },
  edges: {
    baseColor: "rgba(126, 162, 214, 0.08)",
    subduedColor: "rgba(126, 162, 214, 0.03)",
    hoverColor: "rgba(94, 198, 255, 0.9)",
    pathColor: "rgba(255, 192, 92, 0.95)",
    focusColor: "rgba(175, 191, 255, 0.26)",
  },
  motion: {
    hoverMs: 160,
    cameraMs: 480,
  },
  thresholds: {
    interactiveLayoutMaxNodes: 8000,
    stagedLayoutMaxNodes: 25000,
    focusNeighborCap: 18,
    focusPrimaryLabels: 8,
    particleEdgeCap: 32,
  },
} as const;

export const FORCE_ATLAS_SETTINGS = {
  getEdgeWeight: "weight",
  settings: {
    barnesHutOptimize: true,
    barnesHutTheta: 0.6,
    linLogMode: true,
    outboundAttractionDistribution: true,
    strongGravityMode: false,
    gravity: 0.14,
    scalingRatio: 4.8,
    slowDown: 6,
    edgeWeightInfluence: 1,
    adjustSizes: true,
  },
} as const;

export function clamp(min: number, value: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
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
