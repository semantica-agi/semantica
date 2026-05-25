import { useState, useRef } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";
import { Play, Copy, Download, Table2, AlertCircle, FileCode2 } from "lucide-react";

const TEMPLATES: { label: string; query: string }[] = [
  { label: "All triples", query: "SELECT ?s ?p ?o\nWHERE {\n  ?s ?p ?o\n}\nLIMIT 20" },
  { label: "Node types", query: "SELECT ?type (COUNT(?s) AS ?count)\nWHERE {\n  ?s a ?type\n}\nGROUP BY ?type\nORDER BY DESC(?count)" },
  { label: "Outgoing edges", query: "SELECT ?predicate ?object\nWHERE {\n  <urn:node:example> ?predicate ?object\n}\nLIMIT 50" },
  { label: "Path between", query: "SELECT ?mid ?p1 ?p2\nWHERE {\n  <urn:node:a> ?p1 ?mid .\n  ?mid ?p2 <urn:node:b>\n}\nLIMIT 20" },
];

export function SparqlWorkspace() {
  const monaco = useMonaco();
  const editorRef = useRef<unknown>(null);
  const [query, setQuery] = useState(TEMPLATES[0].query);
  const [result, setResult] = useState<{ columns?: string[]; rows?: Record<string, string>[]; error?: string; error_line?: number } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copyState, setCopyState] = useState(false);

  function handleEditorWillMount(monacoIns: { languages: { getLanguages(): { id: string }[]; register(opts: { id: string }): void; setMonarchTokensProvider(id: string, p: unknown): void }; editor: { defineTheme(id: string, t: unknown): void } }) {
    if (!monacoIns.languages.getLanguages().some((l) => l.id === "sparql")) {
      monacoIns.languages.register({ id: "sparql" });
      monacoIns.languages.setMonarchTokensProvider("sparql", {
        keywords: ["SELECT", "WHERE", "LIMIT", "FILTER", "OPTIONAL", "PREFIX", "ORDER", "BY", "DESC", "ASC", "GROUP", "DISTINCT", "CONSTRUCT", "ASK", "DESCRIBE"],
        tokenizer: {
          root: [
            [/[a-zA-Z_]\w*/, { cases: { "@keywords": "keyword", "@default": "identifier" } }],
            [/[?$][a-zA-Z_]\w*/, "variable.name"],
            [/<[^>]+>/, "string.uri"],
            [/"[^"]*"/, "string"],
            [/#.*/, "comment"],
            [/[0-9]+(\.[0-9]+)?/, "number"],
          ],
        },
      });
      monacoIns.editor.defineTheme("sparql-dark", {
        base: "vs-dark",
        inherit: true,
        rules: [
          { token: "keyword", foreground: "58a6ff", fontStyle: "bold" },
          { token: "variable.name", foreground: "a5d6ff" },
          { token: "string.uri", foreground: "7ee787" },
          { token: "string", foreground: "a5d6ff" },
          { token: "comment", foreground: "4a6a85", fontStyle: "italic" },
          { token: "number", foreground: "f2b66d" },
        ],
        colors: {
          "editor.background": "#050c18",
          "editor.lineHighlightBackground": "#0a1628",
          "editorLineNumber.foreground": "#2a4060",
          "editorCursor.foreground": "#4aa3ff",
          "editor.selectionBackground": "#1e3a5a",
        },
      });
    }
  }

  function handleEditorDidMount(editor: unknown) {
    editorRef.current = editor;
  }

  async function handleRun() {
    setIsLoading(true);
    setResult(null);
    if (monaco && editorRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (monaco as any).editor.setModelMarkers((editorRef.current as any).getModel(), "sparql", []);
    }
    try {
      const res = await fetch("/api/sparql", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      if (data.error && data.error_line && monaco && editorRef.current) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (monaco as any).editor.setModelMarkers((editorRef.current as any).getModel(), "sparql", [{
          startLineNumber: data.error_line,
          startColumn: data.error_column || 1,
          endLineNumber: data.error_line,
          endColumn: 100,
          message: data.error,
          severity: (monaco as any).MarkerSeverity.Error,
        }]);
      }
      setResult(data);
    } catch {
      setResult({ error: "Network error — could not reach the SPARQL endpoint." });
    } finally {
      setIsLoading(false);
    }
  }

  function handleCopyQuery() {
    navigator.clipboard.writeText(query).then(() => {
      setCopyState(true);
      setTimeout(() => setCopyState(false), 1500);
    }).catch(() => {
      // Clipboard API unavailable (insecure context or denied) — no-op; query is visible in editor
    });
  }

  function handleExportCSV() {
    if (!result?.rows || !result?.columns) return;
    const cols = result.columns;
    const header = cols.join(",");
    const rows = result.rows.map((r) => cols.map((c) => JSON.stringify(r[c] ?? "")).join(",")).join("\n");
    const blob = new Blob([`${header}\n${rows}`], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sparql_results.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="ws-page">
      <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
        {/* ── Toolbar ── */}
        <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--ws-border)", display: "flex", alignItems: "center", gap: 8, flexShrink: 0, background: "rgba(0,0,0,0.18)" }}>
          <div style={{ display: "flex", gap: 6, flex: 1, flexWrap: "wrap" }}>
            <span className="ws-eyebrow" style={{ alignSelf: "center", marginRight: 4 }}>Templates:</span>
            {TEMPLATES.map((t) => (
              <button
                key={t.label}
                className="ws-btn ws-btn--ghost"
                style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => { setQuery(t.query); setResult(null); }}
              >
                {t.label}
              </button>
            ))}
          </div>
          <button className="ws-btn ws-btn--ghost" style={{ padding: "6px 10px" }} onClick={handleCopyQuery} title="Copy query">
            <Copy size={13} />{copyState ? "Copied!" : "Copy"}
          </button>
          <button
            className="ws-btn ws-btn--primary"
            onClick={handleRun}
            disabled={isLoading}
            style={{ minWidth: 110, justifyContent: "center" }}
          >
            {isLoading
              ? <><span className="ws-spin" style={{ display: "inline-block" }}><Play size={13} /></span>Running…</>
              : <><Play size={13} />Run Query</>}
          </button>
        </div>

        {/* ── Editor + Results split ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Editor */}
          <div style={{ flex: "0 0 55%", minHeight: 0, borderBottom: "1px solid var(--ws-border)", position: "relative" }}>
            <div style={{ position: "absolute", top: 8, right: 12, zIndex: 10, display: "flex", alignItems: "center", gap: 6 }}>
              <span className="ws-pill ws-pill--mono"><FileCode2 size={9} />SPARQL</span>
            </div>
            <Editor
              height="100%"
              defaultLanguage="sparql"
              theme="sparql-dark"
              value={query}
              onChange={(v) => setQuery(v || "")}
              beforeMount={handleEditorWillMount}
              onMount={handleEditorDidMount}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: "'JetBrains Mono','Fira Code',Consolas,monospace",
                lineHeight: 22,
                padding: { top: 16 },
                scrollBeyondLastLine: false,
                renderLineHighlight: "gutter",
                wordWrap: "on",
              }}
            />
          </div>

          {/* Results */}
          <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden", background: "rgba(0,0,0,0.12)" }}>
            <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--ws-border)", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--ws-text-muted)", fontSize: 13, fontWeight: 700 }}>
                <Table2 size={14} />
                Results
                {result?.rows && <span className="ws-pill ws-pill--accent">{result.rows.length} rows</span>}
              </div>
              {result?.rows && result.rows.length > 0 && (
                <button className="ws-btn ws-btn--ghost" style={{ marginLeft: "auto", padding: "4px 10px", fontSize: 11 }} onClick={handleExportCSV}>
                  <Download size={12} />Export CSV
                </button>
              )}
            </div>

            <div className="ws-scroll" style={{ flex: 1 }}>
              {isLoading && (
                <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 8 }}>
                  {[1, 2, 3].map((i) => <div key={i} className="ws-skeleton" style={{ height: 36 }} />)}
                </div>
              )}

              {result?.error && !isLoading && (
                <div className="ws-animate-in" style={{ margin: 16, display: "flex", gap: 10, padding: "12px 14px", borderRadius: "var(--ws-radius-sm)", background: "var(--ws-red-soft)", border: "1px solid rgba(255,123,114,0.28)", color: "#fca5a5", fontSize: 13 }}>
                  <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
                  {result.error}
                </div>
              )}

              {result?.rows && result?.columns && !isLoading && (
                <div className="ws-animate-in" style={{ overflowX: "auto" }}>
                  {result.rows.length === 0 ? (
                    <div className="ws-empty">
                      <div className="ws-empty-title">No results</div>
                      <div className="ws-empty-body">The query returned 0 rows. Try a broader query or check your data.</div>
                    </div>
                  ) : (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, color: "var(--ws-text)" }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--ws-border)", background: "rgba(0,0,0,0.2)" }}>
                          <th style={{ padding: "8px 14px", textAlign: "left", color: "var(--ws-text-dim)", fontFamily: "monospace", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", width: 40 }}>#</th>
                          {result.columns.map((c) => (
                            <th key={c} style={{ padding: "8px 14px", textAlign: "left", color: "var(--ws-text-muted)", fontFamily: "monospace", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em" }}>?{c}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.rows.map((r, i) => (
                          <tr key={i} style={{ borderBottom: "1px solid rgba(74,163,255,0.06)" }}>
                            <td style={{ padding: "7px 14px", color: "var(--ws-text-dim)", fontFamily: "monospace", fontSize: 11 }}>{i + 1}</td>
                            {(result.columns ?? []).map((c) => (
                              <td key={c} style={{ padding: "7px 14px", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "monospace" }} title={String(r[c] ?? "")}>
                                {r[c] != null ? (
                                  String(r[c]).startsWith("urn:") || String(r[c]).startsWith("http")
                                    ? <span style={{ color: "#7ee787" }}>{String(r[c])}</span>
                                    : String(r[c])
                                ) : <span style={{ color: "var(--ws-text-dim)", fontStyle: "italic" }}>null</span>}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {!result && !isLoading && (
                <div className="ws-empty">
                  <div className="ws-empty-icon"><Table2 size={28} /></div>
                  <div className="ws-empty-title">Run a query</div>
                  <div className="ws-empty-body">Write SPARQL above or pick a template, then click Run Query to see results here.</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
