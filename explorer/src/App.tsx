import { lazy, Suspense, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Database, FileSearch, GitBranchPlus, Scale, Settings2 } from 'lucide-react';

const DecisionWorkspace = lazy(() => import('./workspaces/DecisionWorkspace/DecisionWorkspace').then((module) => ({ default: module.DecisionWorkspace })));
const DiffMergeWorkspace = lazy(() => import('./workspaces/DiffMergeWorkspace/DiffMergeWorkspace').then((module) => ({ default: module.DiffMergeWorkspace })));
const GraphWorkspace = lazy(() => import('./workspaces/GraphWorkspace/GraphWorkspace').then((module) => ({ default: module.GraphWorkspace })));
const ImportExportWorkspace = lazy(() => import('./workspaces/ImportExportWorkspace/ImportExportWorkspace').then((module) => ({ default: module.ImportExportWorkspace })));
const LineageDiagram = lazy(() => import('./workspaces/LineageWorkspace/LineageDiagram').then((module) => ({ default: module.LineageDiagram })));
const ReasoningWorkspace = lazy(() => import('./workspaces/ReasoningWorkspace').then((module) => ({ default: module.ReasoningWorkspace })));
const SparqlWorkspace = lazy(() => import('./workspaces/SparqlWorkspace/SparqlWorkspace').then((module) => ({ default: module.SparqlWorkspace })));
const VocabularyWorkspace = lazy(() => import('./workspaces/VocabularyWorkspace/VocabularyWorkspace').then((module) => ({ default: module.VocabularyWorkspace })));
const RegistryTab = lazy(() => import('./workspaces/EnrichWorkspace/RegistryTab').then((module) => ({ default: module.RegistryTab })));
const EntityResolutionTab = lazy(() => import('./workspaces/EnrichWorkspace/EntityResolutionTab').then((module) => ({ default: module.EntityResolutionTab })));
const KGOverviewTab = lazy(() => import('./workspaces/ManageWorkspace/KGOverviewTab').then((module) => ({ default: module.KGOverviewTab })));
const OntologySummaryTab = lazy(() => import('./workspaces/ManageWorkspace/OntologySummaryTab').then((module) => ({ default: module.OntologySummaryTab })));

type WorkspaceId = 'welcome' | 'explore' | 'analyze' | 'decisions' | 'enrich' | 'manage';
type ExploreView = 'graph' | 'vocabulary';
type AnalyzeView = 'sparql' | 'reasoning';
type EnrichView = 'import' | 'merge' | 'registry' | 'resolve';
type ManageView = 'lineage' | 'kg-overview' | 'ontology';

type NavItem = {
  id: WorkspaceId;
  label: string;
  hint: string;
  icon: typeof Database;
};

const queryClient = new QueryClient();

const navItems: NavItem[] = [
  { id: 'explore', label: 'Knowledge Explorer', hint: 'Graph and vocabulary browsing', icon: Database },
  { id: 'analyze', label: 'Analyze', hint: 'Query and inspect the dataset', icon: FileSearch },
  { id: 'decisions', label: 'Decisions', hint: 'Decision chains and precedent review', icon: Scale },
  { id: 'enrich', label: 'Enrich', hint: 'Import, export, and merge workflows', icon: GitBranchPlus },
  { id: 'manage', label: 'Manage', hint: 'Lineage and governance tooling', icon: Settings2 },
];

