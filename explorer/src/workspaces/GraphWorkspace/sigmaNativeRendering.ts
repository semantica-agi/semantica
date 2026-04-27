import EdgeCurveProgram, { EdgeCurvedArrowProgram } from "@sigma/edge-curve";
import { NodeProgram, type ProgramInfo } from "sigma/rendering";
import { DEFAULT_EDGE_PROGRAM_CLASSES, DEFAULT_NODE_PROGRAM_CLASSES } from "sigma/settings";
import type { NodeDisplayData, RenderParams } from "sigma/types";
import { floatColor } from "sigma/utils";
import type { NodeHoverDrawingFunction, NodeLabelDrawingFunction } from "sigma/rendering";

import { GRAPH_THEME, type GraphEntityShapeVariant, withAlpha } from "./graphTheme";

type SemanticaNodeDrawData = {
  x: number;
  y: number;
  size: number;
  label: string;
  color: string;
  shellColor?: string;
  coreScale?: number;
  borderColor?: string;
  borderSize?: number;
  ringColor?: string;
  ringSize?: number;
  entityShape?: GraphEntityShapeVariant;
  entityShapeKind?: number;
  entityAspectRatio?: number;
  nodeType?: string;
};

const ENTITY_TOKEN_UNIFORMS = ["u_sizeRatio", "u_correctionRatio", "u_matrix"] as const;

const ENTITY_TOKEN_FRAGMENT_SHADER = /* glsl */ `
precision highp float;

varying vec4 v_bodyColor;
varying vec4 v_glyphColor;
varying vec4 v_outlineColor;
varying vec4 v_color;
varying vec2 v_diffVector;
varying float v_radius;
varying float v_outlineSize;
varying float v_glyphScale;
varying float v_shapeKind;
varying float v_aspectRatio;

uniform float u_correctionRatio;

const float bias = 255.0 / 254.0;
const vec4 transparent = vec4(0.0, 0.0, 0.0, 0.0);

float hexMetric(vec2 point) {
  vec2 q = abs(point);
  return max(q.y, q.x * 0.8660254 + q.y * 0.5);
}

vec2 rotate45(vec2 point) {
  const float invSqrt2 = 0.70710678;
  return vec2(
    (point.x - point.y) * invSqrt2,
    (point.x + point.y) * invSqrt2
  );
}

float roundedBoxDistance(vec2 point, vec2 halfSize, float radius) {
  vec2 q = abs(point) - halfSize + vec2(radius);
  return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - radius;
}

float capsuleDistance(vec2 point) {
  vec2 q = vec2(max(abs(point.x) - 0.44, 0.0), point.y);
  return length(q) - 0.56;
}

float shapeDistance(vec2 point, float shapeKind) {
  if (shapeKind < 0.5) {
    return length(point) - 1.0;
  }
  if (shapeKind < 1.5) {
    return hexMetric(point) - 0.92;
  }
  if (shapeKind < 2.5) {
    return roundedBoxDistance(rotate45(point), vec2(0.58, 0.58), 0.18);
  }
  if (shapeKind < 3.5) {
    return capsuleDistance(point);
  }
  if (shapeKind < 4.5) {
    return roundedBoxDistance(point, vec2(0.78, 0.78), 0.24);
  }
  return length(point) - 1.0;
}

float glyphDistance(vec2 point, float shapeKind, float scale) {
  vec2 scaled = point / max(scale, 0.08);
  if (shapeKind < 0.5) {
    return 1.0;
  }
  if (shapeKind < 1.5) {
    return abs(hexMetric(scaled) - 0.74) - 0.055;
  }
  if (shapeKind < 2.5) {
    return abs(abs(scaled.x) + abs(scaled.y) - 0.78) - 0.045;
  }
  if (shapeKind < 3.5) {
    return roundedBoxDistance(scaled, vec2(0.56, 0.07), 0.07);
  }
  if (shapeKind < 4.5) {
    return abs(roundedBoxDistance(scaled, vec2(0.48, 0.48), 0.18)) - 0.045;
  }
  return 1.0;
}

void main(void) {
  vec2 unit = vec2(
    v_diffVector.x / max(v_radius * v_aspectRatio, 0.0001),
    v_diffVector.y / max(v_radius, 0.0001)
  );
  float aa = (2.4 * u_correctionRatio) / max(v_radius, 1.0);
  float distance = shapeDistance(unit, v_shapeKind);
  float alpha = 1.0 - smoothstep(-aa, aa, distance);

  #ifdef PICKING_MODE
  if (alpha <= 0.0) {
    gl_FragColor = transparent;
  } else {
    gl_FragColor = v_color;
    gl_FragColor.a *= bias;
  }
  #else
  if (alpha <= 0.0) {
    gl_FragColor = transparent;
    return;
  }

  float outlineNorm = clamp(v_outlineSize / max(v_radius, 1.0), 0.035, 0.28);
  float outlineBlend = 1.0 - smoothstep(-outlineNorm - aa, -outlineNorm + aa, distance);
  float isOutline = 1.0 - outlineBlend;
  float topLight = clamp((-unit.y + 0.85) * 0.5, 0.0, 1.0);
  vec4 color = v_bodyColor;
  color.rgb += vec3(0.014) * pow(topLight, 2.2);

  if (isOutline > 0.0) {
    color = mix(color, v_outlineColor, isOutline);
  }

  float glyphVisible = step(7.25, v_radius) * step(0.13, v_glyphScale) * step(0.5, v_shapeKind) * (1.0 - step(4.5, v_shapeKind));
  float glyph = (1.0 - smoothstep(-aa * 1.4, aa * 1.4, glyphDistance(unit, v_shapeKind, clamp(v_glyphScale, 0.16, 0.52)))) * glyphVisible;
  if (glyph > 0.0 && distance < -outlineNorm) {
    color = mix(color, v_glyphColor, glyph * 0.38);
  }

  color.a *= alpha;
  gl_FragColor = color;
  #endif
}
`;

