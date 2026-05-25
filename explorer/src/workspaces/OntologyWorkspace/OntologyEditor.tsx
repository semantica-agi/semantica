import { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import type { Connection, Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Plus,
  GitBranch,
  User,
  Shield,
  FileText,
  Layout,
  Send,
  Pencil,
  Trash2,
} from "lucide-react";

type OntologyNodeData = {
  label?: string;
  type?: string;
};

type OntologyNode = Node<OntologyNodeData>;
type OntologyEdge = Edge<Record<string, unknown>>;

const nodeTypes = {
  classNode: ({ data }: { data: OntologyNodeData }) => (
    <div style={classNodeStyle}>
      <div style={classNodeHeader}>{data.label}</div>
      <div style={classNodeSub}>{data.type}</div>
    </div>
  ),
};

const classNodeStyle: React.CSSProperties = {
  padding: "12px 16px",
  borderRadius: "8px",
  background: "linear-gradient(135deg, rgba(74, 163, 255, 0.15), rgba(74, 163, 255, 0.05))",
  border: "1px solid rgba(127, 208, 255, 0.3)",
  color: "#ebf3ff",
  fontSize: "13px",
  fontWeight: "600",
  minWidth: "140px",
  textAlign: "center",
  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.2)",
};

const classNodeHeader: React.CSSProperties = {
  fontSize: "14px",
  fontWeight: "700",
  marginBottom: "4px",
};

const classNodeSub: React.CSSProperties = {
  fontSize: "11px",
  color: "#8fa8c6",
  fontWeight: "500",
};

interface DraftDiff {
  added_classes: string[];
  removed_classes: string[];
  modified_classes: Record<string, Record<string, any>>;
  added_properties: string[];
  removed_properties: string[];
  modified_properties: Record<string, Record<string, any>>;
  added_restrictions: Record<string, any>[];
  removed_restrictions: Record<string, any>[];
  added_axioms: Record<string, any>[];
  removed_axioms: Record<string, any>[];
  annotation_changes: Record<string, Record<string, any>>;
}

interface RegistryEntry {
  uri: string;
  name: string;
}

