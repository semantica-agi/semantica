import { useState, useEffect, useMemo, useRef } from "react";
import { Scale, Search, ArrowRight, Info } from "lucide-react";

type OutcomeKind = "approved" | "rejected" | "deferred" | "pending" | string;

function outcomeColor(outcome: string) {
  const o = (outcome ?? "").toLowerCase();
  if (o.includes("approv") || o.includes("accept")) return { color: "#6ee7b7", bg: "var(--ws-green-soft)", border: "rgba(76,195,138,0.3)" };
  if (o.includes("reject") || o.includes("denied") || o.includes("fail"))  return { color: "#fca5a5", bg: "var(--ws-red-soft)",   border: "rgba(255,123,114,0.3)" };
  if (o.includes("defer") || o.includes("pending") || o.includes("review")) return { color: "#fbbf24", bg: "var(--ws-amber-soft)", border: "rgba(242,182,109,0.3)" };
  return { color: "var(--ws-text-muted)", bg: "rgba(255,255,255,0.04)", border: "rgba(255,255,255,0.1)" };
}

function OutcomeBadge({ outcome }: { outcome: OutcomeKind }) {
  const c = outcomeColor(outcome);
  return (
    <span style={{ display: "inline-block", padding: "2px 8px", borderRadius: 999, fontSize: 10, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: c.color, background: c.bg, border: `1px solid ${c.border}` }}>
      {outcome || "unknown"}
    </span>
  );
}

interface ChainStep {
  id: string;
  relationship: string;
  content?: string;
  type?: string;
  [key: string]: unknown;
}

const NODE_ACCENTS = ["#4aa3ff","#4cc38a","#f2b66d","#c084fc","#ff7b72","#38bdf8","#a78bfa"];

function ChainNode({ step, index }: { step: ChainStep; index: number }) {
  const accent = NODE_ACCENTS[index % NODE_ACCENTS.length];
  return (
    <div style={{ padding: "14px 16px", borderRadius: "var(--ws-radius)", background: "var(--ws-surface)", border: `1px solid ${accent}28`, borderLeft: `3px solid ${accent}`, position: "relative" }}>
      {step.type && (
        <div style={{ fontFamily: "monospace", fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: accent, marginBottom: 5 }}>
          {step.type}
        </div>
      )}
      <div style={{ color: "var(--ws-text)", fontSize: 13, fontWeight: 600 }}>{step.content || step.id}</div>
      {step.id && step.id !== step.content && (
        <div style={{ fontFamily: "monospace", fontSize: 10, color: "var(--ws-text-dim)", marginTop: 3 }}>{step.id}</div>
      )}
    </div>
  );
}

function RelEdge({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0, padding: "2px 0" }}>
      <div style={{ width: 2, height: 10, background: "var(--ws-border)" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 999, background: "var(--ws-accent-soft)", border: "1px solid var(--ws-border-strong)", maxWidth: 260 }}>
        <ArrowRight size={10} color="var(--ws-accent)" />
        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--ws-accent)", letterSpacing: "0.06em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
      </div>
      <div style={{ width: 2, height: 10, background: "var(--ws-border)" }} />
    </div>
  );
}

function CausalFlow({ chain, loading }: { chain: ChainStep[]; loading: boolean }) {
  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {[1,2,3].map((i) => <div key={i} className="ws-skeleton" style={{ height: 68 }} />)}
    </div>
  );
  if (!chain.length) return (
    <div className="ws-empty">
      <div className="ws-empty-icon"><Info size={28} /></div>
      <div className="ws-empty-title">No chain steps</div>
      <div className="ws-empty-body">No causal chain steps were found for this decision.</div>
    </div>
  );
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {chain.map((step, i) => (
        <div key={`${step.id}-${i}`}>
          <ChainNode step={step} index={i} />
          {i < chain.length - 1 && <RelEdge label={chain[i + 1]?.relationship || "→"} />}
        </div>
      ))}
    </div>
  );
}