const ENTITY_TOKEN_VERTEX_SHADER = /* glsl */ `
attribute vec4 a_id;
attribute vec2 a_position;
attribute float a_size;
attribute float a_angle;
attribute vec4 a_bodyColor;
attribute vec4 a_glyphColor;
attribute vec4 a_outlineColor;
attribute float a_outlineSize;
attribute float a_glyphScale;
attribute float a_shapeKind;
attribute float a_aspectRatio;

uniform mat3 u_matrix;
uniform float u_sizeRatio;
uniform float u_correctionRatio;

varying vec4 v_bodyColor;
varying vec4 v_glyphColor;
varying vec4 v_outlineColor;
varying vec4 v_color;
varying vec2 v_diffVector;
varying float v_radius;
varying float v_outlineSize;
varying float v_glyphScale;
varying float v_shapeKind;
varying float v_aspectRatio;

const float bias = 255.0 / 254.0;

void main() {
  float size = a_size * u_correctionRatio / u_sizeRatio * 4.0;
  float aspect = max(a_aspectRatio, 1.0);
  vec2 diffVector = size * vec2(cos(a_angle) * aspect, sin(a_angle));
  vec2 position = a_position + diffVector;

  gl_Position = vec4(
    (u_matrix * vec3(position, 1)).xy,
    0,
    1
  );

  v_diffVector = diffVector;
  v_radius = size / 2.0;
  v_outlineSize = a_outlineSize;
  v_glyphScale = a_glyphScale;
  v_shapeKind = a_shapeKind;
  v_aspectRatio = aspect;

  #ifdef PICKING_MODE
  v_color = a_id;
  #else
  v_bodyColor = a_bodyColor;
  v_glyphColor = a_glyphColor;
  v_outlineColor = a_outlineColor;
  #endif

  v_color.a *= bias;
}
`;

class EntityTokenNodeProgram extends NodeProgram<(typeof ENTITY_TOKEN_UNIFORMS)[number]> {
  static readonly ANGLE_1 = 0;
  static readonly ANGLE_2 = (2 * Math.PI) / 3;
  static readonly ANGLE_3 = (4 * Math.PI) / 3;

  drawLabel = drawSemanticaNodeLabel;

  drawHover = drawSemanticaNodeHover;

