import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { GitMerge, Loader2, Sparkles, Trash2 } from "lucide-react";
import {
  loadAlignments,
  loadOntologyRegistry,
  removeAlignment,
  saveAlignment,
  suggestAlignments,
} from "./api";
import type { AlignmentRelation, AlignmentSuggestion, OntologyAlignment, OntologyEntry } from "./types";

const RELATIONS: AlignmentRelation[] = [
  "owl:equivalentClass",
  "owl:equivalentProperty",
  "skos:exactMatch",
  "skos:closeMatch",
  "skos:broadMatch",
  "skos:narrowMatch",
  "skos:relatedMatch",
];

const RELATION_COLORS: Record<AlignmentRelation, string> = {
  "owl:equivalentClass": "#7ce7d3",
  "owl:equivalentProperty": "#7ce7d3",
  "skos:exactMatch": "#9ee8d7",
  "skos:closeMatch": "#58a6ff",
  "skos:broadMatch": "#f2b66d",
  "skos:narrowMatch": "#f2b66d",
  "skos:relatedMatch": "#d2a8ff",
};

export function AlignmentsTab() {
  const [registry, setRegistry] = useState<OntologyEntry[]>([]);
  const [alignments, setAlignments] = useState<OntologyAlignment[]>([]);
  const [suggestions, setSuggestions] = useState<AlignmentSuggestion[]>([]);
  const [sourceOntology, setSourceOntology] = useState("");
  const [targetOntology, setTargetOntology] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [targetUri, setTargetUri] = useState("");
  const [relation, setRelation] = useState<AlignmentRelation>("skos:exactMatch");
  const [confidence, setConfidence] = useState(0.86);
  const [provenance, setProvenance] = useState("");
  const [source, setSource] = useState("Ontology Hub");
  const [reviewer, setReviewer] = useState("");
  const [threshold, setThreshold] = useState(0.68);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    try {
      const [registryData, alignmentData] = await Promise.all([
        loadOntologyRegistry(),
        loadAlignments(),
      ]);
      setRegistry(registryData);
      setAlignments(alignmentData);
      setSourceOntology((current) => current || registryData[0]?.uri || "");
      setTargetOntology((current) => current || registryData[1]?.uri || registryData[0]?.uri || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load ontology alignments.");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const relationCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of alignments) {
      counts.set(item.relation, (counts.get(item.relation) ?? 0) + 1);
    }
    return counts;
  }, [alignments]);

  const handleSave = async () => {
    if (!sourceUri.trim() || !targetUri.trim()) {
      setError("Provide both source and target entity URIs.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await saveAlignment({
        source_uri: sourceUri.trim(),
        target_uri: targetUri.trim(),
        relation,
        confidence,
        provenance: provenance || undefined,
        source: source || undefined,
        reviewer: reviewer || undefined,
      });
      setSourceUri("");
      setTargetUri("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save alignment.");
    } finally {
      setBusy(false);
    }
  };

  const handleSuggest = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await suggestAlignments({
        source_ontology_uri: sourceOntology || undefined,
        target_ontology_uri: targetOntology || undefined,
        threshold,
        limit: 40,
      });
      setSuggestions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not suggest alignments.");
    } finally {
      setBusy(false);
    }
  };

  const handleAcceptSuggestion = (suggestion: AlignmentSuggestion) => {
    setSourceUri(suggestion.source_uri);
    setTargetUri(suggestion.target_uri);
    setRelation(suggestion.relation);
    setConfidence(Math.max(0.1, Math.min(1, suggestion.score)));
    setProvenance(suggestion.reason);
  };

  const handleRemove = async (id: string) => {
    setBusy(true);
    setError("");
    try {
      await removeAlignment(id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove alignment.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={pageStyle}>
      <section style={heroStyle}>
        <div>
          <div style={kickerStyle}><GitMerge size={14} /> Alignment Matrix</div>
          <h2 style={titleStyle}>Cross-ontology mappings</h2>
          <p style={textStyle}>
            Manage equivalence and SKOS match relations with confidence, provenance,
            reviewer context, and label-based suggestions.
          </p>
        </div>
        <div style={summaryGridStyle}>
          <Metric label="Mappings" value={alignments.length} />
          <Metric label="Relations" value={relationCounts.size} />
          <Metric label="Suggestions" value={suggestions.length} />
        </div>
      </section>

      {error ? <div style={errorStyle}>{error}</div> : null}

      <div style={gridStyle}>
        <section style={cardStyle}>
          <h3 style={sectionTitleStyle}>Create or update alignment</h3>
          <label style={labelStyle}>Source entity URI</label>
          <input style={inputStyle} value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} />
          <label style={labelStyle}>Target entity URI</label>
          <input style={inputStyle} value={targetUri} onChange={(event) => setTargetUri(event.target.value)} />
          <div style={twoColStyle}>
            <div>
              <label style={labelStyle}>Relation</label>
              <select style={inputStyle} value={relation} onChange={(event) => setRelation(event.target.value as AlignmentRelation)}>
                {RELATIONS.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Confidence {confidence.toFixed(2)}</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={confidence}
                onChange={(event) => setConfidence(Number(event.target.value))}
                style={{ width: "100%" }}
              />
            </div>
          </div>
          <label style={labelStyle}>Provenance note</label>
          <textarea style={{ ...inputStyle, minHeight: 74, resize: "vertical" }} value={provenance} onChange={(event) => setProvenance(event.target.value)} />
          <div style={twoColStyle}>
            <div>
              <label style={labelStyle}>Source</label>
              <input style={inputStyle} value={source} onChange={(event) => setSource(event.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Reviewer</label>
              <input style={inputStyle} value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
            </div>
          </div>
          <button style={primaryButtonStyle} disabled={busy} onClick={handleSave}>
            {busy ? <Loader2 size={14} className="spin" /> : <GitMerge size={14} />}
            Save alignment
          </button>
        </section>

        <section style={cardStyle}>
          <h3 style={sectionTitleStyle}>Suggest alignments</h3>
          <div style={twoColStyle}>
            <div>
              <label style={labelStyle}>Source ontology</label>
              <select style={inputStyle} value={sourceOntology} onChange={(event) => setSourceOntology(event.target.value)}>
                <option value="">Any ontology</option>
                {registry.map((entry) => <option key={entry.uri} value={entry.uri}>{entry.name}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Target ontology</label>
              <select style={inputStyle} value={targetOntology} onChange={(event) => setTargetOntology(event.target.value)}>
                <option value="">Any ontology</option>
                {registry.map((entry) => <option key={entry.uri} value={entry.uri}>{entry.name}</option>)}
              </select>
            </div>
          </div>
          <label style={labelStyle}>Similarity threshold {threshold.toFixed(2)}</label>
          <input
            type="range"
            min="0.25"
            max="0.95"
            step="0.01"
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
            style={{ width: "100%" }}
          />
          <button style={secondaryButtonStyle} disabled={busy} onClick={handleSuggest}>
            <Sparkles size={14} />
            Suggest alignments
          </button>
          <div style={suggestionListStyle}>
            {suggestions.map((item) => (
              <button key={`${item.source_uri}-${item.target_uri}-${item.relation}`} style={suggestionStyle} onClick={() => handleAcceptSuggestion(item)}>
                <span style={{ color: "#ebf3ff", fontWeight: 800 }}>{item.source_label}</span>
                <span style={{ color: RELATION_COLORS[item.relation] }}>{item.relation}</span>
                <span style={{ color: "#ebf3ff", fontWeight: 800 }}>{item.target_label}</span>
                <span style={{ color: "#8fa8c6" }}>{Math.round(item.score * 100)}%</span>
              </button>
            ))}
            {!suggestions.length ? <p style={mutedStyle}>Run suggestions to review ranked candidate mappings.</p> : null}
          </div>
        </section>
      </div>

      <section style={cardStyle}>
        <h3 style={sectionTitleStyle}>Recorded alignments</h3>
        <div style={tableStyle}>
          {alignments.map((item) => (
            <div key={item.id} style={rowStyle}>
              <div>
                <div style={{ color: "#ebf3ff", fontWeight: 800 }}>{item.source_label || item.source_uri}</div>
                <div style={monoStyle}>{item.source_uri}</div>
              </div>
              <div style={{ ...relationBadgeStyle, color: RELATION_COLORS[item.relation], borderColor: `${RELATION_COLORS[item.relation]}55` }}>
                {item.relation}
              </div>
              <div>
                <div style={{ color: "#ebf3ff", fontWeight: 800 }}>{item.target_label || item.target_uri}</div>
                <div style={monoStyle}>{item.target_uri}</div>
              </div>
              <div style={confidenceStyle}>{Math.round(item.confidence * 100)}%</div>
              <button style={iconButtonStyle} disabled={busy} onClick={() => handleRemove(item.id)} title="Remove alignment">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          {!alignments.length ? <p style={mutedStyle}>No alignments recorded yet.</p> : null}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div style={metricStyle}>
      <span style={{ color: "#9ee8d7", fontSize: 20, fontWeight: 900 }}>{value.toLocaleString()}</span>
      <span style={{ color: "#6a7f97", fontSize: 11 }}>{label}</span>
    </div>
  );
}

const pageStyle: CSSProperties = { height: "100%", overflow: "auto", padding: 22, display: "flex", flexDirection: "column", gap: 16 };
const heroStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 18, padding: 22, border: "1px solid rgba(127,208,255,0.12)", borderRadius: 22, background: "linear-gradient(135deg, rgba(11,25,42,0.94), rgba(7,14,25,0.9))" };
const kickerStyle: CSSProperties = { display: "inline-flex", gap: 8, alignItems: "center", color: "#9ee8d7", fontSize: 11, fontWeight: 900, letterSpacing: "0.12em", textTransform: "uppercase" };
const titleStyle: CSSProperties = { margin: "8px 0", color: "#ebf3ff", fontSize: 26, letterSpacing: "-0.04em" };
const textStyle: CSSProperties = { margin: 0, color: "#8fa8c6", lineHeight: 1.6, maxWidth: 620 };
const summaryGridStyle: CSSProperties = { display: "grid", gridTemplateColumns: "repeat(3, minmax(100px, 1fr))", gap: 10, minWidth: 320 };
const metricStyle: CSSProperties = { padding: 14, borderRadius: 16, background: "rgba(255,255,255,0.035)", border: "1px solid rgba(127,208,255,0.1)", display: "flex", flexDirection: "column", gap: 4 };
const gridStyle: CSSProperties = { display: "grid", gridTemplateColumns: "minmax(320px, 0.9fr) minmax(360px, 1.1fr)", gap: 16 };
const cardStyle: CSSProperties = { padding: 18, border: "1px solid rgba(127,208,255,0.12)", borderRadius: 20, background: "rgba(9,19,34,0.78)", boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)" };
const sectionTitleStyle: CSSProperties = { margin: "0 0 14px", color: "#ebf3ff", fontSize: 16 };
const labelStyle: CSSProperties = { display: "block", color: "#6a7f97", fontSize: 11, fontWeight: 800, margin: "10px 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" };
const inputStyle: CSSProperties = { width: "100%", boxSizing: "border-box", border: "1px solid rgba(127,208,255,0.14)", borderRadius: 12, padding: "10px 12px", background: "rgba(3,9,18,0.8)", color: "#ebf3ff" };
const twoColStyle: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 };
const primaryButtonStyle: CSSProperties = { marginTop: 14, width: "100%", border: "1px solid rgba(124,231,211,0.35)", borderRadius: 12, padding: "11px 13px", background: "linear-gradient(135deg, rgba(20,151,136,0.55), rgba(74,163,255,0.35))", color: "#ebf3ff", fontWeight: 900, cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8 };
const secondaryButtonStyle: CSSProperties = { ...primaryButtonStyle, background: "rgba(127,208,255,0.08)", borderColor: "rgba(127,208,255,0.18)" };
const suggestionListStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 8, marginTop: 14, maxHeight: 260, overflow: "auto" };
const suggestionStyle: CSSProperties = { display: "grid", gridTemplateColumns: "1fr auto 1fr auto", gap: 10, alignItems: "center", textAlign: "left", border: "1px solid rgba(127,208,255,0.1)", borderRadius: 12, background: "rgba(255,255,255,0.03)", padding: 10, cursor: "pointer" };
const tableStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 8 };
const rowStyle: CSSProperties = { display: "grid", gridTemplateColumns: "1fr auto 1fr auto auto", gap: 12, alignItems: "center", padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(127,208,255,0.08)" };
const monoStyle: CSSProperties = { color: "#6a7f97", fontSize: 11, fontFamily: "JetBrains Mono, monospace", wordBreak: "break-all" };
const relationBadgeStyle: CSSProperties = { padding: "5px 9px", border: "1px solid", borderRadius: 999, fontSize: 10, fontWeight: 900 };
const confidenceStyle: CSSProperties = { color: "#f2b66d", fontWeight: 900 };
const iconButtonStyle: CSSProperties = { width: 34, height: 34, borderRadius: 10, border: "1px solid rgba(255,157,175,0.18)", background: "rgba(255,157,175,0.08)", color: "#ff9daf", cursor: "pointer" };
const mutedStyle: CSSProperties = { margin: 0, color: "#6a7f97", fontSize: 13 };
const errorStyle: CSSProperties = { padding: 12, borderRadius: 14, color: "#ffb4c2", background: "rgba(255,157,175,0.1)", border: "1px solid rgba(255,157,175,0.18)" };