export function DecisionWorkspace() {
  const [decisions, setDecisions] = useState<{ decision_id: string; category?: string; outcome?: string }[]>([]);
  const [selected, setSelected] = useState<{ decision_id: string; category?: string; outcome?: string } | null>(null);
  const [chain, setChain] = useState<ChainStep[]>([]);
  const [chainLoading, setChainLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [filter, setFilter] = useState("");

  // Tracks the active chain request so stale responses from rapid selections are ignored.
  const chainCtrlRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setListLoading(true);
    fetch("/api/decisions", { signal: ctrl.signal })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((data) => {
        setDecisions(data);
        if (data.length > 0) void loadChain(data[0]);
      })
      .catch((e) => { if (e?.name !== "AbortError") console.error(e); })
      .finally(() => setListLoading(false));
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cancel any in-flight chain request when the workspace unmounts.
  useEffect(() => () => { chainCtrlRef.current?.abort(); }, []);

  async function loadChain(d: { decision_id: string; category?: string; outcome?: string }) {
    chainCtrlRef.current?.abort();
    const ctrl = new AbortController();
    chainCtrlRef.current = ctrl;

    setSelected(d);
    setChainLoading(true);
    setChain([]);
    try {
      const res = await fetch(`/api/decisions/${encodeURIComponent(d.decision_id)}/chain`, { signal: ctrl.signal });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      if (!ctrl.signal.aborted) setChain(data.chain || []);
    } catch (e) {
      if (e instanceof Error && e.name !== "AbortError") console.error(e);
    } finally {
      if (!ctrl.signal.aborted) setChainLoading(false);
    }
  }

  const filtered = useMemo(() => {
    const q = filter.toLowerCase().trim();
    if (!q) return decisions;
    return decisions.filter((d) =>
      d.decision_id.toLowerCase().includes(q) ||
      (d.category ?? "").toLowerCase().includes(q) ||
      (d.outcome ?? "").toLowerCase().includes(q)
    );
  }, [decisions, filter]);

  return (
    <div className="ws-page" style={{ flexDirection: "row" }}>
      {/* ── Sidebar list ── */}
      <div className="ws-sidebar" style={{ width: 290 }}>
        <div className="ws-sidebar-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <div style={{ width: 30, height: 30, borderRadius: 9, background: "var(--ws-accent-soft)", border: "1px solid var(--ws-border-strong)", display: "grid", placeItems: "center", color: "var(--ws-accent)", flexShrink: 0 }}>
              <Scale size={15} />
            </div>
            <div style={{ color: "var(--ws-text)", fontSize: 14, fontWeight: 700 }}>Decisions</div>
            {decisions.length > 0 && !listLoading && (
              <span className="ws-pill ws-pill--mono" style={{ marginLeft: "auto" }}>{decisions.length}</span>
            )}
          </div>
          <div style={{ position: "relative" }}>
            <Search size={12} color="var(--ws-text-dim)" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} />
            <input
              className="ws-input"
              type="text"
              placeholder="Filter by ID, category, outcome…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              style={{ paddingLeft: 30, fontSize: 12 }}
            />
          </div>
        </div>

        <div className="ws-sidebar-body">
          {listLoading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {[1,2,3,4,5].map((i) => <div key={i} className="ws-skeleton" style={{ height: 58 }} />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="ws-empty" style={{ padding: "28px 12px" }}>
              <div className="ws-empty-title">{decisions.length === 0 ? "No decisions" : "No matches"}</div>
              <div className="ws-empty-body">{decisions.length === 0 ? "No decisions available in the graph." : "Adjust your filter."}</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {filtered.map((d) => {
                const active = selected?.decision_id === d.decision_id;
                return (
                  <button
                    key={d.decision_id}
                    className={`ws-list-item${active ? " ws-list-item--active" : ""}`}
                    onClick={() => void loadChain(d)}
                  >
                    <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 5, color: active ? "#e8f6ff" : "var(--ws-text)" }}>
                      {d.decision_id}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
                      {d.category && <span style={{ fontSize: 10, color: "var(--ws-text-dim)" }}>{d.category}</span>}
                      {d.outcome && <OutcomeBadge outcome={d.outcome} />}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Detail pane ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 60% 40% at 70% 20%, rgba(74,163,255,0.04), transparent 55%)", pointerEvents: "none" }} />

        {selected ? (
          <div className="ws-scroll ws-padded ws-animate-in" style={{ position: "relative", zIndex: 1 }}>
            {/* Decision header */}
            <div style={{ marginBottom: 28 }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
                <div>
                  <div className="ws-eyebrow" style={{ marginBottom: 6 }}>Decision Record</div>
                  <h2 className="ws-title">{selected.decision_id}</h2>
                </div>
                {selected.outcome && <OutcomeBadge outcome={selected.outcome} />}
              </div>
              {selected.category && (
                <span className="ws-pill ws-pill--mono">{selected.category}</span>
              )}
            </div>

            {/* Chain section */}
            <div className="ws-card" style={{ padding: 22 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
                <div style={{ width: 8, height: 8, borderRadius: 999, background: "linear-gradient(135deg, var(--ws-accent), var(--ws-amber))", boxShadow: "0 0 10px rgba(74,163,255,0.4)" }} />
                <div style={{ color: "var(--ws-text)", fontSize: 14, fontWeight: 700 }}>Causal Chain</div>
                {chain.length > 0 && !chainLoading && (
                  <span className="ws-pill ws-pill--accent" style={{ marginLeft: "auto" }}>{chain.length} step{chain.length !== 1 ? "s" : ""}</span>
                )}
              </div>
              <CausalFlow chain={chain} loading={chainLoading} />
            </div>
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", position: "relative", zIndex: 1 }}>
            <div className="ws-empty">
              <div className="ws-empty-icon"><Scale size={32} /></div>
              <div className="ws-empty-title">No decision selected</div>
              <div className="ws-empty-body">Select a decision from the list to inspect its causal chain and metadata.</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