const shellStyles = `
  :root {
    --app-bg: #07111f;
    --panel-bg: rgba(7, 17, 31, 0.82);
    --panel-border: rgba(140, 192, 255, 0.14);
    --text-main: #ebf3ff;
    --text-muted: #8fa8c6;
    --accent: #4aa3ff;
    --accent-strong: #7fd0ff;
    --warm: #f2b66d;
    --success: #4cc38a;
  }

  .app-shell {
    display: flex;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    color: var(--text-main);
    background:
      radial-gradient(circle at top left, rgba(74, 163, 255, 0.12), transparent 32%),
      radial-gradient(circle at bottom right, rgba(242, 182, 109, 0.08), transparent 26%),
      linear-gradient(180deg, #091322 0%, #050b15 100%);
    font-family: "Segoe UI", "SF Pro Display", sans-serif;
  }

  .app-rail {
    width: 88px;
    padding: 20px 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    border-right: 1px solid var(--panel-border);
    background: rgba(3, 9, 18, 0.92);
    backdrop-filter: blur(18px);
  }

  .brand-pill {
    width: 100%;
    min-height: 56px;
    border-radius: 18px;
    display: grid;
    place-items: center;
    color: var(--text-main);
    background: linear-gradient(135deg, rgba(74, 163, 255, 0.22), rgba(127, 208, 255, 0.08));
    border: 1px solid rgba(127, 208, 255, 0.18);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
  }

  .nav-button {
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-muted);
    border-radius: 18px;
    min-height: 72px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    transition: 160ms ease;
  }

  .nav-button:hover {
    color: var(--text-main);
    background: rgba(74, 163, 255, 0.08);
    border-color: rgba(74, 163, 255, 0.12);
  }

  .nav-button[data-active='true'] {
    color: var(--text-main);
    background: linear-gradient(180deg, rgba(74, 163, 255, 0.18), rgba(74, 163, 255, 0.08));
    border-color: rgba(127, 208, 255, 0.22);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
  }

  .nav-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  .workspace-shell {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .workspace-header {
    padding: 14px 22px;
    border-bottom: 1px solid var(--panel-border);
    background: linear-gradient(180deg, rgba(7, 17, 31, 0.94), rgba(7, 17, 31, 0.82));
    backdrop-filter: blur(18px);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    min-height: 68px;
  }

  .workspace-header--compact {
    min-height: 60px;
    padding: 10px 18px;
    background: linear-gradient(180deg, rgba(7, 17, 31, 0.92), rgba(7, 17, 31, 0.72));
  }

  .workspace-header--compact .workspace-title {
    font-size: 16px;
  }

  .workspace-header--compact .workspace-subtitle {
    font-size: 11px;
  }

  .workspace-header-main {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .workspace-kicker {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 999px;
    background: rgba(74, 163, 255, 0.08);
    border: 1px solid rgba(127, 208, 255, 0.14);
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
  }

  .workspace-kicker::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--accent-strong), var(--warm));
    box-shadow: 0 0 14px rgba(127, 208, 255, 0.45);
  }

  .workspace-title-block {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .workspace-title {
    margin: 0;
    font-size: 20px;
    line-height: 1;
    letter-spacing: -0.03em;
  }

  .workspace-subtitle {
    color: var(--text-muted);
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .workspace-tabs {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .workspace-tab {
    border: 1px solid rgba(127, 208, 255, 0.18);
    background: rgba(9, 19, 34, 0.56);
    color: var(--text-muted);
    border-radius: 999px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    transition: 160ms ease;
    white-space: nowrap;
  }

  .workspace-tab[data-active='true'] {
    color: var(--text-main);
    background: rgba(74, 163, 255, 0.16);
    border-color: rgba(127, 208, 255, 0.3);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
  }

  .workspace-body {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .workspace-loading {
    height: 100%;
    display: grid;
    place-items: center;
    color: var(--text-muted);
    background: linear-gradient(180deg, rgba(7, 17, 31, 0.8), rgba(5, 11, 21, 0.92));
    font-size: 14px;
  }

  @media (max-width: 980px) {
    .workspace-header {
      flex-direction: column;
      align-items: stretch;
      min-height: auto;
      padding: 12px 18px;
    }

    .workspace-header-main {
      justify-content: space-between;
    }

    .workspace-subtitle {
      white-space: normal;
    }

    .workspace-tabs {
      justify-content: flex-start;
    }
  }
`;

function WorkspaceShell({
  title,
  subtitle,
  tabs,
  compact = false,
  kicker = 'Workspace',
  children,
}: {
  title: string;
  subtitle?: string;
  tabs?: ReactNode;
  compact?: boolean;
  kicker?: string;
  children: ReactNode;
}) {
  return (
    <section className="workspace-shell">
      <header className={`workspace-header${compact ? " workspace-header--compact" : ""}`}>
        <div className="workspace-header-main">
          <div className="workspace-kicker">{kicker}</div>
          <div className="workspace-title-block">
            <h1 className="workspace-title">{title}</h1>
            {subtitle ? <div className="workspace-subtitle">{subtitle}</div> : null}
          </div>
        </div>
        {tabs ? <div className="workspace-tabs">{tabs}</div> : null}
      </header>
      <div className="workspace-body">{children}</div>
    </section>
  );
}

function WorkspaceFallback() {
  return <div className="workspace-loading">Loading workspace…</div>;
}

