import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { Download, HeartPulse, Loader2, Wrench } from "lucide-react";
import { loadOntologyHealth, loadOntologyRegistry } from "./api";
import type { OntologyEntry, OntologyHealthResponse, HealthIssue } from "./types";

interface HealthTabProps {
  onFixInEditor?: (entityUri: string) => void;
}

export function HealthTab({ onFixInEditor }: HealthTabProps) {
  const [registry, setRegistry] = useState<OntologyEntry[]>([]);
  const [selectedUri, setSelectedUri] = useState("");
  const [health, setHealth] = useState<OntologyHealthResponse | null>(null);
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

  const loadHealth = useCallback(async (uri: string) => {
    if (!uri) return;
    setLoading(true);
    setError("");
    try {
      setHealth(await loadOntologyHealth(uri));
    } catch (err) {
      setHealth(null);
      setError(err instanceof Error ? err.message : "Could not load ontology health.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHealth(selectedUri);
  }, [selectedUri, loadHealth]);

  const exportReport = useCallback(() => {
    if (!health) return;
    const blob = new Blob([JSON.stringify(health, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${health.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-health.json`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    setTimeout(() => URL.revokeObjectURL(url), 100);
  }, [health]);

  return (
    <div style={pageStyle}>
      <section style={heroStyle}>
        <div>
          <div style={kickerStyle}><HeartPulse size={14} /> Ontology Health</div>
          <h2 style={titleStyle}>Quality and governance signals</h2>
          <p style={textStyle}>
            Score completeness, consistency, SHACL readiness, alignment coverage,
            and documentation quality for the selected ontology.
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

      {loading ? (
        <div style={loadingStyle}><Loader2 size={18} className="spin" /> Computing health dashboard...</div>
      ) : health ? (
        <>
          <section style={{ ...scoreGridStyle, gridTemplateColumns: `220px repeat(${health.dimensions.length}, minmax(180px, 1fr))` }}>
            <div style={scoreCardStyle}>
              <span style={scoreValueStyle}>{Math.round(health.total_score)}</span>
              <span style={mutedStyle}>Total health score</span>
              <button style={secondaryButtonStyle} onClick={exportReport}><Download size={14} /> Export report</button>
            </div>
            {health.dimensions.map((dimension) => (
              <div key={dimension.key} style={dimensionCardStyle}>
                <div style={dimensionHeadStyle}>
                  <span style={{ color: "#ebf3ff", fontWeight: 900 }}>{dimension.label}</span>
                  <span style={statusBadgeStyle(dimension.status)}>{dimension.status}</span>
                </div>
                <div style={barTrackStyle}>
                  <div style={{ ...barFillStyle, width: `${dimension.score}%`, background: dimensionColor(dimension.score, dimension.status) }} />
                </div>
                <div style={dimensionFootStyle}>
                  <span>{Math.round(dimension.score)} / 100</span>
                  <span>{dimension.detail}</span>
                </div>
              </div>
            ))}
          </section>

          <section style={cardStyle}>
            <h3 style={sectionTitleStyle}>Actionable issues</h3>
            <div style={issueListStyle}>
              {health.issues.map((issue) => (
                <IssueRow key={issue.id} issue={issue} onFixInEditor={onFixInEditor} />
              ))}
              {!health.issues.length ? <p style={mutedStyle}>No actionable issues reported for this ontology.</p> : null}
            </div>
          </section>
        </>
      ) : (
        <div style={emptyStyle}>Select an ontology to compute health signals.</div>
      )}
    </div>
  );
}

function IssueRow({ issue, onFixInEditor }: { issue: HealthIssue; onFixInEditor?: (entityUri: string) => void }) {
  return (
    <div style={issueRowStyle}>
      <div style={severityDotStyle(issue.severity)} />
      <div>
        <div style={{ color: "#ebf3ff", fontWeight: 800 }}>{issue.entity_label || issue.category}</div>
        <div style={{ color: "#8fa8c6", fontSize: 13, lineHeight: 1.45 }}>{issue.message}</div>
        {issue.entity_uri ? <div style={monoStyle}>{issue.entity_uri}</div> : null}
      </div>
      <span style={categoryStyle}>{issue.category}</span>
      {issue.entity_uri ? (
        <button style={smallButtonStyle} onClick={() => onFixInEditor?.(issue.entity_uri || "")}>
          <Wrench size={13} />
          Fix in Editor
        </button>
      ) : (
        <div />
      )}
    </div>
  );
}

function dimensionColor(score: number, status: string) {
  if (status === "unavailable") return "#6a7f97";
  if (score >= 80) return "#7ce7d3";
  if (score >= 55) return "#f2b66d";
  return "#ff9daf";
}

function statusBadgeStyle(status: string): CSSProperties {
  const color = status === "ok" ? "#7ce7d3" : status === "unavailable" ? "#6a7f97" : "#f2b66d";
  return {
    color,
    background: `${color}18`,
    border: `1px solid ${color}30`,
    borderRadius: 999,
    padding: "2px 7px",
    fontSize: 10,
    fontWeight: 900,
    textTransform: "uppercase",
  };
}

function severityDotStyle(severity: string): CSSProperties {
  const color = severity === "critical" ? "#ff9daf" : severity === "warning" ? "#f2b66d" : "#58a6ff";
  return { width: 10, height: 10, borderRadius: "50%", background: color, boxShadow: `0 0 18px ${color}55`, marginTop: 5 };
}

const pageStyle: CSSProperties = { height: "100%", overflow: "auto", padding: 22, display: "flex", flexDirection: "column", gap: 16 };
const heroStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 18, padding: 22, border: "1px solid rgba(127,208,255,0.12)", borderRadius: 22, background: "linear-gradient(135deg, rgba(11,25,42,0.94), rgba(7,14,25,0.9))" };
const kickerStyle: CSSProperties = { display: "inline-flex", gap: 8, alignItems: "center", color: "#9ee8d7", fontSize: 11, fontWeight: 900, letterSpacing: "0.12em", textTransform: "uppercase" };
const titleStyle: CSSProperties = { margin: "8px 0", color: "#ebf3ff", fontSize: 26, letterSpacing: "-0.04em" };
const textStyle: CSSProperties = { margin: 0, color: "#8fa8c6", lineHeight: 1.6, maxWidth: 620 };
const selectorShellStyle: CSSProperties = { minWidth: 320 };
const labelStyle: CSSProperties = { display: "block", color: "#6a7f97", fontSize: 11, fontWeight: 800, margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" };
const inputStyle: CSSProperties = { width: "100%", boxSizing: "border-box", border: "1px solid rgba(127,208,255,0.14)", borderRadius: 12, padding: "10px 12px", background: "rgba(3,9,18,0.8)", color: "#ebf3ff" };
const scoreGridStyle: CSSProperties = { display: "grid", gridTemplateColumns: "220px repeat(5, minmax(180px, 1fr))", gap: 12 };
const scoreCardStyle: CSSProperties = { padding: 18, borderRadius: 20, background: "rgba(15,35,52,0.88)", border: "1px solid rgba(124,231,211,0.2)", display: "flex", flexDirection: "column", gap: 10 };
const scoreValueStyle: CSSProperties = { color: "#9ee8d7", fontSize: 52, lineHeight: 1, fontWeight: 950, letterSpacing: "-0.06em" };
const dimensionCardStyle: CSSProperties = { padding: 16, borderRadius: 18, background: "rgba(9,19,34,0.78)", border: "1px solid rgba(127,208,255,0.12)" };
const dimensionHeadStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", marginBottom: 12 };
const barTrackStyle: CSSProperties = { height: 8, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" };
const barFillStyle: CSSProperties = { height: "100%", borderRadius: 999 };
const dimensionFootStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 6, color: "#8fa8c6", fontSize: 12, marginTop: 10 };
const cardStyle: CSSProperties = { padding: 18, border: "1px solid rgba(127,208,255,0.12)", borderRadius: 20, background: "rgba(9,19,34,0.78)" };
const sectionTitleStyle: CSSProperties = { margin: "0 0 14px", color: "#ebf3ff", fontSize: 16 };
const issueListStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 8 };
const issueRowStyle: CSSProperties = { display: "grid", gridTemplateColumns: "14px 1fr auto auto", gap: 12, alignItems: "start", padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(127,208,255,0.08)" };
const categoryStyle: CSSProperties = { color: "#9ee8d7", border: "1px solid rgba(158,232,215,0.22)", borderRadius: 999, padding: "4px 8px", fontSize: 10, fontWeight: 900 };
const smallButtonStyle: CSSProperties = { display: "inline-flex", gap: 6, alignItems: "center", border: "1px solid rgba(127,208,255,0.16)", borderRadius: 10, padding: "7px 9px", background: "rgba(127,208,255,0.08)", color: "#ebf3ff", cursor: "pointer", fontWeight: 800 };
const secondaryButtonStyle: CSSProperties = { display: "inline-flex", gap: 8, alignItems: "center", justifyContent: "center", border: "1px solid rgba(127,208,255,0.16)", borderRadius: 12, padding: "10px 12px", background: "rgba(127,208,255,0.08)", color: "#ebf3ff", cursor: "pointer", fontWeight: 900 };
const monoStyle: CSSProperties = { marginTop: 4, color: "#6a7f97", fontSize: 11, fontFamily: "JetBrains Mono, monospace", wordBreak: "break-all" };
const mutedStyle: CSSProperties = { margin: 0, color: "#6a7f97", fontSize: 13 };
const loadingStyle: CSSProperties = { display: "inline-flex", alignItems: "center", gap: 8, color: "#8fa8c6", padding: 18 };
const emptyStyle: CSSProperties = { color: "#6a7f97", padding: 22 };
const errorStyle: CSSProperties = { display: "flex", alignItems: "center", gap: 8, padding: 12, borderRadius: 14, color: "#ffb4c2", background: "rgba(255,157,175,0.1)", border: "1px solid rgba(255,157,175,0.18)" };