  getDefinition() {
    return {
      VERTICES: 3,
      VERTEX_SHADER_SOURCE: ENTITY_TOKEN_VERTEX_SHADER,
      FRAGMENT_SHADER_SOURCE: ENTITY_TOKEN_FRAGMENT_SHADER,
      METHOD: WebGLRenderingContext.TRIANGLES,
      UNIFORMS: ENTITY_TOKEN_UNIFORMS,
      ATTRIBUTES: [
        { name: "a_position", size: 2, type: WebGLRenderingContext.FLOAT },
        { name: "a_size", size: 1, type: WebGLRenderingContext.FLOAT },
        { name: "a_bodyColor", size: 4, type: WebGLRenderingContext.UNSIGNED_BYTE, normalized: true },
        { name: "a_glyphColor", size: 4, type: WebGLRenderingContext.UNSIGNED_BYTE, normalized: true },
        { name: "a_outlineColor", size: 4, type: WebGLRenderingContext.UNSIGNED_BYTE, normalized: true },
        { name: "a_outlineSize", size: 1, type: WebGLRenderingContext.FLOAT },
        { name: "a_glyphScale", size: 1, type: WebGLRenderingContext.FLOAT },
        { name: "a_shapeKind", size: 1, type: WebGLRenderingContext.FLOAT },
        { name: "a_aspectRatio", size: 1, type: WebGLRenderingContext.FLOAT },
        { name: "a_id", size: 4, type: WebGLRenderingContext.UNSIGNED_BYTE, normalized: true },
      ],
      CONSTANT_ATTRIBUTES: [
        { name: "a_angle", size: 1, type: WebGLRenderingContext.FLOAT },
      ],
      CONSTANT_DATA: [
        [EntityTokenNodeProgram.ANGLE_1],
        [EntityTokenNodeProgram.ANGLE_2],
        [EntityTokenNodeProgram.ANGLE_3],
      ],
    };
  }

  processVisibleItem(nodeIndex: number, startIndex: number, data: NodeDisplayData & SemanticaNodeDrawData): void {
    const array = this.array;
    const outlineColor = resolveAccentBorderColor(data.ringSize, data.ringColor, data.borderColor, GRAPH_THEME.nodes.selectedRing.color);
    const outlineSize = Math.max(data.ringSize || 0, data.borderSize || 0.7);

    array[startIndex++] = data.x;
    array[startIndex++] = data.y;
    array[startIndex++] = data.size;
    array[startIndex++] = floatColor(data.color || GRAPH_THEME.palette.overview.nodeCore);
    array[startIndex++] = floatColor(data.shellColor || withAlpha(GRAPH_THEME.palette.overview.nodeBase, 0.58));
    array[startIndex++] = floatColor(outlineColor);
    array[startIndex++] = outlineSize;
    array[startIndex++] = data.coreScale ?? 0.22;
    array[startIndex++] = data.entityShapeKind ?? GRAPH_THEME.nodes.entityShapes[data.entityShape || "entity"].shapeKind;
    array[startIndex++] = data.entityAspectRatio ?? GRAPH_THEME.nodes.entityShapes[data.entityShape || "entity"].aspectRatio;
    array[startIndex++] = nodeIndex;
  }

  setUniforms(params: RenderParams, { gl, uniformLocations }: ProgramInfo<(typeof ENTITY_TOKEN_UNIFORMS)[number]>): void {
    gl.uniform1f(uniformLocations.u_correctionRatio, params.correctionRatio);
    gl.uniform1f(uniformLocations.u_sizeRatio, params.sizeRatio);
    gl.uniformMatrix3fv(uniformLocations.u_matrix, false, params.matrix);
  }
}

function resolveAccentBorderColor(
  ringSize: number | undefined,
  ringColor: string | undefined,
  borderColor: string | undefined,
  fallbackColor: string,
) {
  if (typeof ringSize === "number" && ringSize > 0 && ringColor) {
    return ringColor;
  }

  return borderColor || fallbackColor;
}

function drawRoundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  const clampedRadius = Math.max(0, Math.min(radius, Math.min(width, height) / 2));
  context.beginPath();
  context.moveTo(x + clampedRadius, y);
  context.lineTo(x + width - clampedRadius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + clampedRadius);
  context.lineTo(x + width, y + height - clampedRadius);
  context.quadraticCurveTo(x + width, y + height, x + width - clampedRadius, y + height);
  context.lineTo(x + clampedRadius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - clampedRadius);
  context.lineTo(x, y + clampedRadius);
  context.quadraticCurveTo(x, y, x + clampedRadius, y);
  context.closePath();
}

