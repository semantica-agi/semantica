import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, Download, FileJson, FileText, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { logEvent } from "../../store/registryStore";

interface Toast { id: number; type: "success" | "error"; text: string }

export function ImportExportWorkspace() {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [exportFormat, setExportFormat] = useState<"json" | "csv">("json");
  const [isExporting, setIsExporting] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  function showToast(type: Toast["type"], text: string) {
    const id = Date.now();
    setToasts((p) => [...p, { id, type, text }]);
    setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), 5000);
  }

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/json": [".json"], "text/csv": [".csv"] },
    maxFiles: 1,
  });

  async function handleImport() {
    if (!file) return;
    setIsUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/import", { method: "POST", body: fd });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Import failed"); }
      const data = await res.json();
      showToast("success", `Imported ${data.nodes_imported} nodes · ${data.edges_imported} edges`);
      logEvent("import", `Imported ${data.nodes_imported} nodes · ${data.edges_imported} edges from ${file.name}`, { file: file.name });
      setFile(null);
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Import failed");
    } finally { setIsUploading(false); }
  }

  async function handleExport() {
    setIsExporting(true);
    try {
      const res = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format: exportFormat }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Export failed"); }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `semantica_export.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("success", `Export ready — semantica_export.${exportFormat}`);
      logEvent("export", `Exported graph as ${exportFormat.toUpperCase()}`, { format: exportFormat });
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Export failed");
    } finally { setIsExporting(false); }
  }

  return (
    <div className="ws-page ws-scroll">
      <div className="ws-padded" style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 980, margin: "0 auto", width: "100%" }}>
        {/* Page header */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 42, height: 42, borderRadius: 13, background: "var(--ws-accent-soft)", border: "1px solid var(--ws-border-strong)", display: "grid", placeItems: "center", color: "var(--ws-accent)", flexShrink: 0 }}>
            <UploadCloud size={20} />
          </div>
          <div>
            <h2 className="ws-title" style={{ fontSize: 18 }}>Import &amp; Export</h2>
            <div className="ws-body" style={{ marginTop: 2 }}>Ingest new graph datasets or extract the current knowledge base.</div>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
          {/* ── Import card ── */}
          <div className="ws-card" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <UploadCloud size={16} color="var(--ws-accent)" />
              <div style={{ color: "var(--ws-text)", fontWeight: 700, fontSize: 14 }}>Import Entities &amp; Relations</div>
            </div>

            {/* Dropzone */}
            <div
              {...getRootProps()}
              style={{
                border: `2px dashed ${isDragActive ? "var(--ws-accent)" : "var(--ws-border)"}`,
                borderRadius: "var(--ws-radius)",
                background: isDragActive ? "var(--ws-accent-soft)" : "rgba(0,0,0,0.18)",
                padding: 32,
                textAlign: "center",
                cursor: "pointer",
                transition: "all 200ms ease",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 10,
              }}
            >
              <input {...getInputProps()} />
              {file ? (
                <>
                  {file.name.endsWith(".json") ? <FileJson size={40} color="#4cc38a" /> : <FileText size={40} color="#4cc38a" />}
                  <div style={{ color: "var(--ws-text)", fontWeight: 700 }}>{file.name}</div>
                  <div className="ws-body" style={{ fontSize: 11 }}>{(file.size / 1024).toFixed(1)} KB — click to replace</div>
                </>
              ) : (
                <>
                  <UploadCloud size={36} color="var(--ws-accent)" style={{ opacity: 0.7 }} />
                  <div style={{ color: "var(--ws-text)", fontWeight: 600 }}>Drag &amp; drop or click to browse</div>
                  <div className="ws-pill ws-pill--mono">.json</div>
                  <span style={{ color: "var(--ws-text-dim)", fontSize: 11 }}>or</span>
                  <div className="ws-pill ws-pill--mono">.csv</div>
                </>
              )}
            </div>

            <button
              className="ws-btn ws-btn--primary"
              onClick={handleImport}
              disabled={!file || isUploading}
              style={{ width: "100%", justifyContent: "center" }}
            >
              {isUploading ? <><Loader2 size={15} className="ws-spin" />Uploading…</> : <><UploadCloud size={15} />Upload to Graph</>}
            </button>
          </div>

          {/* ── Export card ── */}
          <div className="ws-card" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Download size={16} color="var(--ws-purple)" />
              <div style={{ color: "var(--ws-text)", fontWeight: 700, fontSize: 14 }}>Export Graph Snapshot</div>
            </div>

            <div>
              <label className="ws-label">Format</label>
              <div style={{ display: "flex", gap: 8 }}>
                {(["json", "csv"] as const).map((fmt) => (
                  <button
                    key={fmt}
                    className={`ws-btn ${exportFormat === fmt ? "ws-btn--primary" : "ws-btn--ghost"}`}
                    style={{ flex: 1, justifyContent: "center", textTransform: "uppercase", fontSize: 12 }}
                    onClick={() => setExportFormat(fmt)}
                  >
                    {fmt === "json" ? <FileJson size={14} /> : <FileText size={14} />}
                    {fmt}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ flex: 1, padding: "14px 16px", borderRadius: "var(--ws-radius-sm)", background: "rgba(0,0,0,0.22)", border: "1px solid var(--ws-border)" }}>
              <div style={{ color: "var(--ws-text-muted)", fontWeight: 700, fontSize: 12, marginBottom: 6 }}>What's included</div>
              <div className="ws-body" style={{ fontSize: 12 }}>
                {exportFormat === "json"
                  ? "Full graph snapshot: all node properties, edge weights, entity metadata and semantic groups in a standardized JSON payload."
                  : "Flattened CSV: nodes and edges as rows. Complex nested properties are stringified. Best for spreadsheet analysis."}
              </div>
            </div>

            <button
              className="ws-btn"
              onClick={handleExport}
              disabled={isExporting}
              style={{ width: "100%", justifyContent: "center", background: "var(--ws-purple-soft)", borderColor: "rgba(192,132,252,0.3)", color: "#d8b4fe" }}
            >
              {isExporting ? <><Loader2 size={15} className="ws-spin" />Preparing…</> : <><Download size={15} />Download Export</>}
            </button>
          </div>
        </div>
      </div>

      {/* Toasts */}
      <div style={{ position: "fixed", bottom: 28, right: 28, display: "flex", flexDirection: "column", gap: 10, zIndex: 1000 }}>
        {toasts.map((t) => (
          <div key={t.id} className="ws-animate-in" style={{ display: "flex", alignItems: "center", gap: 10, padding: "13px 18px", borderRadius: "var(--ws-radius-sm)", background: t.type === "success" ? "rgba(16,36,22,0.96)" : "rgba(40,10,10,0.96)", border: `1px solid ${t.type === "success" ? "rgba(76,195,138,0.4)" : "rgba(255,123,114,0.4)"}`, boxShadow: "0 8px 24px rgba(0,0,0,0.5)", backdropFilter: "blur(12px)" }}>
            {t.type === "success" ? <CheckCircle2 size={16} color="#4cc38a" /> : <AlertCircle size={16} color="#ff7b72" />}
            <span style={{ color: "var(--ws-text)", fontSize: 13, fontWeight: 500 }}>{t.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