export function OntologyEditor() {
  const [nodes, setNodes, onNodesChange] = useNodesState<OntologyNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<OntologyEdge>([]);
  const [selectedElement, setSelectedElement] = useState<OntologyNode | OntologyEdge | null>(null);
  const [registry, setRegistry] = useState<RegistryEntry[]>([]);
  const [ontologyUri, setOntologyUri] = useState<string>("");
  const [draftDiff, setDraftDiff] = useState<DraftDiff>({
    added_classes: [],
    removed_classes: [],
    modified_classes: {},
    added_properties: [],
    removed_properties: [],
    modified_properties: {},
    added_restrictions: [],
    removed_restrictions: [],
    added_axioms: [],
    removed_axioms: [],
    annotation_changes: {},
  });
  const [isSaving, setIsSaving] = useState(false);
  const [showContext, setShowContext] = useState<{ x: number; y: number; type: string; element: OntologyNode | OntologyEdge } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/ontology/registry")
      .then((response) => (response.ok ? response.json() : []))
      .then((entries: RegistryEntry[]) => {
        if (cancelled) return;
        setRegistry(entries);
        setOntologyUri((current) => current || entries[0]?.uri || "");
      })
      .catch((error) => {
        console.error("Failed to load ontology registry:", error);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, markerEnd: { type: MarkerType.ArrowClosed } }, eds)),
    [setEdges]
  );

  const addClass = useCallback(() => {
    const newId = `class_${Date.now()}`;
    const newNode: OntologyNode = {
      id: newId,
      type: "classNode",
      position: { x: Math.random() * 400, y: Math.random() * 300 },
      data: { label: "NewClass", type: "owl:Class" },
    };
    setNodes((nds) => [...nds, newNode]);
    setDraftDiff((prev) => ({
      ...prev,
      added_classes: [...prev.added_classes, newId],
    }));
  }, [setNodes]);

  const addProperty = useCallback(() => {
    if (nodes.length < 2) {
      alert("Add at least two classes before creating a property edge.");
      return;
    }
    const newId = `prop_${Date.now()}`;
    const newEdge: OntologyEdge = {
      id: newId,
      source: nodes[0].id,
      target: nodes[1].id,
      label: "hasProperty",
      type: "smoothstep",
      animated: true,
    };
    setEdges((eds) => [...eds, newEdge]);
    setDraftDiff((prev) => ({
      ...prev,
      added_properties: [...prev.added_properties, newId],
    }));
  }, [nodes, setEdges]);

  const addIndividual = useCallback(() => {
    const newId = `ind_${Date.now()}`;
    const newNode: OntologyNode = {
      id: newId,
      type: "classNode",
      position: { x: Math.random() * 400, y: Math.random() * 300 },
      data: { label: "NewIndividual", type: "owl:NamedIndividual" },
    };
    setNodes((nds) => [...nds, newNode]);
  }, [setNodes]);

  const addRestriction = useCallback(() => {
    setDraftDiff((prev) => ({
      ...prev,
      added_restrictions: [...prev.added_restrictions, { type: "someValuesFrom", value: "" }],
    }));
  }, []);

  const addAxiom = useCallback(() => {
    setDraftDiff((prev) => ({
      ...prev,
      added_axioms: [...prev.added_axioms, { type: "subClassOf", value: "" }],
    }));
  }, []);

  const autoLayout = useCallback(() => {
    const layoutNodes = nodes.map((node, index) => ({
      ...node,
      position: { x: (index % 4) * 200, y: Math.floor(index / 4) * 150 },
    }));
    setNodes(layoutNodes);
  }, [nodes, setNodes]);

  const saveDraft = useCallback(async () => {
    if (!ontologyUri) {
      alert("Please select an ontology first");
      return;
    }
    setIsSaving(true);
    try {
      const response = await fetch("/api/ontology/draft", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ontology_uri: ontologyUri,
          diff: draftDiff,
          author: "user",
          summary: "Visual editor changes",
        }),
      });
      if (response.ok) {
        const data = await response.json();
        alert(`Draft saved: ${data.draft_id}`);
      }
    } catch (error) {
      console.error("Failed to save draft:", error);
      alert("Failed to save draft");
    } finally {
      setIsSaving(false);
    }
  }, [ontologyUri, draftDiff]);

  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: OntologyNode) => {
    event.preventDefault();
    setSelectedElement(node);
    setShowContext({ x: event.clientX, y: event.clientY, type: "node", element: node });
  }, []);

  const handleEdgeContextMenu = useCallback((event: React.MouseEvent, edge: OntologyEdge) => {
    event.preventDefault();
    setSelectedElement(edge);
    setShowContext({ x: event.clientX, y: event.clientY, type: "edge", element: edge });
  }, []);

  const deleteSelected = useCallback(() => {
    const target = showContext?.element ?? selectedElement;
    if (target) {
      if ("source" in target) {
        setEdges((eds) => eds.filter((e) => e.id !== target.id));
        setDraftDiff((prev) => ({
          ...prev,
          removed_properties: [...prev.removed_properties, target.id],
        }));
      } else {
        setNodes((nds) => nds.filter((n) => n.id !== target.id));
        setDraftDiff((prev) => ({
          ...prev,
          removed_classes: [...prev.removed_classes, target.id],
        }));
      }
      setSelectedElement(null);
    }
    setShowContext(null);
  }, [selectedElement, setNodes, setEdges, showContext]);

  const renameSelected = useCallback(() => {
    const target = showContext?.element ?? selectedElement;
    if (target && !("source" in target)) {
      const newLabel = prompt("Enter new name:", String(target.data.label ?? ""));
      if (newLabel) {
        setNodes((nds) =>
          nds.map((n) => (n.id === target.id ? { ...n, data: { ...n.data, label: newLabel } } : n))
        );
        setDraftDiff((prev) => ({
          ...prev,
          modified_classes: { ...prev.modified_classes, [target.id]: { label: newLabel } },
        }));
      }
    }
    setShowContext(null);
  }, [selectedElement, setNodes, showContext]);

  useEffect(() => {
    const handleClick = () => setShowContext(null);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  const toolbarStyle: React.CSSProperties = {
    display: "flex",
    gap: "8px",
    padding: "12px 16px",
    background: "rgba(3, 9, 18, 0.92)",
    borderBottom: "1px solid rgba(140, 192, 255, 0.12)",
    flexWrap: "wrap",
  };

  const toolbarButtonStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    padding: "8px 12px",
    borderRadius: "8px",
    border: "1px solid rgba(127, 208, 255, 0.18)",
    background: "rgba(74, 163, 255, 0.08)",
    color: "#ebf3ff",
    fontSize: "12px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "160ms ease",
  };

  const selectStyle: React.CSSProperties = {
    padding: "8px 12px",
    borderRadius: "8px",
    border: "1px solid rgba(127, 208, 255, 0.18)",
    background: "rgba(3, 9, 18, 0.88)",
    color: "#ebf3ff",
    fontSize: "12px",
    minWidth: "260px",
  };

  const contextMenuStyle: React.CSSProperties = {
    position: "fixed",
    background: "rgba(9, 19, 34, 0.95)",
    border: "1px solid rgba(127, 208, 255, 0.3)",
    borderRadius: "8px",
    padding: "8px 0",
    minWidth: "180px",
    boxShadow: "0 8px 24px rgba(0, 0, 0, 0.4)",
    zIndex: 1000,
  };

  const contextItemStyle: React.CSSProperties = {
    padding: "8px 16px",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    color: "#ebf3ff",
    fontSize: "13px",
    cursor: "pointer",
    transition: "160ms ease",
  };

  const detailPanelStyle: React.CSSProperties = {
    position: "absolute",
    right: 0,
    top: 0,
    bottom: 0,
    width: "320px",
    background: "rgba(9, 19, 34, 0.95)",
    borderLeft: "1px solid rgba(140, 192, 255, 0.12)",
    padding: "20px",
    overflow: "auto",
    backdropFilter: "blur(18px)",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#07111f" }}>
      <div style={toolbarStyle}>
        <select
          aria-label="Active ontology"
          value={ontologyUri}
          onChange={(event) => setOntologyUri(event.target.value)}
          style={selectStyle}
        >
          <option value="">Select ontology...</option>
          {registry.map((entry) => (
            <option key={entry.uri} value={entry.uri}>
              {entry.name || entry.uri}
            </option>
          ))}
        </select>
        <button style={toolbarButtonStyle} onClick={addClass}>
          <Plus size={14} />
          Add Class
        </button>
        <button style={toolbarButtonStyle} onClick={addProperty} disabled={nodes.length < 2}>
          <GitBranch size={14} />
          Add Property
        </button>
        <button style={toolbarButtonStyle} onClick={addIndividual}>
          <User size={14} />
          Add Individual
        </button>
        <button style={toolbarButtonStyle} onClick={addRestriction}>
          <Shield size={14} />
          Add Restriction
        </button>
        <button style={toolbarButtonStyle} onClick={addAxiom}>
          <FileText size={14} />
          Add Axiom
        </button>
        <button style={toolbarButtonStyle} onClick={autoLayout}>
          <Layout size={14} />
          Auto Layout
        </button>
        <div style={{ flex: 1 }} />
        <button style={toolbarButtonStyle} onClick={saveDraft} disabled={isSaving}>
          <Send size={14} />
          {isSaving ? "Saving..." : "Propose"}
        </button>
      </div>

      <div style={{ flex: 1, position: "relative" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedElement(node)}
          onEdgeClick={(_, edge) => setSelectedElement(edge)}
          onNodeContextMenu={handleNodeContextMenu}
          onEdgeContextMenu={handleEdgeContextMenu}
          nodeTypes={nodeTypes}
          fitView
          style={{ background: "#07111f" }}
        >
          <Background color="#1a2d3d" gap={20} />
          <Controls />
          <MiniMap nodeColor="#4aa3ff" maskColor="rgba(0,0,0,0.6)" />
        </ReactFlow>

        {showContext && (
          <div style={{ ...contextMenuStyle, left: showContext.x, top: showContext.y }}>
            <div style={contextItemStyle} onClick={renameSelected}>
              <Pencil size={14} />
              Rename
            </div>
            <div style={contextItemStyle} onClick={deleteSelected}>
              <Trash2 size={14} />
              Delete
            </div>
          </div>
        )}

        {selectedElement && (
          <div style={detailPanelStyle}>
            <h3 style={{ margin: "0 0 16px", color: "#ebf3ff", fontSize: "16px" }}>
              {"source" in selectedElement ? "Property Details" : "Class Details"}
            </h3>
            <div style={{ marginBottom: "12px" }}>
              <label style={{ display: "block", color: "#8fa8c6", fontSize: "12px", marginBottom: "4px" }}>
                ID
              </label>
              <div style={{ color: "#ebf3ff", fontSize: "13px", wordBreak: "break-all" }}>
                {selectedElement.id}
              </div>
            </div>
            {!("source" in selectedElement) && (
              <>
                <div style={{ marginBottom: "12px" }}>
                  <label style={{ display: "block", color: "#8fa8c6", fontSize: "12px", marginBottom: "4px" }}>
                    Label
                  </label>
                  <input
                    type="text"
                    value={String(selectedElement.data.label ?? "")}
                    onChange={(e) => {
                      setNodes((nds) =>
                        nds.map((n) =>
                          n.id === selectedElement.id
                            ? { ...n, data: { ...n.data, label: e.target.value } }
                            : n
                        )
                      );
                      setDraftDiff((prev) => ({
                        ...prev,
                        modified_classes: {
                          ...prev.modified_classes,
                          [selectedElement.id]: { label: e.target.value },
                        },
                      }));
                    }}
                    style={{
                      width: "100%",
                      padding: "8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(127, 208, 255, 0.2)",
                      background: "rgba(3, 9, 18, 0.8)",
                      color: "#ebf3ff",
                      fontSize: "13px",
                    }}
                  />
                </div>
                <div style={{ marginBottom: "12px" }}>
                  <label style={{ display: "block", color: "#8fa8c6", fontSize: "12px", marginBottom: "4px" }}>
                    Type
                  </label>
                  <div style={{ color: "#ebf3ff", fontSize: "13px" }}>
                    {selectedElement.data.type || "owl:Class"}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
