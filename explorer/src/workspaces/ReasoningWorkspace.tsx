import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, Play, RotateCcw, CheckCircle2, AlertCircle, Zap, GitBranch, Info } from "lucide-react";

const SAMPLE_FACTS = `inhibits(Metformin, mTOR)
causes(mTOR, Neurodegeneration)
treats(Metformin, Diabetes)`;

const SAMPLE_RULE = `IF inhibits(Metformin, mTOR) AND causes(mTOR, Neurodegeneration) THEN candidate(Metformin, Alzheimer's)`;

const TEMPLATES = [
  {
    label: "Drug Candidate",
    facts: `inhibits(Metformin, mTOR)\ncauses(mTOR, Neurodegeneration)\ntreats(Metformin, Diabetes)`,
    rule: `IF inhibits(Metformin, mTOR) AND causes(mTOR, Neurodegeneration) THEN candidate(Metformin, Alzheimer's)`,
  },
  {
    label: "Gene → Disease",
    facts: `expressed_in(BRCA1, Breast)\nmutated_in(BRCA1, Cancer)\nassociated_with(Breast, Cancer)`,
    rule: `IF mutated_in(X, Cancer) AND expressed_in(X, Y) THEN risk_gene(X, Y)`,
  },
  {
    label: "Pathway Activation",
    facts: `activates(EGF, EGFR)\ndownstream_of(MAPK, EGFR)\ndownstream_of(AKT, EGFR)`,
    rule: `IF activates(X, EGFR) AND downstream_of(Y, EGFR) THEN activates(X, Y)`,
  },
];

