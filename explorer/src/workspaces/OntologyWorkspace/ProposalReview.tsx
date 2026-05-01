import { useCallback, useEffect, useState } from "react";
import {
  GitMerge,
  CheckCircle,
  XCircle,
  AlertCircle,
  Send,
  MessageSquare,
  User,
  Clock,
  Plus,
  Minus,
  Edit,
} from "lucide-react";

interface Proposal {
  proposal_id: string;
  draft_id: string;
  ontology_uri: string;
  summary: string;
  author: string;
  reviewer: string | null;
  state: "draft" | "proposed" | "approved" | "published" | "rejected";
  impact_analysis: Record<string, any>;
  shacl_validation: Record<string, any>;
  created_at: string;
  updated_at: string;
  comments: Record<string, any>[];
}

interface DiffChange {
  type: "added" | "removed" | "modified";
  element: string;
  details?: Record<string, any>;
}

export function ProposalReview({ proposalId }: { proposalId: string }) {
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [diff, setDiff] = useState<DiffChange[]>([]);
  const [selectedElement, setSelectedElement] = useState<string | null>(null);
  const [commentText, setCommentText] = useState("");

  const loadProposal = useCallback(async () => {
    try {
      const response = await fetch(`/api/ontology/proposals/${proposalId}`);
      if (response.ok) {
        const data = await response.json();
        setProposal(data);
        generateDiff(data);
      }
    } catch (error) {
      console.error("Failed to load proposal:", error);
    }
  }, [proposalId]);

  const generateDiff = useCallback((prop: Proposal) => {
    const changes: DiffChange[] = [];

    // Generate diff from impact analysis
    if (prop.impact_analysis) {
      if (prop.impact_analysis.class_adds > 0) {
        changes.push({ type: "added", element: `Classes (${prop.impact_analysis.class_adds})` });
      }
      if (prop.impact_analysis.class_removals > 0) {
        changes.push({ type: "removed", element: `Classes (${prop.impact_analysis.class_removals})` });
      }
      if (prop.impact_analysis.property_changes > 0) {
        changes.push({ type: "modified", element: `Properties (${prop.impact_analysis.property_changes})` });
      }
      if (prop.impact_analysis.restriction_changes > 0) {
        changes.push({ type: "modified", element: `Restrictions (${prop.impact_analysis.restriction_changes})` });
      }
    }

    setDiff(changes);
  }, []);

  useEffect(() => {
    loadProposal();
  }, [loadProposal]);

  const addComment = useCallback(async () => {
    if (!selectedElement || !commentText || !proposal) return;
    try {
      const response = await fetch(`/api/ontology/proposals/${proposal.proposal_id}/comment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          element_uri: selectedElement,
          text: commentText,
          author: "user",
        }),
      });
      if (response.ok) {
        setCommentText("");
        loadProposal();
      }
    } catch (error) {
      console.error("Failed to add comment:", error);
      alert("Failed to add comment");
    }
  }, [selectedElement, commentText, proposal, loadProposal]);

  const approveProposal = useCallback(async () => {
    if (!proposal) return;
    try {
      const response = await fetch(`/api/ontology/proposals/${proposal.proposal_id}/approve`, {
        method: "POST",
      });
      if (response.ok) {
        alert("Proposal approved");
        loadProposal();
      }
    } catch (error) {
      console.error("Failed to approve proposal:", error);
      alert("Failed to approve proposal");
    }
  }, [proposal, loadProposal]);

  const rejectProposal = useCallback(async () => {
    if (!proposal) return;
    try {
      const response = await fetch(`/api/ontology/proposals/${proposal.proposal_id}/reject`, {
        method: "POST",
      });
      if (response.ok) {
        alert("Proposal rejected");
        loadProposal();
      }
    } catch (error) {
      console.error("Failed to reject proposal:", error);
      alert("Failed to reject proposal");
    }
  }, [proposal, loadProposal]);

  const publishProposal = useCallback(async () => {
    if (!proposal) return;
    try {
      const response = await fetch(`/api/ontology/proposals/${proposal.proposal_id}/publish`, {
        method: "POST",
      });
      if (response.ok) {
        alert("Proposal published");
        loadProposal();
      }
    } catch (error) {
      console.error("Failed to publish proposal:", error);
      alert("Failed to publish proposal");
    }
  }, [proposal, loadProposal]);

  const getChangeIcon = (type: string) => {
    switch (type) {
      case "added":
        return <Plus size={14} color="#4cc38a" />;
      case "removed":
        return <Minus size={14} color="#ff6b6b" />;
      case "modified":
        return <Edit size={14} color="#f2b66d" />;
      default:
        return null;
    }
  };

  const getStateIcon = (state: string) => {
    switch (state) {
      case "published":
        return <CheckCircle size={20} color="#4cc38a" />;
      case "approved":
        return <CheckCircle size={20} color="#4aa3ff" />;
      case "rejected":
        return <XCircle size={20} color="#ff6b6b" />;
      case "proposed":
        return <AlertCircle size={20} color="#f2b66d" />;
      default:
        return <Clock size={20} color="#8fa8c6" />;
    }
  };

  const containerStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    background: "#07111f",
    padding: "20px",
    overflow: "auto",
  };

  const headerStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "20px",
    paddingBottom: "16px",
    borderBottom: "1px solid rgba(140, 192, 255, 0.12)",
  };

  const titleStyle: React.CSSProperties = {
    margin: 0,
    color: "#ebf3ff",
    fontSize: "20px",
    fontWeight: "700",
  };

  const contentStyle: React.CSSProperties = {
    display: "flex",
    gap: "20px",
    flex: 1,
    minHeight: 0,
  };

  const diffPanelStyle: React.CSSProperties = {
    flex: 1,
    background: "rgba(9, 19, 34, 0.8)",
    borderRadius: "8px",
    border: "1px solid rgba(127, 208, 255, 0.12)",
    padding: "16px",
    overflow: "auto",
  };

  const commentsPanelStyle: React.CSSProperties = {
    width: "320px",
    background: "rgba(9, 19, 34, 0.8)",
    borderRadius: "8px",
    border: "1px solid rgba(127, 208, 255, 0.12)",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
  };

  const diffItemStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 12px",
    borderRadius: "6px",
    background: "rgba(3, 9, 18, 0.6)",
    marginBottom: "8px",
    cursor: "pointer",
    transition: "160ms ease",
  };

  const buttonStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    padding: "8px 14px",
    borderRadius: "6px",
    border: "1px solid rgba(127, 208, 255, 0.2)",
    background: "rgba(74, 163, 255, 0.1)",
    color: "#ebf3ff",
    fontSize: "12px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "160ms ease",
  };

  const textareaStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    borderRadius: "6px",
    border: "1px solid rgba(127, 208, 255, 0.2)",
    background: "rgba(3, 9, 18, 0.8)",
    color: "#ebf3ff",
    fontSize: "13px",
    resize: "vertical",
    minHeight: "80px",
  };

  if (!proposal) {
    return (
      <div style={containerStyle}>
        <div style={{ color: "#8fa8c6", fontSize: "14px" }}>Loading proposal...</div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {getStateIcon(proposal.state)}
          <div>
            <h1 style={titleStyle}>{proposal.summary}</h1>
            <div style={{ color: "#8fa8c6", fontSize: "12px", marginTop: "4px" }}>
              {proposal.author} • {new Date(proposal.created_at).toLocaleString()}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          {proposal.state === "proposed" && (
            <>
              <button style={buttonStyle} onClick={approveProposal}>
                <CheckCircle size={12} />
                Approve
              </button>
              <button style={buttonStyle} onClick={rejectProposal}>
                <XCircle size={12} />
                Reject
              </button>
            </>
          )}
          {proposal.state === "approved" && (
            <button style={buttonStyle} onClick={publishProposal}>
              <Send size={12} />
              Publish
            </button>
          )}
        </div>
      </div>

      <div style={contentStyle}>
        <div style={diffPanelStyle}>
          <h2 style={{ margin: "0 0 16px", color: "#ebf3ff", fontSize: "14px", fontWeight: "600" }}>
            <GitMerge size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
            Diff Viewer
          </h2>
          {diff.length === 0 ? (
            <div style={{ color: "#8fa8c6", fontSize: "13px" }}>No changes detected</div>
          ) : (
            diff.map((change, index) => (
              <div
                key={index}
                style={{
                  ...diffItemStyle,
                  border: selectedElement === change.element ? "1px solid rgba(74, 163, 255, 0.4)" : "1px solid transparent",
                }}
                onClick={() => setSelectedElement(change.element)}
              >
                {getChangeIcon(change.type)}
                <div style={{ flex: 1 }}>
                  <div style={{ color: "#ebf3ff", fontSize: "13px", fontWeight: "600" }}>
                    {change.element}
                  </div>
                  <div style={{ color: "#8fa8c6", fontSize: "11px" }}>
                    {change.type}
                  </div>
                </div>
              </div>
            ))
          )}

          <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid rgba(140, 192, 255, 0.12)" }}>
            <h3 style={{ margin: "0 0 12px", color: "#ebf3ff", fontSize: "13px", fontWeight: "600" }}>
              Impact Analysis
            </h3>
            <pre style={{ background: "rgba(3, 9, 18, 0.8)", padding: "12px", borderRadius: "6px", color: "#ebf3ff", fontSize: "12px", overflow: "auto" }}>
              {JSON.stringify(proposal.impact_analysis, null, 2)}
            </pre>
          </div>

          <div style={{ marginTop: "16px" }}>
            <h3 style={{ margin: "0 0 12px", color: "#ebf3ff", fontSize: "13px", fontWeight: "600" }}>
              SHACL Validation
            </h3>
            <pre style={{ background: "rgba(3, 9, 18, 0.8)", padding: "12px", borderRadius: "6px", color: "#ebf3ff", fontSize: "12px", overflow: "auto" }}>
              {JSON.stringify(proposal.shacl_validation, null, 2)}
            </pre>
          </div>
        </div>

        <div style={commentsPanelStyle}>
          <h2 style={{ margin: "0 0 16px", color: "#ebf3ff", fontSize: "14px", fontWeight: "600" }}>
            <MessageSquare size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
            Comments ({proposal.comments.length})
          </h2>
          <div style={{ flex: 1, overflow: "auto", marginBottom: "12px" }}>
            {proposal.comments.length === 0 ? (
              <div style={{ color: "#8fa8c6", fontSize: "13px" }}>No comments yet</div>
            ) : (
              proposal.comments.map((comment) => (
                <div
                  key={comment.id}
                  style={{
                    padding: "10px",
                    background: "rgba(3, 9, 18, 0.6)",
                    borderRadius: "6px",
                    marginBottom: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                    <User size={12} color="#8fa8c6" />
                    <span style={{ color: "#ebf3ff", fontSize: "12px", fontWeight: "600" }}>
                      {comment.author}
                    </span>
                  </div>
                  <div style={{ color: "#8fa8c6", fontSize: "12px", marginBottom: "4px" }}>{comment.text}</div>
                  <div style={{ color: "#5a7a9a", fontSize: "10px" }}>
                    {new Date(comment.created_at).toLocaleString()}
                  </div>
                </div>
              ))
            )}
          </div>
          {selectedElement && (
            <div>
              <textarea
                placeholder="Add a comment..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                style={textareaStyle}
              />
              <button style={buttonStyle} onClick={addComment} disabled={!commentText}>
                <Send size={12} />
                Add Comment
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