export const drawSemanticaNodeLabel: NodeLabelDrawingFunction = (context, rawData) => {
  const data = rawData as typeof rawData & SemanticaNodeDrawData;
  if (!data.label) {
    return;
  }

  const chipTheme = GRAPH_THEME.labels.chip;
  const fontSize = Math.max(
    chipTheme.fontSize,
    Math.min(chipTheme.maxFontSize, data.size * chipTheme.sizeScale),
  );
  const font = `${chipTheme.fontWeight} ${fontSize}px ${chipTheme.fontFamily}`;
  const paddingX = chipTheme.paddingX;
  const paddingY = chipTheme.paddingY;
  const borderColor = resolveAccentBorderColor(data.ringSize, data.ringColor, data.borderColor, chipTheme.borderColor);

  context.save();
  context.font = font;
  context.textBaseline = "middle";
  const metrics = context.measureText(data.label);
  const width = metrics.width + paddingX * 2;
  const height = fontSize + paddingY * 2;
  const x = data.x + Math.max(data.size * 0.7, chipTheme.offsetX);
  const y = data.y - Math.max(data.size * 0.9, chipTheme.offsetY) - height;

  context.shadowColor = withAlpha(chipTheme.shadowColor, chipTheme.shadowAlpha);
  context.shadowBlur = chipTheme.shadowBlur;
  context.fillStyle = chipTheme.background;
  drawRoundedRect(context, x, y, width, height, chipTheme.radius);
  context.fill();

  context.shadowBlur = 0;
  context.strokeStyle = withAlpha(borderColor, chipTheme.borderAlpha);
  context.lineWidth = 1;
  drawRoundedRect(context, x, y, width, height, chipTheme.radius);
  context.stroke();

  context.fillStyle = chipTheme.textColor;
  context.fillText(data.label, x + paddingX, y + height / 2);
  context.restore();
};

export const drawSemanticaNodeHover: NodeHoverDrawingFunction = (context, rawData) => {
  const data = rawData as typeof rawData & SemanticaNodeDrawData;
  if (!data.label) {
    return;
  }

  const hoverTheme = GRAPH_THEME.labels.hoverCard;
  const borderColor = resolveAccentBorderColor(data.ringSize, data.ringColor, data.borderColor, hoverTheme.borderColor);
  const metaLabel = (typeof data.nodeType === "string" && data.nodeType.trim().length > 0)
    ? data.nodeType.replaceAll("_", " ").toUpperCase()
    : "NODE";

  context.save();
  context.textBaseline = "top";

  const titleFont = `${hoverTheme.titleWeight} ${hoverTheme.titleSize}px ${hoverTheme.fontFamily}`;
  const metaFont = `${hoverTheme.metaWeight} ${hoverTheme.metaSize}px ${hoverTheme.fontFamily}`;
  context.font = titleFont;
  const titleWidth = context.measureText(data.label).width;
  context.font = metaFont;
  const metaWidth = context.measureText(metaLabel).width;

  const width = Math.max(titleWidth, metaWidth) + hoverTheme.paddingX * 2;
  const height = hoverTheme.paddingY * 2 + hoverTheme.titleSize + hoverTheme.metaGap + hoverTheme.metaSize;
  const x = data.x + Math.max(data.size * 0.9, hoverTheme.offsetX);
  const y = data.y - Math.max(data.size * 1.1, hoverTheme.offsetY) - height;

  context.shadowColor = withAlpha(hoverTheme.shadowColor, hoverTheme.shadowAlpha);
  context.shadowBlur = hoverTheme.shadowBlur;
  context.fillStyle = hoverTheme.background;
  drawRoundedRect(context, x, y, width, height, hoverTheme.radius);
  context.fill();

  context.shadowBlur = 0;
  context.strokeStyle = withAlpha(borderColor, hoverTheme.borderAlpha);
  context.lineWidth = 1.2;
  drawRoundedRect(context, x, y, width, height, hoverTheme.radius);
  context.stroke();

  context.fillStyle = hoverTheme.textColor;
  context.font = titleFont;
  context.fillText(data.label, x + hoverTheme.paddingX, y + hoverTheme.paddingY);

  context.fillStyle = hoverTheme.metaColor;
  context.font = metaFont;
  context.fillText(
    metaLabel,
    x + hoverTheme.paddingX,
    y + hoverTheme.paddingY + hoverTheme.titleSize + hoverTheme.metaGap,
  );

  context.restore();
};

export const SEMANTICA_NODE_PROGRAM_CLASSES = {
  ...DEFAULT_NODE_PROGRAM_CLASSES,
  circle: EntityTokenNodeProgram,
};

export const SEMANTICA_EDGE_PROGRAM_CLASSES = {
  ...DEFAULT_EDGE_PROGRAM_CLASSES,
  curve: EdgeCurveProgram,
  curvedArrow: EdgeCurvedArrowProgram,
};