export function ReasoningWorkspace() {
  const queryClient = useQueryClient();
  const [facts, setFacts] = useState(SAMPLE_FACTS);
  const [rules, setRules] = useState(SAMPLE_RULE);
  const [applyToGraph, setApplyToGraph] = useState(true);
  const [result, setResult] = useState<{
    inferred_facts?: string[];
    rules_fired?: number;
    added_edges?: number;
    mutated?: boolean;
  } | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");

  async function handleRun() {
    setIsRunning(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch("/api/reason", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          facts: facts.split(/\r?\n/).map((l) => l.trim()).filter(Boolean),
          rules: rules.split(/\r?\n/).map((l) => l.trim()).filter(Boolean),
          mode: "forward",
          apply_to_graph: applyToGraph,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Status ${response.status}`);
      setResult(data);
      if (data.mutated) queryClient.invalidateQueries({ queryKey: ["graph", "full-load"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reasoning failed");
    } finally {
      setIsRunning(false);
    }
  }

  function loadTemplate(t: (typeof TEMPLATES)[number]) {
    setFacts(t.facts);
    setRules(t.rule);
    setResult(null);
    setError("");
  }

  function handleReset() {
    setFacts(SAMPLE_FACTS);
    setRules(SAMPLE_RULE);
    setResult(null);
    setError("");
  }

  return (
    <div className="ws-page" style={{ flexDirection: "row" }}>
      {/* ── Left: Input panel ── */}
      <div style={{ width: 480, flexShrink: 0, display: "flex", flexDirection: "column", borderRight: "1px solid var(--ws-border)", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "18px 20px 14px", borderBottom: "1px solid var(--ws-border)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
            <div style={{ width: 32, height: 32, borderRadius: 10, background: "var(--ws-accent-soft)", border: "1px solid var(--ws-border-strong)", display: "grid", placeItems: "center", color: "var(--ws-accent)", flexShrink: 0 }}>
              <BrainCircuit size={16} />
            </div>
            <div>
              <div className="ws-eyebrow" style={{ marginBottom: 2 }}>Forward Chaining</div>
              <div style={{ color: "var(--ws-text)", fontWeight: 700, fontSize: 15, lineHeight: 1 }}>Inference Engine</div>
            </div>
          </div>
        </div>

        {/* Templates */}
        <div style={{ padding: "12px 16px 10px", borderBottom: "1px solid var(--ws-border)", flexShrink: 0 }}>
          <div className="ws-eyebrow" style={{ marginBottom: 8 }}>Quick Templates</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {TEMPLATES.map((t) => (
              <button key={t.label} className="ws-btn ws-btn--ghost" style={{ padding: "5px 10px", fontSize: 11 }} onClick={() => loadTemplate(t)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Input area */}
        <div className="ws-scroll ws-padded" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label className="ws-label">Facts</label>
            <div className="ws-body" style={{ marginBottom: 8 }}>One fact per line using <code style={{ color: "var(--ws-accent)", fontSize: 11 }}>predicate(subject, object)</code> form.</div>
            <textarea
              className="ws-textarea"
              value={facts}
              onChange={(e) => setFacts(e.target.value)}
              rows={6}
              spellCheck={false}
            />
          </div>

          <div>
            <label className="ws-label">Rules</label>
            <div className="ws-body" style={{ marginBottom: 8 }}>Use <code style={{ color: "var(--ws-amber)", fontSize: 11 }}>IF … AND … THEN …</code> syntax. Falls back to internal matcher if the reasoning server is unavailable.</div>
            <textarea
              className="ws-textarea"
              value={rules}
              onChange={(e) => setRules(e.target.value)}
              rows={5}
              spellCheck={false}
            />
          </div>

          {/* Apply toggle */}
          <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", padding: "10px 12px", borderRadius: "var(--ws-radius-sm)", border: "1px solid var(--ws-border)", background: applyToGraph ? "var(--ws-green-soft)" : "var(--ws-surface)" }}>
            <div style={{ position: "relative", width: 36, height: 20, flexShrink: 0 }}>
              <input
                type="checkbox"
                checked={applyToGraph}
                onChange={(e) => setApplyToGraph(e.target.checked)}
                style={{ opacity: 0, position: "absolute", inset: 0, cursor: "pointer", margin: 0 }}
              />
              <div style={{ position: "absolute", inset: 0, borderRadius: 999, background: applyToGraph ? "var(--ws-green)" : "rgba(255,255,255,0.12)", transition: "background 180ms ease" }} />
              <div style={{ position: "absolute", top: 3, left: applyToGraph ? 19 : 3, width: 14, height: 14, borderRadius: 999, background: "#fff", transition: "left 180ms ease", boxShadow: "0 1px 4px rgba(0,0,0,0.4)" }} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: applyToGraph ? "#6ee7b7" : "var(--ws-text-muted)" }}>Write inferred facts to graph</div>
              <div style={{ fontSize: 11, color: "var(--ws-text-dim)" }}>Inferred binary facts are added as edges</div>
            </div>
          </label>

          {/* Actions */}
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="ws-btn ws-btn--primary"
              onClick={handleRun}
              disabled={isRunning}
              style={{ flex: 1, justifyContent: "center" }}
            >
              {isRunning
                ? <><span className="ws-spin" style={{ display: "inline-block" }}><Zap size={15} /></span>Running…</>
                : <><Play size={14} />Run Reasoning</>}
            </button>
            <button className="ws-btn ws-btn--ghost" onClick={handleReset} title="Reset to defaults">
              <RotateCcw size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Right: Results panel ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ padding: "18px 24px 14px", borderBottom: "1px solid var(--ws-border)", flexShrink: 0, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ws-text)" }}>Inference Results</div>
          {result && !isRunning && (
            <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <span className="ws-pill ws-pill--accent">
                <Zap size={9} /> {result.rules_fired ?? 0} rules fired
              </span>
              <span className="ws-pill ws-pill--green">
                <GitBranch size={9} /> {result.added_edges ?? 0} edges added
              </span>
              {result.mutated
                ? <span className="ws-pill ws-pill--green">graph updated</span>
                : <span className="ws-pill ws-pill--mono">preview only</span>}
            </div>
          )}
        </div>

        <div className="ws-scroll ws-padded" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {error && (
            <div className="ws-animate-in" style={{ display: "flex", gap: 10, padding: "12px 14px", borderRadius: "var(--ws-radius-sm)", background: "var(--ws-red-soft)", border: "1px solid rgba(255,123,114,0.28)", color: "#fca5a5", fontSize: 13 }}>
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <div>{error}</div>
            </div>
          )}

          {isRunning && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[1,2,3,4].map((i) => <div key={i} className="ws-skeleton" style={{ height: 52 }} />)}
            </div>
          )}

          {result && !isRunning && (
            <div className="ws-animate-in">
              {(result.inferred_facts ?? []).length === 0 ? (
                <div className="ws-empty">
                  <div className="ws-empty-icon"><CheckCircle2 size={32} /></div>
                  <div className="ws-empty-title">Reasoning complete</div>
                  <div className="ws-empty-body">No new facts were inferred from the current rule set and facts.</div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {result.inferred_facts!.map((fact, i) => (
                    <div key={`${fact}-${i}`} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "12px 14px", borderRadius: "var(--ws-radius-sm)", background: "var(--ws-surface)", border: "1px solid var(--ws-border)" }}>
                      <div style={{ width: 20, height: 20, borderRadius: 6, background: "var(--ws-green-soft)", border: "1px solid rgba(76,195,138,0.28)", display: "grid", placeItems: "center", flexShrink: 0, marginTop: 1 }}>
                        <CheckCircle2 size={11} color="var(--ws-green)" />
                      </div>
                      <code style={{ fontFamily: "'JetBrains Mono','Fira Code',monospace", fontSize: 12, color: "var(--ws-text)", lineHeight: 1.6, wordBreak: "break-all" }}>{fact}</code>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {!result && !isRunning && !error && (
            <div className="ws-empty">
              <div className="ws-empty-icon"><Info size={32} /></div>
              <div className="ws-empty-title">Ready to reason</div>
              <div className="ws-empty-body">Enter facts and rules on the left, then click Run Reasoning to see inferred statements here.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
