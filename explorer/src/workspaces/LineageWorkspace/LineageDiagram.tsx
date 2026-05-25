/**
 * src/workspaces/LineageWorkspace/LineageDiagram.tsx
 */
import { useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const THEME_CSS = `
  .react-flow { background: var(--ws-bg, #060d1a); }
  .react-flow__node-group {
    background: rgba(74,163,255,0.04);
    border: 1px dashed rgba(74,163,255,0.18);
    border-radius: 10px;
  }
  .react-flow__node-default {
    background: rgba(6,13,26,0.92);
    color: var(--ws-text, #ddeeff);
    border: 1px solid rgba(74,163,255,0.22);
    border-radius: 8px;
    padding: 10px 12px;
    white-space: pre-wrap;
    font-size: 12px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }
  .react-flow__controls { background: rgba(6,13,26,0.9); border: 1px solid rgba(74,163,255,0.18); border-radius: 10px; }
  .react-flow__controls-button { background: transparent; border-color: rgba(74,163,255,0.15); color: var(--ws-text-muted, #5a7a9a); }
  .react-flow__controls-button:hover { background: rgba(74,163,255,0.1); color: var(--ws-text, #ddeeff); }
`;

export function LineageDiagram() {
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [searchId, setSearchId] = useState("");
  const [activeId, setActiveId] = useState("");

  const downloadReport = async (format: "json" | "markdown") => {
    if (!activeId) return;
    const response = await fetch(`/api/provenance/report?node_id=${encodeURIComponent(activeId)}&format=${format}`);
    if (!response.ok) {
      return;
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${activeId}_provenance.${format === "markdown" ? "md" : "json"}`;
    document.body.appendChild(anchor);
    anchor.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(anchor);
  };

  useEffect(() => {
    if (!activeId) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const xLanes = [
      { id: "group_agent", type: "group", position: { x: 50, y: 50 }, style: { width: 800, height: 120 } },
      { id: "group_activity", type: "group", position: { x: 50, y: 200 }, style: { width: 800, height: 120 } },
      { id: "group_entity", type: "group", position: { x: 50, y: 350 }, style: { width: 800, height: 120 } }
    ];

    const fetchLineage = async () => {
      try {
        const res = await fetch("/api/provenance?node_id=" + encodeURIComponent(activeId));

        if (!res.ok) {
          const text = await res.text();
          console.error(`HTTP ${res.status}: API Route missing or failed.`, text.substring(0, 100));
          return;
        }

        const contentType = res.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          console.error("Backend returned non-JSON response (likely an HTML fallback). Check FastAPI routing.");
          return;
        }

        const data = await res.json();

        const counters: Record<string, number> = { "group_agent": 0, "group_activity": 0, "group_entity": 0 };

        const mappedNodes = data.nodes.map((n: any) => {
          const c = counters[n.parent_id] || 0;
          counters[n.parent_id] = c + 1;
          return {
            id: n.id,
            data: { label: n.label + "\\n(" + n.prov_type + ")" },
            position: { x: 50 + c * 180, y: 30 },
            parentId: n.parent_id,
            extent: "parent",
            type: "default"
          };
        });

        const mappedEdges = data.edges.map((e: any) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          animated: true,
          style: { stroke: "#58a6ff" }
        }));

        setNodes([...xLanes, ...mappedNodes]);
        setEdges(mappedEdges);
      } catch (err) {
        console.error(err);
      }
    };
    fetchLineage();
  }, [activeId]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative", background: "var(--ws-bg, #060d1a)" }}>
      <style>{THEME_CSS}</style>

      {/* Toolbar */}
      <div style={{ position: "absolute", top: 14, left: 14, right: 14, zIndex: 10, display: "flex", gap: 8, alignItems: "center", background: "rgba(4,10,18,0.88)", backdropFilter: "blur(14px)", padding: "8px 12px", borderRadius: 12, border: "1px solid rgba(74,163,255,0.16)", boxShadow: "0 4px 20px rgba(0,0,0,0.4)" }}>
        <span className="ws-eyebrow" style={{ color: "var(--ws-accent, #4aa3ff)", marginRight: 4 }}>PROV-O Lineage</span>
        <input
          className="ws-input"
          type="text"
          placeholder="Enter Node ID…"
          value={searchId}
          onChange={(e) => setSearchId(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") setActiveId(searchId); }}
          style={{ width: 200, padding: "6px 10px", fontSize: 12 }}
        />
        <button className="ws-btn ws-btn--primary" style={{ padding: "6px 12px" }} onClick={() => setActiveId(searchId)}>
          Trace
        </button>
        <div style={{ flex: 1 }} />
        <button className="ws-btn ws-btn--ghost" style={{ padding: "6px 12px", fontSize: 11 }} disabled={!activeId} onClick={() => void downloadReport("json")}>
          Export JSON
        </button>
        <button className="ws-btn ws-btn--ghost" style={{ padding: "6px 12px", fontSize: 11 }} disabled={!activeId} onClick={() => void downloadReport("markdown")}>
          Export MD
        </button>
      </div>

      {activeId ? (
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background color="rgba(74,163,255,0.08)" gap={24} />
          <Controls />
        </ReactFlow>
      ) : (
        <div className="ws-empty" style={{ height: "100%", paddingTop: 72 }}>
          <div className="ws-empty-icon"><Link2 size={36} color="var(--ws-accent)" /></div>
          <div className="ws-empty-title">PROV-O Lineage Viewer</div>
          <div className="ws-empty-body">Enter a Node ID in the toolbar above and click Trace to view its W3C PROV-O lineage diagram.</div>
        </div>
      )}
    </div>
  );
}
