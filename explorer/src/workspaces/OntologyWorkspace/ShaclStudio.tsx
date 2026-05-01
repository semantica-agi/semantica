import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import Editor, { type Monaco } from "@monaco-editor/react";
import { FileCode2, Loader2, Play, Shield, Wand2 } from "lucide-react";
import {
  generateShacl,
  loadOntologyRegistry,
  loadShaclShapes,
  validateShacl,
} from "./api";
import type { OntologyEntry, ShaclShapeSummary, ShaclValidationResponse } from "./types";

interface ShaclStudioProps {
  onJumpToNode?: (nodeId: string) => void;
}

export function ShaclStudio({ onJumpToNode }: ShaclStudioProps) {
  const [registry, setRegistry] = useState<OntologyEntry[]>([]);
  const [selectedUri, setSelectedUri] = useState("");
  const [shacl, setShacl] = useState("");
  const [shapes, setShapes] = useState<ShaclShapeSummary[]>([]);
  const [validation, setValidation] = useState<ShaclValidationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadOntologyRegistry()
      .then((entries) => {
        if (cancelled) return;
        setRegistry(entries);
        setSelectedUri((current) => current || entries[0]?.uri || "");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load ontology registry.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadShapes = useCallback(async (uri: string) => {
    if (!uri) return;
    setLoading(true);
    setError("");
    try {
      const data = await loadShaclShapes(uri);
      setShapes(data.shapes);
      setShacl((current) => current || data.shacl_turtle);
      setValidation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load SHACL shapes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setShacl("");
    void loadShapes(selectedUri);
  }, [selectedUri, loadShapes]);

  const handleGenerate = async () => {
    if (!selectedUri) return;
    setLoading(true);
    setError("");
    try {
      const data = await generateShacl(selectedUri, "strict");
      setShacl(data.shacl_turtle);
      const shapeData = await loadShaclShapes(selectedUri);
      setShapes(shapeData.shapes);
      setValidation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate SHACL.");
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    if (!selectedUri || !shacl.trim()) return;
    setLoading(true);
    setError("");
    try {
      setValidation(await validateShacl(selectedUri, shacl));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not validate SHACL.");
    } finally {
      setLoading(false);
    }
  };

  const groupedShapes = useMemo(() => {
    const groups = new Map<string, ShaclShapeSummary[]>();
    for (const shape of shapes) {
      const key = shape.target_class || "Untargeted shapes";
      groups.set(key, [...(groups.get(key) || []), shape]);
    }
    return Array.from(groups.entries());
  }, [shapes]);

  const beforeMount = (monaco: Monaco) => {
    if (!monaco.languages.getLanguages().some((language: { id: string }) => language.id === "turtle")) {
      monaco.languages.register({ id: "turtle" });
    }
    monaco.editor.defineTheme("shacl-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "keyword", foreground: "9ee8d7" },
        { token: "string", foreground: "f2b66d" },
      ],
      colors: {
        "editor.background": "#050b13",
        "editor.foreground": "#d7e7f8",
        "editorLineNumber.foreground": "#41536b",
      },
    });
  };

  return (
    <div style={pageStyle}>
      <section style={heroStyle}>
        <div>
          <div style={kickerStyle}><Shield size={14} /> SHACL Studio</div>
          <h2 style={titleStyle}>Generate, edit, and validate shapes</h2>
          <p style={textStyle}>
            Create strict SHACL Turtle from ontology structure, inspect shape targets,
            run validation, and jump from violations back into the graph.
          </p>
        </div>
        <div style={selectorShellStyle}>
          <label style={labelStyle}>Ontology</label>
          <select style={inputStyle} value={selectedUri} onChange={(event) => setSelectedUri(event.target.value)}>
            {registry.map((entry) => <option key={entry.uri} value={entry.uri}>{entry.name}</option>)}
          </select>
        </div>
      </section>

      {error ? <div style={errorStyle}>{error}</div> : null}

      <div style={gridStyle}>
        <section style={cardStyle}>
          <div style={panelHeaderStyle}>
            <h3 style={sectionTitleStyle}>Shape library</h3>
            <span style={countBadgeStyle}>{shapes.length} shapes</span>
          </div>
          <div style={shapeListStyle}>
            {groupedShapes.map(([target, items]) => (
              <div key={target} style={shapeGroupStyle}>
                <div style={shapeTargetStyle}>{target}</div>
                {items.map((shape) => (
                  <div key={shape.id} style={shapeRowStyle}>
                    <FileCode2 size={14} color="#9ee8d7" />
                    <div>
                      <div style={{ color: "#ebf3ff", fontWeight: 800 }}>{shape.id}</div>
                      <div style={mutedStyle}>
                        {shape.constraint_count} constraints
                        {shape.constraints.length ? ` · ${shape.constraints.join(", ")}` : ""}
                      </div>
                    </div>
                    <span style={violationBadgeStyle}>{shape.violation_count}</span>
                  </div>
                ))}
              </div>
            ))}
            {!shapes.length ? <p style={mutedStyle}>No shapes generated yet.</p> : null}
          </div>
        </section>

        <section style={editorShellStyle}>
          <div style={panelHeaderStyle}>
            <h3 style={sectionTitleStyle}>Turtle shape editor</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <button style={secondaryButtonStyle} disabled={loading} onClick={handleGenerate}><Wand2 size={14} /> Generate strict</button>
              <button style={primaryButtonStyle} disabled={loading || !shacl.trim()} onClick={handleValidate}>
                {loading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                Validate
              </button>
            </div>
          </div>
          <div style={editorFrameStyle}>
            <Editor
              height="100%"
              language="turtle"
              theme="shacl-dark"
              beforeMount={beforeMount}
              value={shacl}
              onChange={(value) => setShacl(value || "")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: "JetBrains Mono, monospace",
                wordWrap: "on",
                scrollBeyondLastLine: false,
              }}
            />
          </div>
        </section>
      </div>

      <section style={cardStyle}>
        <div style={panelHeaderStyle}>
          <h3 style={sectionTitleStyle}>Validation report</h3>
          {validation ? <span style={validationBadgeStyle(validation.status, validation.conforms)}>{validation.status}{validation.conforms ? " · conforms" : ""}</span> : null}
        </div>
        {validation ? (
          <>
            <p style={textStyle}>{validation.message}</p>
            <div style={shapeListStyle}>
              {validation.violations.map((violation, index) => {
                const nodeId = violation.focus_node || violation.node;
                return (
                  <div key={`${violation.node}-${violation.path}-${index}`} style={violationRowStyle}>
                    <div>
                      <div style={{ color: "#ebf3ff", fontWeight: 800 }}>{violation.message}</div>
                      <div style={mutedStyle}>{violation.severity} {violation.path ? `· ${violation.path}` : ""}</div>
                      {nodeId ? <div style={monoStyle}>{nodeId}</div> : null}
                    </div>
                    {nodeId ? (
                      <button style={smallButtonStyle} onClick={() => onJumpToNode?.(nodeId)}>
                        Jump to Node
                      </button>
                    ) : null}
                  </div>
                );
              })}
              {!validation.violations.length ? <p style={mutedStyle}>No validation violations returned.</p> : null}
            </div>
          </>
        ) : (
          <p style={mutedStyle}>Generate or edit SHACL Turtle, then run validation.</p>
        )}
      </section>
    </div>
  );
}

function validationBadgeStyle(status: string, conforms: boolean): CSSProperties {
  const color = status === "unavailable" ? "#f2b66d" : conforms ? "#7ce7d3" : "#ff9daf";
  return { color, border: `1px solid ${color}35`, background: `${color}14`, borderRadius: 999, padding: "4px 9px", fontSize: 11, fontWeight: 900, textTransform: "uppercase" };
}

const pageStyle: CSSProperties = { height: "100%", overflow: "auto", padding: 22, display: "flex", flexDirection: "column", gap: 16 };
const heroStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 18, padding: 22, border: "1px solid rgba(127,208,255,0.12)", borderRadius: 22, background: "linear-gradient(135deg, rgba(11,25,42,0.94), rgba(7,14,25,0.9))" };
const kickerStyle: CSSProperties = { display: "inline-flex", gap: 8, alignItems: "center", color: "#9ee8d7", fontSize: 11, fontWeight: 900, letterSpacing: "0.12em", textTransform: "uppercase" };
const titleStyle: CSSProperties = { margin: "8px 0", color: "#ebf3ff", fontSize: 26, letterSpacing: "-0.04em" };
const textStyle: CSSProperties = { margin: 0, color: "#8fa8c6", lineHeight: 1.6, maxWidth: 680 };
const selectorShellStyle: CSSProperties = { minWidth: 320 };
const labelStyle: CSSProperties = { display: "block", color: "#6a7f97", fontSize: 11, fontWeight: 800, margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" };
const inputStyle: CSSProperties = { width: "100%", boxSizing: "border-box", border: "1px solid rgba(127,208,255,0.14)", borderRadius: 12, padding: "10px 12px", background: "rgba(3,9,18,0.8)", color: "#ebf3ff" };
const gridStyle: CSSProperties = { display: "grid", gridTemplateColumns: "360px minmax(0, 1fr)", gap: 16, minHeight: 560 };
const cardStyle: CSSProperties = { padding: 18, border: "1px solid rgba(127,208,255,0.12)", borderRadius: 20, background: "rgba(9,19,34,0.78)" };
const editorShellStyle: CSSProperties = { ...cardStyle, display: "flex", flexDirection: "column", minHeight: 560 };
const panelHeaderStyle: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 };
const sectionTitleStyle: CSSProperties = { margin: 0, color: "#ebf3ff", fontSize: 16 };
const countBadgeStyle: CSSProperties = { color: "#9ee8d7", border: "1px solid rgba(158,232,215,0.2)", borderRadius: 999, padding: "4px 9px", fontSize: 11, fontWeight: 900 };
const shapeListStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 10 };
const shapeGroupStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 6 };
const shapeTargetStyle: CSSProperties = { color: "#6a7f97", fontSize: 11, fontWeight: 900, textTransform: "uppercase", letterSpacing: "0.08em" };
const shapeRowStyle: CSSProperties = { display: "grid", gridTemplateColumns: "18px 1fr auto", gap: 10, padding: 10, borderRadius: 14, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(127,208,255,0.08)" };
const violationBadgeStyle: CSSProperties = { color: "#f2b66d", fontWeight: 900 };
const editorFrameStyle: CSSProperties = { flex: 1, minHeight: 0, border: "1px solid rgba(127,208,255,0.12)", borderRadius: 16, overflow: "hidden" };
const primaryButtonStyle: CSSProperties = { border: "1px solid rgba(124,231,211,0.35)", borderRadius: 12, padding: "9px 11px", background: "linear-gradient(135deg, rgba(20,151,136,0.55), rgba(74,163,255,0.35))", color: "#ebf3ff", fontWeight: 900, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8 };
const secondaryButtonStyle: CSSProperties = { ...primaryButtonStyle, background: "rgba(127,208,255,0.08)", borderColor: "rgba(127,208,255,0.18)" };
const violationRowStyle: CSSProperties = { display: "grid", gridTemplateColumns: "1fr auto", gap: 12, padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(127,208,255,0.08)" };
const smallButtonStyle: CSSProperties = { border: "1px solid rgba(127,208,255,0.16)", borderRadius: 10, padding: "7px 9px", background: "rgba(127,208,255,0.08)", color: "#ebf3ff", cursor: "pointer", fontWeight: 800 };
const monoStyle: CSSProperties = { marginTop: 4, color: "#6a7f97", fontSize: 11, fontFamily: "JetBrains Mono, monospace", wordBreak: "break-all" };
const mutedStyle: CSSProperties = { margin: 0, color: "#6a7f97", fontSize: 12, lineHeight: 1.5 };
const errorStyle: CSSProperties = { padding: 12, borderRadius: 14, color: "#ffb4c2", background: "rgba(255,157,175,0.1)", border: "1px solid rgba(255,157,175,0.18)" };
