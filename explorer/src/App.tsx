import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  ArrowRight,
  BrainCircuit,
  Database,
  FileSearch,
  GitBranchPlus,
  GitMerge,
  LogOut,
  Network,
  Radar,
  Route,
  Scale,
  Search,
  Settings2,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { ErrorBoundary } from './ErrorBoundary';
import { ExploreWorkspaceTabs, type ExploreView } from './ExploreWorkspaceTabs';
import { fetchAgentMemoryAvailability } from './explorerCapabilities';
import { hasOntologyUrlState } from './workspaces/OntologyWorkspace/ontologyUrlState';
import {
  AUTH_EXPIRED_EVENT,
  clearSession,
  fetchAuthStatus,
  installAuthFetchBridge,
  peekStoredUser,
  verifyStoredSession,
  type AuthUser,
} from './api/auth';
import { LoginGate } from './api/LoginGate';

const DecisionWorkspace = lazy(() => import('./workspaces/DecisionWorkspace/DecisionWorkspace').then((module) => ({ default: module.DecisionWorkspace })));
const DiffMergeWorkspace = lazy(() => import('./workspaces/DiffMergeWorkspace/DiffMergeWorkspace').then((module) => ({ default: module.DiffMergeWorkspace })));
const GraphWorkspace = lazy(() => import('./workspaces/GraphWorkspace/GraphWorkspace').then((module) => ({ default: module.GraphWorkspace })));
const MemoryWorkspace = lazy(() => import('./workspaces/MemoryWorkspace').then((module) => ({ default: module.MemoryWorkspace })));
const ImportExportWorkspace = lazy(() => import('./workspaces/ImportExportWorkspace/ImportExportWorkspace').then((module) => ({ default: module.ImportExportWorkspace })));
const LineageDiagram = lazy(() => import('./workspaces/LineageWorkspace/LineageDiagram').then((module) => ({ default: module.LineageDiagram })));
const ReasoningWorkspace = lazy(() => import('./workspaces/ReasoningWorkspace').then((module) => ({ default: module.ReasoningWorkspace })));
const SparqlWorkspace = lazy(() => import('./workspaces/SparqlWorkspace/SparqlWorkspace').then((module) => ({ default: module.SparqlWorkspace })));
const VocabularyWorkspace = lazy(() => import('./workspaces/VocabularyWorkspace/VocabularyWorkspace').then((module) => ({ default: module.VocabularyWorkspace })));
const RegistryTab = lazy(() => import('./workspaces/EnrichWorkspace/RegistryTab').then((module) => ({ default: module.RegistryTab })));
const EntityResolutionTab = lazy(() => import('./workspaces/EnrichWorkspace/EntityResolutionTab').then((module) => ({ default: module.EntityResolutionTab })));
const KGOverviewTab = lazy(() => import('./workspaces/ManageWorkspace/KGOverviewTab').then((module) => ({ default: module.KGOverviewTab })));
const OntologySummaryTab = lazy(() => import('./workspaces/ManageWorkspace/OntologySummaryTab').then((module) => ({ default: module.OntologySummaryTab })));
const OntologyWorkspace = lazy(() => import('./workspaces/OntologyWorkspace').then((module) => ({ default: module.OntologyWorkspace })));

type WorkspaceId = 'welcome' | 'explore' | 'analyze' | 'decisions' | 'enrich' | 'manage' | 'ontology-hub';
type AnalyzeView = 'sparql' | 'reasoning';
type EnrichView = 'import' | 'merge' | 'registry' | 'resolve';
type ManageView = 'lineage' | 'kg-overview' | 'ontology';

type NavItem = {
  id: WorkspaceId;
  label: string;
  hint: string;
  icon: LucideIcon;
};

type LandingMetric = {
  label: string;
  value: string;
  tone?: 'cyan' | 'mint' | 'amber' | 'rose';
};

type LandingAction = {
  label: string;
  description: string;
  icon: LucideIcon;
  onClick: () => void;
};

type GraphStatsPayload = {
  node_count?: number;
  edge_count?: number;
  nodeCount?: number;
  edgeCount?: number;
  nodes?: number;
  edges?: number;
};

type ConnectionStatus = 'checking' | 'online' | 'offline';

const CONNECTION_STATUS_LABEL: Record<ConnectionStatus, string> = {
  checking: '连接中…',
  online: '系统在线',
  offline: '后端不可达',
};

const queryClient = new QueryClient();

const PREVIEW_DOTS = Array.from({ length: 42 }, (_, i) => ({
  cx: 170 + ((i * 73) % 330),
  cy: 170 + ((i * 47) % 210),
  r: 2 + (i % 3),
  fill: (['#2da44e', '#0052d9', '#e37318', '#d54941'] as const)[i % 4],
}));

const navItems: NavItem[] = [
  { id: 'explore', label: '知识探索', hint: '图谱与词汇浏览', icon: Database },
  { id: 'analyze', label: '分析', hint: '查询与检查数据集', icon: FileSearch },
  { id: 'decisions', label: '决策', hint: '决策链与先例审查', icon: Scale },
  { id: 'enrich', label: '数据增强', hint: '导入、导出与合并流程', icon: GitBranchPlus },
  { id: 'manage', label: '管理', hint: '溯源与治理工具', icon: Settings2 },
  { id: 'ontology-hub', label: '本体中心', hint: '模式治理、注册表与词汇管理', icon: GitMerge },
];

function readInitialWorkspace(): WorkspaceId {
  return hasOntologyUrlState() ? 'ontology-hub' : 'welcome';
}