function WelcomeScreen() {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 12,
      color: 'var(--text-muted)',
    }}>
      <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.03em' }}>
        Welcome to Semantica
      </h1>
      <p style={{ margin: 0, fontSize: 14 }}>
        Select a workspace from the sidebar to get started.
      </p>
    </div>
  );
}

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>('welcome');
  const [exploreView, setExploreView] = useState<ExploreView>('graph');
  const [analyzeView, setAnalyzeView] = useState<AnalyzeView>('reasoning');
  const [enrichView, setEnrichView] = useState<EnrichView>('import');
  const [manageView, setManageView] = useState<ManageView>('lineage');

  const renderWorkspace = () => {
    if (activeWorkspace === 'welcome') {
      return <WelcomeScreen />;
    }

    if (activeWorkspace === 'explore') {
      return (
        <WorkspaceShell
          title="Explore"
          subtitle={exploreView === 'graph' ? undefined : "Browse the graph and switch views without leaving the workspace."}
          kicker={exploreView === 'graph' ? 'Graph Studio' : 'Vocabulary Browser'}
          compact
          tabs={
            <>
              <button className="workspace-tab" data-active={exploreView === 'graph'} onClick={() => setExploreView('graph')}>
                Network Explorer
              </button>
              <button className="workspace-tab" data-active={exploreView === 'vocabulary'} onClick={() => setExploreView('vocabulary')}>
                Vocabulary Browser
              </button>
            </>
          }
        >
          <Suspense fallback={<WorkspaceFallback />}>
            {exploreView === 'graph' ? <GraphWorkspace /> : <VocabularyWorkspace />}
          </Suspense>
        </WorkspaceShell>
      );
    }

    if (activeWorkspace === 'analyze') {
      return (
        <WorkspaceShell
          title="Analyze"
          subtitle="Query the active graph and test inference rules."
          kicker={analyzeView === 'reasoning' ? 'Reasoning Engine' : 'SPARQL Query'}
          tabs={
            <>
              <button className="workspace-tab" data-active={analyzeView === 'reasoning'} onClick={() => setAnalyzeView('reasoning')}>
                Reasoning Playground
              </button>
              <button className="workspace-tab" data-active={analyzeView === 'sparql'} onClick={() => setAnalyzeView('sparql')}>
                SPARQL Querying
              </button>
            </>
          }
        >
          <Suspense fallback={<WorkspaceFallback />}>
            {analyzeView === 'reasoning' ? <ReasoningWorkspace /> : <SparqlWorkspace />}
          </Suspense>
        </WorkspaceShell>
      );
    }

    if (activeWorkspace === 'decisions') {
      return (
        <WorkspaceShell
          title="Decisions"
          subtitle="Inspect decision chains, causal context, and precedent matches."
          kicker="Decision Intelligence"
        >
          <Suspense fallback={<WorkspaceFallback />}>
            <DecisionWorkspace />
          </Suspense>
        </WorkspaceShell>
      );
    }

    if (activeWorkspace === 'enrich') {
      return (
        <WorkspaceShell
          title="Enrich"
          subtitle="Import, export, reconcile, and audit graph entities."
          kicker="Knowledge Audit"
          tabs={
            <>
              <button className="workspace-tab" data-active={enrichView === 'import'} onClick={() => setEnrichView('import')}>
                Import and Export
              </button>
              <button className="workspace-tab" data-active={enrichView === 'merge'} onClick={() => setEnrichView('merge')}>
                Diff and Merge
              </button>
              <button className="workspace-tab" data-active={enrichView === 'resolve'} onClick={() => setEnrichView('resolve')}>
                Entity Resolution
              </button>
              <button className="workspace-tab" data-active={enrichView === 'registry'} onClick={() => setEnrichView('registry')}>
                Registry
              </button>
            </>
          }
        >
          <Suspense fallback={<WorkspaceFallback />}>
            {enrichView === 'import' ? <ImportExportWorkspace /> :
             enrichView === 'merge' ? <DiffMergeWorkspace /> :
             enrichView === 'resolve' ? <EntityResolutionTab /> :
             <RegistryTab />}
          </Suspense>
        </WorkspaceShell>
      );
    }

    return (
      <WorkspaceShell
        title="Manage"
        subtitle="Review provenance, lineage, ontology, and governance context."
        kicker="Graph Governance"
        tabs={
          <>
            <button className="workspace-tab" data-active={manageView === 'lineage'} onClick={() => setManageView('lineage')}>
              PROV-O Lineage
            </button>
            <button className="workspace-tab" data-active={manageView === 'kg-overview'} onClick={() => setManageView('kg-overview')}>
              KG Overview
            </button>
            <button className="workspace-tab" data-active={manageView === 'ontology'} onClick={() => setManageView('ontology')}>
              Ontology Summary
            </button>
          </>
        }
      >
        <Suspense fallback={<WorkspaceFallback />}>
          {manageView === 'lineage' ? <LineageDiagram /> :
           manageView === 'kg-overview' ? <KGOverviewTab /> :
           <OntologySummaryTab onOpenVocabularyBrowser={() => {
             setActiveWorkspace('explore');
             setExploreView('vocabulary');
           }} />}
        </Suspense>
      </WorkspaceShell>
    );
  };

  return (
    <QueryClientProvider client={queryClient}>
      <style>{shellStyles}</style>
      <div className="app-shell">
        <aside className="app-rail">
          <button className="brand-pill" title="Semantica Knowledge Explorer" onClick={() => setActiveWorkspace('welcome')} style={{ cursor: 'pointer', border: '1px solid rgba(127,208,255,0.18)' }}>SKE</button>
          {navItems.map(({ id, label, hint, icon: Icon }) => (
            <button
              key={id}
              className="nav-button"
              data-active={activeWorkspace === id}
              onClick={() => setActiveWorkspace(id)}
              title={hint}
            >
              <Icon size={20} />
              <span className="nav-label">{label}</span>
            </button>
          ))}
        </aside>
        {renderWorkspace()}
      </div>
    </QueryClientProvider>
  );
}
