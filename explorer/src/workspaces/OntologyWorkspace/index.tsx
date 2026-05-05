import { useCallback, useEffect, useState } from "react";
import {
  BookMarked,
  GitMerge,
  HeartPulse,
  Layers,
  Shield,
  Sliders,
} from "lucide-react";
import { AlignmentsTab } from "./AlignmentsTab";
import { HealthTab } from "./HealthTab";
import { OntologyManager } from "./OntologyManager";
import { OntologyEditor } from "./OntologyEditor";
import { ShaclStudio } from "./ShaclStudio";
import { VersionsTab } from "./VersionsTab";

export type OntologyHubTab =
  | "registry"
  | "editor"
  | "versions"
  | "alignments"
  | "health"
  | "shacl";

const TAB_PARAM = "ontologyTab";

const TABS: { id: OntologyHubTab; label: string; icon: typeof GitMerge }[] = [
  { id: "registry", label: "Registry", icon: BookMarked },
  { id: "editor", label: "Editor", icon: Sliders },
  { id: "versions", label: "Versions", icon: Layers },
  { id: "alignments", label: "Alignments", icon: GitMerge },
  { id: "health", label: "Health", icon: HeartPulse },
  { id: "shacl", label: "SHACL", icon: Shield },
];

function readTabParam(): OntologyHubTab {
  try {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get(TAB_PARAM);
    if (raw && TABS.some((t) => t.id === raw)) return raw as OntologyHubTab;
  } catch {
    // ignore
  }
  return "registry";
}

function writeTabParam(tab: OntologyHubTab) {
  try {
    const params = new URLSearchParams(window.location.search);
    params.set(TAB_PARAM, tab);
    window.history.replaceState(null, "", `?${params.toString()}`);
  } catch {
    // ignore
  }
}

function ComingSoonStub({
  icon: Icon,
  title,
  description,
  badge,
}: {
  icon: typeof GitMerge;
  title: string;
  description: string;
  badge: string;
}) {
  return (
    <div style={stubShellStyle}>
      <div style={stubCardStyle}>
        <div style={stubIconRingStyle}>
          <Icon size={28} color="#7fd0ff" />
        </div>
        <div style={stubBadgeStyle}>{badge}</div>
        <h2 style={stubTitleStyle}>{title}</h2>
        <p style={stubDescStyle}>{description}</p>
        <div style={stubDividerStyle} />
        <p style={stubSubnoteStyle}>Coming in Subissue 2 / 3 of Ontology Hub</p>
      </div>
    </div>
  );
}

interface OntologyWorkspaceProps {
  onJumpToGraphNode?: (nodeId: string) => void;
}

export function OntologyWorkspace({ onJumpToGraphNode }: OntologyWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<OntologyHubTab>(readTabParam);

  useEffect(() => {
    writeTabParam(activeTab);
  }, [activeTab]);

  const handleTabChange = useCallback((tab: OntologyHubTab) => {
    setActiveTab(tab);
  }, []);

  const handleFixInEditor = useCallback((entityUri: string) => {
    const params = new URLSearchParams(window.location.search);
    params.set(TAB_PARAM, "editor");
    params.set("ontologyEntity", entityUri);
    window.history.replaceState(null, "", `?${params.toString()}`);
    setActiveTab("editor");
  }, []);

  const renderTab = () => {
    switch (activeTab) {
      case "registry":
        return <OntologyManager />;
      case "editor":
        return <OntologyEditor />;
      case "versions":
        return <VersionsTab />;
      case "alignments":
        return <AlignmentsTab />;
      case "health":
        return <HealthTab onFixInEditor={handleFixInEditor} />;
      case "shacl":
        return <ShaclStudio onJumpToNode={onJumpToGraphNode} />;
    }
  };

  return (
    <div style={shellStyle}>
      <div style={tabBarStyle}>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            style={{
              ...tabBtnBase,
              ...(activeTab === id ? tabBtnActive : tabBtnIdle),
            }}
            onClick={() => handleTabChange(id)}
          >
            <Icon size={14} />
            <span>{label}</span>
          </button>
        ))}
      </div>
      <div style={contentStyle}>{renderTab()}</div>
    </div>
  );
}

/* ─── styles ─────────────────────────────────────────────────────────── */

const shellStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  width: "100%",
  height: "100%",
  background: "#07111f",
  overflow: "hidden",
};

const tabBarStyle: React.CSSProperties = {
  display: "flex",
  gap: 6,
  padding: "10px 18px",
  borderBottom: "1px solid rgba(140,192,255,0.12)",
  background: "rgba(3,9,18,0.72)",
  flexShrink: 0,
  flexWrap: "wrap",
};

const tabBtnBase: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "7px 13px",
  borderRadius: 999,
  border: "1px solid transparent",
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 600,
  transition: "160ms ease",
  background: "transparent",
};

const tabBtnIdle: React.CSSProperties = {
  color: "#8fa8c6",
  borderColor: "rgba(127,208,255,0.1)",
};

const tabBtnActive: React.CSSProperties = {
  color: "#ebf3ff",
  background: "rgba(74,163,255,0.16)",
  borderColor: "rgba(127,208,255,0.3)",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)",
};

const contentStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflow: "hidden",
};

const stubShellStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: "100%",
  height: "100%",
  background: "linear-gradient(180deg, rgba(7,17,31,0.8), rgba(5,11,21,0.95))",
};

const stubCardStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: 12,
  padding: "48px 52px",
  borderRadius: 28,
  border: "1px solid rgba(127,208,255,0.12)",
  background: "rgba(9,19,34,0.82)",
  boxShadow: "0 24px 64px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.06)",
  maxWidth: 480,
  textAlign: "center",
};

const stubIconRingStyle: React.CSSProperties = {
  width: 64,
  height: 64,
  borderRadius: "50%",
  display: "grid",
  placeItems: "center",
  background: "rgba(74,163,255,0.1)",
  border: "1px solid rgba(127,208,255,0.18)",
  marginBottom: 4,
};

const stubBadgeStyle: React.CSSProperties = {
  padding: "4px 10px",
  borderRadius: 999,
  background: "rgba(242,182,109,0.1)",
  border: "1px solid rgba(242,182,109,0.22)",
  color: "#f2b66d",
  fontSize: 10,
  fontWeight: 800,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
};

const stubTitleStyle: React.CSSProperties = {
  margin: 0,
  color: "#ebf3ff",
  fontSize: 22,
  fontWeight: 800,
  letterSpacing: "-0.04em",
};

const stubDescStyle: React.CSSProperties = {
  margin: 0,
  color: "#8fa8c6",
  fontSize: 14,
  lineHeight: 1.65,
  maxWidth: 360,
};

const stubDividerStyle: React.CSSProperties = {
  width: "100%",
  height: 1,
  background: "rgba(127,208,255,0.08)",
};

const stubSubnoteStyle: React.CSSProperties = {
  margin: 0,
  color: "#5a7a9a",
  fontSize: 12,
};