const shellStyles = `
  :root {
    --app-bg: #eeeeee;
    --panel-bg: #ffffff;
    --panel-border: #e8e8e8;
    --text-main: rgba(0, 0, 0, 0.9);
    --text-muted: rgba(0, 0, 0, 0.6);
    --accent: #0052d9;
    --accent-strong: #366ef4;
    --warm: #e37318;
    --success: #2ba471;

    /* ── Shared workspace design tokens ── */
    --ws-bg: #eeeeee;
    --ws-surface: #f3f3f3;
    --ws-surface-hover: rgba(0, 82, 217, 0.06);
    --ws-border: #e8e8e8;
    --ws-border-strong: #ddd;
    --ws-text: rgba(0, 0, 0, 0.9);
    --ws-text-muted: rgba(0, 0, 0, 0.6);
    --ws-text-dim: rgba(0, 0, 0, 0.26);
    --ws-accent: #0052d9;
    --ws-accent-soft: rgba(0, 82, 217, 0.08);
    --ws-green: #2ba471;
    --ws-green-soft: rgba(43, 164, 113, 0.1);
    --ws-amber: #e37318;
    --ws-amber-soft: rgba(227, 115, 24, 0.1);
    --ws-red: #d54941;
    --ws-red-soft: rgba(213, 73, 65, 0.1);
    --ws-purple: #7b53d8;
    --ws-purple-soft: rgba(123, 83, 216, 0.08);
    --ws-radius: 14px;
    --ws-radius-sm: 8px;
    --ws-radius-lg: 20px;
  }

  /* ── Shared workspace primitives (available to all workspace components) ── */
  .ws-page {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    background: var(--ws-bg);
    overflow: hidden;
  }

  .ws-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    scrollbar-color: var(--ws-border) transparent;
  }

  .ws-padded {
    padding: 24px 28px;
  }

  .ws-split {
    display: grid;
    height: 100%;
    overflow: hidden;
  }

  .ws-split--2col { grid-template-columns: 300px 1fr; }
  .ws-split--half { grid-template-columns: 1fr 1fr; }
  .ws-split--rows { grid-template-rows: 1fr auto; }

  .ws-panel {
    background: var(--ws-surface);
    border: 1px solid var(--ws-border);
    border-radius: var(--ws-radius);
    overflow: hidden;
  }

  .ws-panel--inset {
    background: rgba(0,0,0,0.035);
    border: 1px solid rgba(0, 82, 217,0.09);
    border-radius: var(--ws-radius);
  }

  .ws-card {
    background: var(--ws-surface);
    border: 1px solid var(--ws-border);
    border-radius: var(--ws-radius);
    padding: 20px;
    position: relative;
    overflow: hidden;
    transition: border-color 180ms ease, background 180ms ease;
  }

  .ws-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 82, 217,0.18), transparent);
  }

  .ws-card:hover {
    border-color: var(--ws-border-strong);
    background: var(--ws-surface-hover);
  }

  .ws-eyebrow {
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ws-text-muted);
  }

  .ws-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ws-text-muted);
    margin-bottom: 8px;
    display: block;
  }

  .ws-title {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.035em;
    color: var(--ws-text);
    margin: 0;
  }

  .ws-body {
    font-size: 13px;
    line-height: 1.65;
    color: var(--ws-text-muted);
  }

  .ws-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 9px 16px;
    border-radius: var(--ws-radius-sm);
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    transition: 160ms ease;
    border: 1px solid transparent;
  }

  .ws-btn--primary {
    background: linear-gradient(135deg, rgba(0, 82, 217,0.28), rgba(43, 164, 113,0.16));
    border-color: rgba(0, 82, 217,0.4);
    color: rgba(0, 0, 0, 0.9);
    box-shadow: 0 0 0 1px rgba(0, 82, 217,0.08) inset;
  }

  .ws-btn--primary:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(0, 82, 217,0.4), rgba(43, 164, 113,0.24));
    border-color: rgba(0, 82, 217,0.6);
    box-shadow: 0 6px 20px rgba(0, 82, 217,0.18);
    transform: translateY(-1px);
  }

  .ws-btn--ghost {
    background: rgba(0, 0, 0, 0.04);
    border-color: var(--ws-border);
    color: var(--ws-text-muted);
  }

  .ws-btn--ghost:hover:not(:disabled) {
    background: var(--ws-surface-hover);
    border-color: var(--ws-border-strong);
    color: var(--ws-text);
  }

  .ws-btn--danger {
    background: var(--ws-red-soft);
    border-color: rgba(213, 73, 65,0.3);
    color: #d54941;
  }

  .ws-btn--success {
    background: var(--ws-green-soft);
    border-color: rgba(43, 164, 113,0.3);
    color: #2ba471;
  }

  .ws-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none !important;
  }

  .ws-input {
    width: 100%;
    padding: 9px 12px;
    background: #ffffff;
    border: 1px solid var(--ws-border);
    border-radius: var(--ws-radius-sm);
    color: var(--ws-text);
    font-size: 13px;
    outline: none;
    transition: border-color 160ms ease;
    box-sizing: border-box;
  }

  .ws-input:focus {
    border-color: var(--ws-accent);
    box-shadow: 0 0 0 3px rgba(0, 82, 217,0.1);
  }

  .ws-textarea {
    width: 100%;
    padding: 12px;
    background: #ffffff;
    border: 1px solid var(--ws-border);
    border-radius: var(--ws-radius-sm);
    color: var(--ws-text);
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: 12.5px;
    line-height: 1.7;
    resize: vertical;
    outline: none;
    transition: border-color 160ms ease;
    box-sizing: border-box;
  }

  .ws-textarea:focus {
    border-color: var(--ws-accent);
    box-shadow: 0 0 0 3px rgba(0, 82, 217,0.1);
  }

  .ws-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    white-space: nowrap;
  }

  .ws-pill--accent { color: #366ef4; background: var(--ws-accent-soft); border: 1px solid rgba(0, 82, 217,0.22); }
  .ws-pill--green  { color: #2ba471; background: var(--ws-green-soft);  border: 1px solid rgba(43, 164, 113,0.28); }
  .ws-pill--amber  { color: #e37318; background: var(--ws-amber-soft);  border: 1px solid rgba(227, 115, 24,0.28); }
  .ws-pill--red    { color: #d54941; background: var(--ws-red-soft);    border: 1px solid rgba(213, 73, 65,0.28); }
  .ws-pill--purple { color: #7b53d8; background: var(--ws-purple-soft); border: 1px solid rgba(123, 83, 216,0.22); }
  .ws-pill--mono   { color: var(--ws-text-muted); background: rgba(0, 0, 0, 0.04); border: 1px solid rgba(0, 0, 0, 0.08); }

  .ws-divider {
    height: 1px;
    background: var(--ws-border);
    margin: 0;
  }

  .ws-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 48px 24px;
    gap: 10px;
    color: var(--ws-text-muted);
  }

  .ws-empty-icon { opacity: 0.35; margin-bottom: 4px; }
  .ws-empty-title { font-size: 14px; font-weight: 700; color: var(--ws-text); }
  .ws-empty-body { font-size: 12px; line-height: 1.5; max-width: 36ch; }

  .ws-sidebar {
    border-right: 1px solid var(--ws-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: rgba(0,0,0,0.03);
  }

  .ws-sidebar-header {
    padding: 18px 16px 14px;
    border-bottom: 1px solid var(--ws-border);
    flex-shrink: 0;
  }

  .ws-sidebar-body {
    flex: 1;
    overflow-y: auto;
    padding: 10px 10px;
    scrollbar-width: thin;
    scrollbar-color: var(--ws-border) transparent;
  }

  .ws-list-item {
    width: 100%;
    text-align: left;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--ws-text-muted);
    cursor: pointer;
    transition: 140ms ease;
    display: block;
  }

  .ws-list-item:hover {
    background: var(--ws-surface);
    border-color: var(--ws-border);
    color: var(--ws-text);
  }

  .ws-list-item--active {
    background: var(--ws-accent-soft);
    border-color: var(--ws-border-strong);
    color: rgba(0, 0, 0, 0.9);
  }

  .ws-stat-grid {
    display: grid;
    gap: 12px;
  }

  .ws-stat-grid--3 { grid-template-columns: repeat(3, 1fr); }
  .ws-stat-grid--4 { grid-template-columns: repeat(4, 1fr); }
  .ws-stat-grid--2 { grid-template-columns: repeat(2, 1fr); }

  .ws-stat-card {
    padding: 18px 20px;
    border-radius: var(--ws-radius);
    border: 1px solid var(--ws-border);
    background: var(--ws-surface);
    position: relative;
    overflow: hidden;
  }

  .ws-stat-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 82, 217,0.2), transparent);
  }

  .ws-stat-value {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: var(--ws-text);
    line-height: 1;
  }

  .ws-stat-label {
    margin-top: 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--ws-text-dim);
    letter-spacing: 0.04em;
  }

  @keyframes ws-spin { to { transform: rotate(360deg); } }
  .ws-spin { animation: ws-spin 0.8s linear infinite; }

  @keyframes ws-skeleton {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.7; }
  }

  .ws-skeleton {
    background: rgba(0, 0, 0, 0.06);
    border-radius: 8px;
    animation: ws-skeleton 1.4s ease-in-out infinite;
  }

  @keyframes ws-slide-up {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .ws-animate-in { animation: ws-slide-up 0.22s ease both; }

  .app-shell {
    display: flex;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    color: var(--text-main);
    background:
      radial-gradient(circle at top left, rgba(0, 82, 217, 0.05), transparent 32%),
      radial-gradient(circle at bottom right, rgba(227, 115, 24, 0.04), transparent 26%),
      linear-gradient(180deg, #f6f7f9 0%, #ececee 100%);
    font-family: "Segoe UI", "SF Pro Display", sans-serif;
  }

  .app-rail {
    width: 88px;
    padding: 20px 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    border-right: 1px solid var(--panel-border);
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(18px);
  }

  .brand-pill {
    width: 100%;
    min-height: 56px;
    border-radius: 18px;
    display: grid;
    place-items: center;
    color: var(--text-main);
    background: linear-gradient(135deg, rgba(0, 82, 217, 0.22), rgba(54, 110, 244, 0.08));
    border: 1px solid rgba(54, 110, 244, 0.18);
    box-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.08);
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
    background: rgba(0, 82, 217, 0.08);
    border-color: rgba(0, 82, 217, 0.12);
  }

  .nav-button[data-active='true'] {
    color: var(--text-main);
    background: linear-gradient(180deg, rgba(0, 82, 217, 0.18), rgba(0, 82, 217, 0.08));
    border-color: rgba(54, 110, 244, 0.22);
    box-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.08);
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
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 255, 255, 0.82));
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
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.72));
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
    background: rgba(0, 82, 217, 0.08);
    border: 1px solid rgba(54, 110, 244, 0.14);
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
    box-shadow: 0 0 14px rgba(54, 110, 244, 0.45);
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
    border: 1px solid rgba(54, 110, 244, 0.18);
    background: rgba(255, 255, 255, 0.56);
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
    background: rgba(0, 82, 217, 0.16);
    border-color: rgba(54, 110, 244, 0.3);
    box-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.05);
  }

  .workspace-body {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  /* ── Welcome page ─────────────────────────────────────── */
  .landing-page {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    background:
      radial-gradient(ellipse 80% 50% at 50% -10%, rgba(0, 82, 217, 0.18) 0%, transparent 60%),
      radial-gradient(ellipse 60% 40% at 80% 90%, rgba(227, 115, 24, 0.1) 0%, transparent 50%),
      linear-gradient(180deg, #eeeeee 0%, #ececee 100%);
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 82, 217,0.18) transparent;
  }

  .landing-page::before {
    content: "";
    position: fixed;
    inset: 0 0 0 88px;
    pointer-events: none;
    background:
      repeating-linear-gradient(0deg, transparent, transparent 79px, rgba(0, 82, 217,0.035) 80px),
      repeating-linear-gradient(90deg, transparent, transparent 79px, rgba(0, 82, 217,0.025) 80px);
    mask-image: radial-gradient(ellipse 90% 80% at 50% 20%, black 30%, transparent 100%);
  }

  .landing-shell {
    position: relative;
    z-index: 1;
    width: min(1360px, 100%);
    margin: 0 auto;
    padding: clamp(28px, 4vw, 56px) clamp(20px, 3vw, 48px);
    display: flex;
    flex-direction: column;
    gap: 56px;
  }

  /* ── Hero ──────────────────────────────────────────────── */
  .landing-hero {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(380px, 520px);
    gap: clamp(24px, 3vw, 48px);
    align-items: center;
    min-height: min(580px, calc(100vh - 140px));
  }

  .landing-copy {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .landing-status-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 24px;
    --status-color: #2ba471;
    --status-shadow-a: 0 0 0 3px rgba(43, 164, 113, 0.22), 0 0 12px rgba(43, 164, 113, 0.5);
    --status-shadow-b: 0 0 0 5px rgba(43, 164, 113, 0.1), 0 0 20px rgba(43, 164, 113, 0.35);
  }

  .landing-status-bar[data-status='checking'] {
    --status-color: #e37318;
    --status-shadow-a: 0 0 0 3px rgba(227, 115, 24, 0.22), 0 0 12px rgba(227, 115, 24, 0.5);
    --status-shadow-b: 0 0 0 5px rgba(227, 115, 24, 0.1), 0 0 20px rgba(227, 115, 24, 0.35);
  }

  .landing-status-bar[data-status='offline'] {
    --status-color: #d54941;
    --status-shadow-a: 0 0 0 3px rgba(213, 73, 65, 0.22), 0 0 12px rgba(213, 73, 65, 0.5);
    --status-shadow-b: 0 0 0 5px rgba(213, 73, 65, 0.1), 0 0 20px rgba(213, 73, 65, 0.35);
  }

  .landing-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: var(--status-color);
    box-shadow: var(--status-shadow-a);
    animation: landing-pulse 2.4s ease-in-out infinite;
  }

  .landing-status-text {
    color: var(--status-color);
    font: 700 11px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .landing-status-divider {
    width: 1px;
    height: 14px;
    background: rgba(158, 217, 255, 0.2);
  }

  .landing-status-version {
    color: rgba(0, 0, 0, 0.4);
    font: 600 11px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.06em;
  }

  .landing-kicker {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 12px 5px 8px;
    border-radius: 999px;
    border: 1px solid rgba(0, 82, 217, 0.3);
    background: rgba(0, 82, 217, 0.08);
    color: #366ef4;
    font: 700 11px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    width: fit-content;
    margin-bottom: 20px;
  }

  .landing-kicker-mark {
    width: 16px;
    height: 16px;
    border-radius: 6px;
    background: linear-gradient(135deg, #0052d9, #2ba471);
    display: grid;
    place-items: center;
    flex: 0 0 auto;
  }

  .landing-kicker-node { display: none; }

  .landing-kicker-mark::after {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 999px;
    background: rgba(3, 10, 20, 0.8);
  }

  .landing-title {
    margin: 0 0 20px;
    color: rgba(0, 0, 0, 0.9);
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: clamp(38px, 4.8vw, 72px);
    line-height: 1.08;
    letter-spacing: -0.04em;
    font-weight: 800;
  }

  .landing-title span {
    color: transparent;
    background: linear-gradient(100deg, #366ef4 0%, #2ba471 50%, #e37318 100%);
    -webkit-background-clip: text;
    background-clip: text;
  }

  .landing-subtitle {
    margin: 0 0 32px;
    color: rgba(0, 0, 0, 0.4);
    font-size: clamp(14px, 1.2vw, 17px);
    line-height: 1.7;
    max-width: 54ch;
  }

  .landing-cta-row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .landing-cta-primary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 22px;
    border-radius: 12px;
    border: 1px solid rgba(0, 82, 217, 0.5);
    background: linear-gradient(135deg, rgba(0, 82, 217, 0.28), rgba(43, 164, 113, 0.18));
    color: rgba(0, 0, 0, 0.9);
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: 180ms ease;
    box-shadow: 0 0 0 1px rgba(0, 82, 217, 0.1) inset, 0 8px 24px rgba(0, 82, 217, 0.15);
  }

  .landing-cta-primary:hover {
    transform: translateY(-2px);
    background: linear-gradient(135deg, rgba(0, 82, 217, 0.38), rgba(43, 164, 113, 0.26));
    box-shadow: 0 0 0 1px rgba(0, 82, 217, 0.18) inset, 0 14px 32px rgba(0, 82, 217, 0.22);
  }

  .landing-cta-secondary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 18px;
    border-radius: 12px;
    border: 1px solid rgba(158, 217, 255, 0.14);
    background: rgba(0, 0, 0, 0.04);
    color: rgba(0, 0, 0, 0.4);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: 180ms ease;
  }

  .landing-cta-secondary:hover {
    border-color: rgba(158, 217, 255, 0.26);
    color: rgba(0, 0, 0, 0.7);
    background: rgba(0, 0, 0, 0.07);
  }

  /* ── Preview panel ─────────────────────────────────────── */
  .landing-preview {
    position: relative;
    overflow: hidden;
    border-radius: 24px;
    border: 1px solid rgba(0, 82, 217, 0.18);
    background:
      radial-gradient(circle at 40% 30%, rgba(0, 82, 217, 0.06), transparent 46%),
      radial-gradient(circle at 70% 70%, rgba(227, 115, 24, 0.05), transparent 38%),
      linear-gradient(145deg, #ffffff, #f1f3f7);
    box-shadow: 0 24px 72px rgba(0, 0, 0, 0.14), 0 0 0 1px rgba(0, 0, 0, 0.04) inset;
    aspect-ratio: 4/3.2;
    min-height: 340px;
  }

  .landing-preview-topbar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 38px;
    background: rgba(255, 255, 255, 0.82);
    border-bottom: 1px solid rgba(0, 82, 217, 0.1);
    backdrop-filter: blur(12px);
    display: flex;
    align-items: center;
    padding: 0 14px;
    gap: 8px;
  }

  .landing-preview-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
  }

  .landing-preview-dot:nth-child(1) { background: rgba(213, 73, 65, 0.7); }
  .landing-preview-dot:nth-child(2) { background: rgba(227, 115, 24, 0.7); }
  .landing-preview-dot:nth-child(3) { background: rgba(43, 164, 113, 0.7); }

  .landing-preview-tab {
    margin-left: 12px;
    padding: 3px 10px;
    border-radius: 6px;
    background: rgba(0, 82, 217, 0.12);
    border: 1px solid rgba(0, 82, 217, 0.2);
    color: #366ef4;
    font: 600 10px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.06em;
  }

  .landing-preview-orbit {
    position: absolute;
    inset: 38px 0 0;
    opacity: 0.95;
  }

  .landing-preview-orbit svg {
    width: 100%;
    height: 100%;
    overflow: visible;
  }

  .landing-preview-line {
    stroke: rgba(0, 82, 217, 0.3);
    stroke-width: 1.2;
    fill: none;
    stroke-dasharray: 4 3;
  }

  .landing-preview-line--warm {
    stroke: rgba(227, 115, 24, 0.3);
  }

  .landing-preview-line--mint {
    stroke: rgba(43, 164, 113, 0.28);
  }

  .landing-node {
    transform-origin: center;
    animation: landing-float 7s ease-in-out infinite;
  }

  .landing-node:nth-child(2n) { animation-delay: -2.2s; }
  .landing-node:nth-child(3n) { animation-delay: -4.1s; }

  .landing-command-card,
  .landing-dossier-card,
  .landing-timeline-card {
    position: absolute;
    border: 1px solid rgba(0, 82, 217, 0.16);
    background: rgba(255, 255, 255, 0.84);
    backdrop-filter: blur(20px);
    box-shadow: 0 12px 32px rgba(0,0,0,0.12), 0 0 0 1px rgba(0, 0, 0, 0.04) inset;
  }

  .landing-command-card {
    top: 50px;
    left: 16px;
    right: 16px;
    border-radius: 14px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .landing-command-icon {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    display: grid;
    place-items: center;
    color: #2ba471;
    background: rgba(43, 164, 113, 0.1);
    border: 1px solid rgba(43, 164, 113, 0.2);
    flex: 0 0 auto;
  }

  .landing-command-label {
    color: rgba(0, 0, 0, 0.7);
    font-size: 12px;
    font-weight: 700;
  }

  .landing-command-meta {
    margin-top: 2px;
    color: rgba(0, 0, 0, 0.4);
    font: 500 10px/1 "JetBrains Mono", monospace;
  }

  .landing-dossier-card {
    right: 14px;
    bottom: 80px;
    width: min(210px, calc(100% - 28px));
    border-radius: 16px;
    padding: 14px;
  }

  .landing-dossier-kicker {
    color: #2ba471;
    font: 700 9px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .landing-dossier-title {
    margin-top: 6px;
    color: rgba(0, 0, 0, 0.9);
    font: 800 20px/1 "Inter", sans-serif;
    letter-spacing: -0.04em;
  }

  .landing-dossier-row {
    margin-top: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    color: rgba(0, 0, 0, 0.4);
    font-size: 10px;
    font-weight: 600;
  }

  .landing-dossier-row strong { color: #e37318; font-weight: 700; }

  .landing-timeline-card {
    left: 14px;
    right: 14px;
    bottom: 14px;
    border-radius: 12px;
    padding: 10px 12px;
  }

  .landing-timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .landing-timeline-title {
    color: rgba(0, 0, 0, 0.4);
    font: 700 9px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .landing-timeline-badge {
    color: #366ef4;
    font: 700 9px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.06em;
  }

  .landing-timeline-track {
    position: relative;
    height: 4px;
    border-radius: 999px;
    background: rgba(0, 82, 217, 0.1);
    overflow: hidden;
  }

  .landing-timeline-track::after {
    content: "";
    position: absolute;
    inset: 0 28% 0 0;
    border-radius: inherit;
    background: linear-gradient(90deg, #2ba471, #0052d9, #e37318);
  }

  .landing-timeline-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    color: rgba(0, 0, 0, 0.26);
    font: 600 9px/1 "JetBrains Mono", monospace;
  }

  /* ── Metrics strip ─────────────────────────────────────── */
  .landing-metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .landing-metric {
    padding: 18px 20px;
    border-radius: 16px;
    border: 1px solid rgba(158, 217, 255, 0.09);
    background: rgba(0, 0, 0, 0.025);
    position: relative;
    overflow: hidden;
    transition: border-color 200ms ease;
  }

  .landing-metric::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(158, 217, 255, 0.2), transparent);
  }

  .landing-metric:hover {
    border-color: rgba(158, 217, 255, 0.18);
  }

  .landing-metric-value {
    color: rgba(0, 0, 0, 0.9);
    font: 800 28px/1 "Inter", sans-serif;
    letter-spacing: -0.04em;
  }

  .landing-metric[data-tone='mint'] .landing-metric-value { color: #2ba471; }
  .landing-metric[data-tone='amber'] .landing-metric-value { color: #e37318; }
  .landing-metric[data-tone='rose'] .landing-metric-value { color: #d54941; }
  .landing-metric[data-tone='cyan'] .landing-metric-value { color: #366ef4; }

  .landing-metric-label {
    margin-top: 6px;
    color: rgba(0, 0, 0, 0.4);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  /* ── Workspace grid ────────────────────────────────────── */
  .landing-section-header {
    display: flex;
    align-items: baseline;
    gap: 14px;
    margin-bottom: 16px;
  }

  .landing-section-title {
    color: rgba(0, 0, 0, 0.7);
    font: 700 13px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin: 0;
  }

  .landing-section-line {
    flex: 1;
    height: 1px;
    background: rgba(0, 82, 217, 0.1);
  }

  .landing-workspace-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .landing-workspace-card {
    position: relative;
    overflow: hidden;
    padding: 22px;
    border-radius: 18px;
    border: 1px solid rgba(158, 217, 255, 0.09);
    background: rgba(0, 0, 0, 0.025);
    cursor: pointer;
    text-align: left;
    color: inherit;
    transition: border-color 200ms ease, background 200ms ease, transform 200ms ease, box-shadow 200ms ease;
  }

  .landing-workspace-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(158, 217, 255, 0.16), transparent);
    opacity: 0;
    transition: opacity 200ms ease;
  }

  .landing-workspace-card:hover {
    border-color: rgba(0, 82, 217, 0.24);
    background: rgba(0, 82, 217, 0.06);
    transform: translateY(-3px);
    box-shadow: 0 12px 32px rgba(0,0,0,0.14);
  }

  .landing-workspace-card:hover::before { opacity: 1; }

  .landing-workspace-card--primary {
    grid-column: span 3;
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 24px;
    border-color: rgba(43, 164, 113, 0.22);
    background: linear-gradient(135deg, rgba(43, 164, 113, 0.08), rgba(0, 82, 217, 0.05));
  }

  .landing-workspace-card--primary:hover {
    border-color: rgba(43, 164, 113, 0.38);
    background: linear-gradient(135deg, rgba(43, 164, 113, 0.12), rgba(0, 82, 217, 0.08));
    box-shadow: 0 12px 40px rgba(43, 164, 113, 0.12);
  }

  .landing-workspace-card-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    color: #366ef4;
    background: rgba(0, 82, 217, 0.1);
    border: 1px solid rgba(0, 82, 217, 0.2);
    margin-bottom: 14px;
  }

  .landing-workspace-card--primary .landing-workspace-card-icon {
    color: #2ba471;
    background: rgba(43, 164, 113, 0.1);
    border-color: rgba(43, 164, 113, 0.22);
    width: 48px;
    height: 48px;
    border-radius: 14px;
    margin-bottom: 0;
  }

  .landing-workspace-card-eyebrow {
    color: #2ba471;
    font: 700 10px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }

  .landing-workspace-card-title {
    color: rgba(0, 0, 0, 0.85);
    font: 700 16px/1.2 "Inter", sans-serif;
    letter-spacing: -0.025em;
    margin-bottom: 6px;
  }

  .landing-workspace-card--primary .landing-workspace-card-title {
    font-size: 20px;
  }

  .landing-workspace-card-desc {
    color: rgba(0, 0, 0, 0.4);
    font-size: 12px;
    line-height: 1.5;
    max-width: 36ch;
  }

  .landing-workspace-card-arrow {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: grid;
    place-items: center;
    color: #2ba471;
    background: rgba(43, 164, 113, 0.1);
    border: 1px solid rgba(43, 164, 113, 0.2);
    flex: 0 0 auto;
    transition: 180ms ease;
  }

  .landing-workspace-card--primary:hover .landing-workspace-card-arrow {
    background: rgba(43, 164, 113, 0.18);
    transform: translateX(3px);
  }

  /* ── Capability band ───────────────────────────────────── */
  .landing-capability-band {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 14px 18px;
    border: 1px solid rgba(0, 82, 217, 0.1);
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(12px);
  }

  .landing-capability-label {
    color: rgba(0, 0, 0, 0.26);
    font: 700 10px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-right: 4px;
    white-space: nowrap;
  }

  .landing-capability {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 28px;
    padding: 0 10px;
    border-radius: 999px;
    color: rgba(0, 0, 0, 0.4);
    background: rgba(0, 82, 217, 0.05);
    border: 1px solid rgba(0, 82, 217, 0.12);
    font-size: 11px;
    font-weight: 600;
    transition: 160ms ease;
    cursor: default;
  }

  .landing-capability:hover {
    color: #0052d9;
    border-color: rgba(0, 82, 217, 0.28);
    background: rgba(0, 82, 217, 0.1);
  }

  /* ── Animations ────────────────────────────────────────── */
  @keyframes landing-float {
    0%, 100% { transform: translateY(0) scale(1); }
    50% { transform: translateY(-8px) scale(1.05); }
  }

  @keyframes landing-pulse {
    0%, 100% { box-shadow: var(--status-shadow-a); }
    50% { box-shadow: var(--status-shadow-b); }
  }

  .workspace-loading {
    height: 100%;
    display: grid;
    place-items: center;
    color: var(--text-muted);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.92));
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

    .landing-hero {
      grid-template-columns: 1fr;
      min-height: auto;
    }

    .landing-workspace-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .landing-workspace-card--primary {
      grid-column: span 2;
    }

    .landing-metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .landing-preview {
      aspect-ratio: 16/10;
      min-height: 320px;
    }
  }

  @media (max-width: 680px) {
    .app-rail {
      width: 72px;
      padding: 14px 9px;
    }

    .landing-shell {
      padding: 20px 16px;
      gap: 36px;
    }

    .landing-workspace-grid {
      grid-template-columns: 1fr;
    }

    .landing-workspace-card--primary {
      grid-column: span 1;
      grid-template-columns: 1fr;
    }

    .landing-workspace-card-arrow {
      display: none;
    }

    .landing-metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .landing-preview {
      min-height: 280px;
    }

    .landing-dossier-card {
      left: 10px;
      right: 10px;
      width: auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .landing-node,
    .landing-workspace-card,
    .landing-cta-primary,
    .landing-cta-secondary {
      animation: none;
      transition: none;
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

function getNumberStat(payload: GraphStatsPayload, keys: Array<keyof GraphStatsPayload>) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

function formatMetric(value: number | null, fallback: string) {
  return value === null ? fallback : value.toLocaleString();
}

function WelcomeScreen({
  onOpenNetwork,
  onOpenVocabulary,
  onOpenReasoning,
  onOpenImport,
  onOpenDecisions,
  onOpenManage,
}: {
  onOpenNetwork: () => void;
  onOpenVocabulary: () => void;
  onOpenReasoning: () => void;
  onOpenImport: () => void;
  onOpenDecisions: () => void;
  onOpenManage: () => void;
}) {
  const [stats, setStats] = useState<{ nodes: number | null; edges: number | null; status: ConnectionStatus }>({
    nodes: null,
    edges: null,
    status: 'checking',
  });

  useEffect(() => {
    const controller = new AbortController();

    fetch('/api/graph/stats', { signal: controller.signal })
      .then((response) => (response.ok ? response.json() as Promise<GraphStatsPayload> : null))
      .then((payload) => {
        if (!payload) {
          setStats((current) => ({ ...current, status: 'offline' }));
          return;
        }

        setStats({
          nodes: getNumberStat(payload, ['node_count', 'nodeCount', 'nodes']),
          edges: getNumberStat(payload, ['edge_count', 'edgeCount', 'edges']),
          status: 'online',
        });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        setStats((current) => ({ ...current, status: 'offline' }));
      });

    return () => controller.abort();
  }, []);

  const isOnline = stats.status === 'online';
  const metrics: LandingMetric[] = [
    { label: '知识节点', value: formatMetric(stats.nodes, '在线'), tone: 'cyan' },
    { label: '已映射关系', value: formatMetric(stats.edges, '就绪'), tone: 'mint' },
    { label: '图谱模式', value: '3', tone: 'amber' },
    { label: isOnline ? '数据集在线' : '随时可探索', value: isOnline ? '活跃' : '待命', tone: 'rose' },
  ];

  const secondaryLaunchers: LandingAction[] = [
    {
      label: '词汇表',
      description: '模式与术语',
      icon: Database,
      onClick: onOpenVocabulary,
    },
    {
      label: '分析',
      description: '推理与查询',
      icon: BrainCircuit,
      onClick: onOpenReasoning,
    },
    {
      label: '决策',
      description: '决策链与先例',
      icon: Scale,
      onClick: onOpenDecisions,
    },
    {
      label: '数据增强',
      description: '导入与消解',
      icon: GitBranchPlus,
      onClick: onOpenImport,
    },
    {
      label: '管理',
      description: '溯源与本体',
      icon: ShieldCheck,
      onClick: onOpenManage,
    },
  ];

  return (
    <main className="landing-page">
      <div className="landing-shell">

        {/* ── Hero ── */}
        <section className="landing-hero">
          <div className="landing-copy">
            <div className="landing-status-bar" data-status={stats.status}>
              <div className="landing-status-dot" />
              <span className="landing-status-text">{CONNECTION_STATUS_LABEL[stats.status]}</span>
              <div className="landing-status-divider" />
              <span className="landing-status-version">COWIN · 语义智能平台</span>
            </div>

            <div className="landing-kicker" aria-label="产品类别">
              <span className="landing-kicker-mark" aria-hidden="true" />
              知识图谱工作台
            </div>

            <h1 className="landing-title">
              像生命系统一样<br />
              驾驭<span>知识网络。</span>
            </h1>
            <p className="landing-subtitle">
              COWIN 将高密度知识图谱转化为可导航的指挥中心 ——
              发现、推理、溯源、距离智能与决策上下文，
              尽在一个界面。
            </p>

            <div className="landing-cta-row">
              <button className="landing-cta-primary" type="button" onClick={onOpenNetwork}>
                <Network size={16} />
                打开 COWIN 图谱
                <ArrowRight size={15} />
              </button>
              <button className="landing-cta-secondary" type="button" onClick={onOpenReasoning}>
                <BrainCircuit size={15} />
                运行推理
              </button>
            </div>
          </div>

          {/* ── Preview panel ── */}
          <div className="landing-preview" aria-label="Knowledge graph preview">
            <div className="landing-preview-topbar" aria-hidden="true">
              <div className="landing-preview-dot" />
              <div className="landing-preview-dot" />
              <div className="landing-preview-dot" />
              <div className="landing-preview-tab">COWIN 图谱</div>
            </div>
            <div className="landing-command-card">
              <div className="landing-command-icon">
                <Search size={15} />
              </div>
              <div>
                <div className="landing-command-label">搜索命令、节点或概念</div>
                <div className="landing-command-meta">距离热力图 · 聚焦视图 · 因果路径</div>
              </div>
            </div>
            <div className="landing-preview-orbit">
              <svg viewBox="0 0 640 440" role="img" aria-hidden="true">
                <path className="landing-preview-line" d="M110 310 C200 110 390 90 510 240" />
                <path className="landing-preview-line landing-preview-line--warm" d="M120 190 C240 270 374 182 508 340" />
                <path className="landing-preview-line landing-preview-line--mint" d="M168 378 C274 200 392 218 488 144" />
                <path className="landing-preview-line landing-preview-line--warm" d="M204 118 C318 340 408 368 526 284" />
                <path className="landing-preview-line" d="M110 310 C180 350 260 360 340 320 C420 280 480 260 510 240" />
                <g className="landing-node">
                  <circle cx="110" cy="310" r="10" fill="#2ba471" fillOpacity="0.9" />
                  <circle cx="110" cy="310" r="20" fill="none" stroke="rgba(43, 164, 113,0.24)" strokeWidth="1.5" />
                  <circle cx="110" cy="310" r="34" fill="none" stroke="rgba(43, 164, 113,0.1)" strokeWidth="1" />
                </g>
                <g className="landing-node">
                  <circle cx="204" cy="118" r="7" fill="#0052d9" fillOpacity="0.9" />
                  <circle cx="204" cy="118" r="16" fill="none" stroke="rgba(0, 82, 217,0.24)" strokeWidth="1.5" />
                </g>
                <g className="landing-node">
                  <circle cx="510" cy="240" r="13" fill="#e37318" fillOpacity="0.9" />
                  <circle cx="510" cy="240" r="26" fill="none" stroke="rgba(227, 115, 24,0.26)" strokeWidth="1.5" />
                  <circle cx="510" cy="240" r="40" fill="none" stroke="rgba(227, 115, 24,0.1)" strokeWidth="1" />
                </g>
                <g className="landing-node">
                  <circle cx="488" cy="144" r="6" fill="#d54941" fillOpacity="0.9" />
                  <circle cx="488" cy="144" r="14" fill="none" stroke="rgba(213, 73, 65,0.22)" strokeWidth="1.5" />
                </g>
                <g className="landing-node">
                  <circle cx="340" cy="320" r="9" fill="#366ef4" fillOpacity="0.9" />
                  <circle cx="340" cy="320" r="20" fill="none" stroke="rgba(54, 110, 244,0.22)" strokeWidth="1.5" />
                </g>
                <g opacity="0.45">
                  {PREVIEW_DOTS.map((dot, index) => (
                    <circle key={index} cx={dot.cx} cy={dot.cy * 0.82} r={dot.r * 0.8} fill={dot.fill} />
                  ))}
                </g>
              </svg>
            </div>
            <div className="landing-dossier-card">
              <div className="landing-dossier-kicker">实体档案</div>
              <div className="landing-dossier-title">NSRP1</div>
              <div className="landing-dossier-row"><span>距离区间</span><strong>近</strong></div>
              <div className="landing-dossier-row"><span>路径一致性</span><strong>0.84</strong></div>
              <div className="landing-dossier-row"><span>溯源</span><strong>已审计</strong></div>
            </div>
            <div className="landing-timeline-card">
              <div className="landing-timeline-header">
                <span className="landing-timeline-title">时序证据</span>
                <span className="landing-timeline-badge">66% 覆盖率</span>
              </div>
              <div className="landing-timeline-track" />
              <div className="landing-timeline-labels">
                <span>1970</span>
                <span>2030</span>
              </div>
            </div>
          </div>
        </section>

        {/* ── Live metrics ── */}
        <div className="landing-metrics" aria-label="系统状态">
          {metrics.map((metric) => (
            <div key={metric.label} className="landing-metric" data-tone={metric.tone}>
              <div className="landing-metric-value">{metric.value}</div>
              <div className="landing-metric-label">{metric.label}</div>
            </div>
          ))}
        </div>

        {/* ── Workspace grid ── */}
        <section aria-label="工作区">
          <div className="landing-section-header">
            <h2 className="landing-section-title">工作区</h2>
            <div className="landing-section-line" />
          </div>
          <div className="landing-workspace-grid">
            <button className="landing-workspace-card landing-workspace-card--primary" type="button" onClick={onOpenNetwork}>
              <div>
                <div className="landing-workspace-card-eyebrow">主工作区</div>
                <div className="landing-workspace-card-title">COWIN 图谱</div>
                <div className="landing-workspace-card-desc">
                  完整图谱、社区分组、聚焦邻域与距离智能 —— 尽在一块画布。
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div className="landing-workspace-card-icon" style={{ marginBottom: 0 }}>
                  <Network size={22} />
                </div>
                <div className="landing-workspace-card-arrow">
                  <ArrowRight size={18} />
                </div>
              </div>
            </button>

            {secondaryLaunchers.map((launcher) => {
              const Icon = launcher.icon;
              return (
                <button key={launcher.label} className="landing-workspace-card" type="button" onClick={launcher.onClick}>
                  <div className="landing-workspace-card-icon">
                    <Icon size={18} />
                  </div>
                  <div className="landing-workspace-card-title">{launcher.label}</div>
                  <div className="landing-workspace-card-desc">{launcher.description}</div>
                </button>
              );
            })}
          </div>
        </section>

        {/* ── Capability band ── */}
        <section className="landing-capability-band" aria-label="智能能力">
          <div className="landing-capability-label">智能层</div>
          <div className="landing-capability"><Radar size={12} />距离热力图</div>
          <div className="landing-capability"><Network size={12} />聚焦邻域</div>
          <div className="landing-capability"><GitMerge size={12} />社区分组</div>
          <div className="landing-capability"><Route size={12} />因果路径追踪</div>
          <div className="landing-capability"><ShieldCheck size={12} />溯源档案</div>
        </section>

      </div>
    </main>
  );
}

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>(readInitialWorkspace);
  const [exploreView, setExploreView] = useState<ExploreView>('graph');
  const [analyzeView, setAnalyzeView] = useState<AnalyzeView>('reasoning');
  const [enrichView, setEnrichView] = useState<EnrichView>('import');
  const [manageView, setManageView] = useState<ManageView>('lineage');
  const [graphFocusRequest, setGraphFocusRequest] = useState<{ nodeId: string; token: number } | null>(null);
  const [exploreDraftDirty, setExploreDraftDirty] = useState(false);
  const [agentMemoryAvailable, setAgentMemoryAvailable] = useState(false);
  const [authState, setAuthState] = useState<'checking' | 'login' | 'ready'>('checking');
  const [authUser, setAuthUser] = useState<AuthUser | null>(peekStoredUser());
  const authRequiredRef = useRef(false);

  useEffect(() => {
    let active = true;
    void fetchAgentMemoryAvailability().then((available) => {
      if (active) setAgentMemoryAvailable(available);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    installAuthFetchBridge();
    let cancelled = false;
    void (async () => {
      const status = await fetchAuthStatus();
      if (cancelled) return;
      // 服务不可达或未启用 LDAP 登录时，保持既有行为，不弹登录页。
      if (!status || !status.ldap) {
        setAuthState('ready');
        return;
      }
      authRequiredRef.current = true;
      const user = await verifyStoredSession();
      if (cancelled) return;
      setAuthUser(user);
      setAuthState(user ? 'ready' : 'login');
    })();
    const handleAuthExpired = () => {
      if (!authRequiredRef.current) return;
      setAuthUser(null);
      setAuthState('login');
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    return () => {
      cancelled = true;
      window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    };
  }, []);

  const handleLogout = () => {
    clearSession();
    setAuthUser(null);
    setAuthState('login');
  };

  const confirmDiscardExploreDraft = () => (
    !exploreDraftDirty
    || window.confirm("放弃未应用的 Markdown 草稿并离开该资源？")
  );

  const switchExploreView = (nextView: ExploreView) => {
    if (nextView === exploreView) return;
    if (!confirmDiscardExploreDraft()) return;
    setExploreDraftDirty(false);
    setExploreView(nextView);
  };

  const switchWorkspace = (nextWorkspace: WorkspaceId) => {
    if (nextWorkspace === activeWorkspace) return;
    if (activeWorkspace === "explore" && !confirmDiscardExploreDraft()) return;
    setExploreDraftDirty(false);
    setActiveWorkspace(nextWorkspace);
  };


  const renderWorkspace = () => {
    if (activeWorkspace === 'welcome') {
      return (
        <WelcomeScreen
          onOpenNetwork={() => {
            setActiveWorkspace('explore');
            setExploreView('graph');
          }}
          onOpenVocabulary={() => {
            setActiveWorkspace('explore');
            setExploreView('vocabulary');
          }}
          onOpenReasoning={() => {
            setActiveWorkspace('analyze');
            setAnalyzeView('reasoning');
          }}
          onOpenImport={() => {
            setActiveWorkspace('enrich');
            setEnrichView('import');
          }}
          onOpenDecisions={() => setActiveWorkspace('decisions')}
          onOpenManage={() => setActiveWorkspace('manage')}
        />
      );
    }

    if (activeWorkspace === 'explore') {
      return (
        <WorkspaceShell
          title="探索"
          subtitle={exploreView === 'graph' ? undefined : exploreView === 'memories' ? "浏览并编辑规范的 AgentMemory 文档。" : "浏览图谱并在视图间切换，无需离开工作区。"}
          kicker={exploreView === 'graph' ? '图谱工作室' : exploreView === 'memories' ? '记忆浏览' : '词汇浏览'}
          compact
          tabs={
            <ExploreWorkspaceTabs
              activeView={exploreView}
              agentMemoryAvailable={agentMemoryAvailable}
              onSelect={switchExploreView}
            />
          }
        >
          <ErrorBoundary key={`explore-${exploreView}`}>
            <Suspense fallback={<WorkspaceFallback />}>
              {exploreView === 'graph' ? (
                <GraphWorkspace
                  externalFocusNodeId={graphFocusRequest?.nodeId}
                  externalFocusToken={graphFocusRequest?.token}
                  onDirtyChange={setExploreDraftDirty}
                />
              ) : exploreView === 'memories' ? <MemoryWorkspace onDirtyChange={setExploreDraftDirty} /> : <VocabularyWorkspace />}
            </Suspense>
          </ErrorBoundary>
        </WorkspaceShell>
      );
    }

    if (activeWorkspace === 'analyze') {
      return (
        <WorkspaceShell
          title="分析"
          subtitle="查询当前图谱并测试推理规则。"
          kicker={analyzeView === 'reasoning' ? '推理引擎' : 'SPARQL 查询'}
          tabs={
            <>
              <button className="workspace-tab" data-active={analyzeView === 'reasoning'} onClick={() => setAnalyzeView('reasoning')}>
                推理演练场
              </button>
              <button className="workspace-tab" data-active={analyzeView === 'sparql'} onClick={() => setAnalyzeView('sparql')}>
                SPARQL 查询
              </button>
            </>
          }
        >
          <ErrorBoundary key={`analyze-${analyzeView}`}>
            <Suspense fallback={<WorkspaceFallback />}>
              {analyzeView === 'reasoning' ? <ReasoningWorkspace /> : <SparqlWorkspace />}
            </Suspense>
          </ErrorBoundary>
        </WorkspaceShell>
      );
    }

    if (activeWorkspace === 'decisions') {
      return (
        <WorkspaceShell
          title="决策"
          subtitle="检查决策链、因果上下文与先例匹配。"
          kicker="决策智能"
        >
          <ErrorBoundary key="decisions">
            <Suspense fallback={<WorkspaceFallback />}>
              <DecisionWorkspace />
            </Suspense>
          </ErrorBoundary>
        </WorkspaceShell>
      );
    }

    if (activeWorkspace === 'enrich') {
      return (
        <WorkspaceShell
          title="数据增强"
          subtitle="导入、导出、对账与审计图谱实体。"
          kicker="知识审计"
          tabs={
            <>
              <button className="workspace-tab" data-active={enrichView === 'import'} onClick={() => setEnrichView('import')}>
                导入与导出
              </button>
              <button className="workspace-tab" data-active={enrichView === 'merge'} onClick={() => setEnrichView('merge')}>
                差异与合并
              </button>
              <button className="workspace-tab" data-active={enrichView === 'resolve'} onClick={() => setEnrichView('resolve')}>
                实体消解
              </button>
              <button className="workspace-tab" data-active={enrichView === 'registry'} onClick={() => setEnrichView('registry')}>
                注册表
              </button>
            </>
          }
        >
          <ErrorBoundary key={`enrich-${enrichView}`}>
            <Suspense fallback={<WorkspaceFallback />}>
              {enrichView === 'import' ? <ImportExportWorkspace /> :
               enrichView === 'merge' ? <DiffMergeWorkspace /> :
               enrichView === 'resolve' ? <EntityResolutionTab /> :
               <RegistryTab />}
            </Suspense>
          </ErrorBoundary>
        </WorkspaceShell>
      );
    }

    if (activeWorkspace === 'ontology-hub') {
      return (
        <WorkspaceShell
          title="本体中心"
          subtitle="加载、浏览、编辑并治理本体与词汇表。"
          kicker="模式治理"
          compact
        >
          <ErrorBoundary key="ontology-hub">
            <Suspense fallback={<WorkspaceFallback />}>
              <OntologyWorkspace
                onJumpToGraphNode={(nodeId: string) => {
                  setGraphFocusRequest({ nodeId, token: Date.now() });
                  setActiveWorkspace('explore');
                  setExploreView('graph');
                }}
              />
            </Suspense>
          </ErrorBoundary>
        </WorkspaceShell>
      );
    }

    return (
      <WorkspaceShell
        title="管理"
        subtitle="审查溯源、谱系、本体与治理上下文。"
        kicker="图谱治理"
        tabs={
          <>
            <button className="workspace-tab" data-active={manageView === 'lineage'} onClick={() => setManageView('lineage')}>
              PROV-O 谱系
            </button>
            <button className="workspace-tab" data-active={manageView === 'kg-overview'} onClick={() => setManageView('kg-overview')}>
              知识图谱总览
            </button>
            <button className="workspace-tab" data-active={manageView === 'ontology'} onClick={() => setManageView('ontology')}>
              本体摘要
            </button>
          </>
        }
      >
        <ErrorBoundary key={`manage-${manageView}`}>
          <Suspense fallback={<WorkspaceFallback />}>
            {manageView === 'lineage' ? <LineageDiagram /> :
             manageView === 'kg-overview' ? <KGOverviewTab /> :
             <OntologySummaryTab onOpenVocabularyBrowser={() => {
               setActiveWorkspace('explore');
               setExploreView('vocabulary');
             }} />}
          </Suspense>
        </ErrorBoundary>
      </WorkspaceShell>
    );
  };

  if (authState === 'checking') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: 14 }}>
        正在检查登录状态…
      </div>
    );
  }
  if (authState === 'login') {
    return (
      <LoginGate
        onAuthenticated={(user) => {
          setAuthUser(user);
          setAuthState('ready');
        }}
      />
    );
  }
  return (
    <QueryClientProvider client={queryClient}>
      <style>{shellStyles}</style>
      <div className="app-shell">
        <aside className="app-rail">
          <button className="brand-pill" title="COWIN 知识图谱" onClick={() => switchWorkspace('welcome')} style={{ cursor: 'pointer', border: '1px solid rgba(54, 110, 244,0.18)', padding: 0, background: 'transparent', overflow: 'hidden' }}>
            <img src="/favicon.png" alt="COWIN" width={34} height={34} style={{ display: 'block', borderRadius: 'inherit' }} />
          </button>
          {navItems.map(({ id, label, hint, icon: Icon }) => (
            <button
              key={id}
              className="nav-button"
              data-active={activeWorkspace === id}
              onClick={() => switchWorkspace(id)}
              title={hint}
            >
              <Icon size={20} />
              <span className="nav-label">{label}</span>
            </button>
          ))}
          {authUser ? (
            <button
              className="nav-button"
              onClick={handleLogout}
              title={"退出登录（" + authUser.username + "）"}
            >
              <LogOut size={20} />
              <span className="nav-label">退出登录</span>
            </button>
          ) : null}
        </aside>
        {renderWorkspace()}
      </div>
    </QueryClientProvider>
  );
}
