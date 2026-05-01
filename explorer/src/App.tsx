import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  ArrowRight,
  BrainCircuit,
  Database,
  FileSearch,
  GitBranchPlus,
  GitMerge,
  Network,
  Radar,
  Route,
  Scale,
  Search,
  Settings2,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';

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
const OntologyWorkspace = lazy(() => import('./workspaces/OntologyWorkspace').then((module) => ({ default: module.OntologyWorkspace })));

type WorkspaceId = 'welcome' | 'explore' | 'analyze' | 'decisions' | 'enrich' | 'manage' | 'ontology-hub';
type ExploreView = 'graph' | 'vocabulary';
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

const queryClient = new QueryClient();

const PREVIEW_DOTS = Array.from({ length: 42 }, (_, i) => ({
  cx: 170 + ((i * 73) % 330),
  cy: 170 + ((i * 47) % 210),
  r: 2 + (i % 3),
  fill: (['#56d364', '#58a6ff', '#f2b66d', '#ff9daf'] as const)[i % 4],
}));

const navItems: NavItem[] = [
  { id: 'explore', label: 'Knowledge Explorer', hint: 'Graph and vocabulary browsing', icon: Database },
  { id: 'analyze', label: 'Analyze', hint: 'Query and inspect the dataset', icon: FileSearch },
  { id: 'decisions', label: 'Decisions', hint: 'Decision chains and precedent review', icon: Scale },
  { id: 'enrich', label: 'Enrich', hint: 'Import, export, and merge workflows', icon: GitBranchPlus },
  { id: 'manage', label: 'Manage', hint: 'Lineage and governance tooling', icon: Settings2 },
  { id: 'ontology-hub', label: 'Ontology Hub', hint: 'Schema governance, registry, and vocabulary management', icon: GitMerge },
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

  .landing-page {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: clamp(22px, 3vw, 42px);
    background:
      linear-gradient(108deg, rgba(18, 29, 38, 0.4) 0%, rgba(6, 12, 20, 0.72) 42%, rgba(4, 8, 14, 0.92) 100%),
      linear-gradient(180deg, rgba(11, 19, 28, 0.9) 0%, rgba(3, 7, 12, 0.98) 100%);
  }

  .landing-page::before {
    content: "";
    position: fixed;
    inset: 0 0 0 88px;
    pointer-events: none;
    opacity: 0.5;
    background:
      linear-gradient(116deg, transparent 0 18%, rgba(126, 160, 176, 0.045) 18.2%, transparent 18.6% 40%, rgba(201, 164, 104, 0.035) 40.2%, transparent 40.6%),
      repeating-linear-gradient(164deg, rgba(141, 171, 183, 0.032) 0 1px, transparent 1px 56px),
      repeating-linear-gradient(24deg, rgba(141, 171, 183, 0.018) 0 1px, transparent 1px 116px);
    mask-image: linear-gradient(90deg, transparent 0%, black 18%, black 82%, transparent 100%);
  }

  .landing-page::after {
    content: "";
    position: fixed;
    inset: 0 0 0 88px;
    pointer-events: none;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 18%),
      radial-gradient(ellipse at 50% 32%, transparent 0 44%, rgba(0, 0, 0, 0.34) 100%),
      linear-gradient(90deg, rgba(0, 0, 0, 0.34), transparent 18%, transparent 76%, rgba(0, 0, 0, 0.36));
    opacity: 0.82;
  }

  .landing-shell {
    position: relative;
    z-index: 1;
    width: min(1480px, 100%);
    min-height: 100%;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .landing-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.02fr) minmax(420px, 0.98fr);
    gap: clamp(22px, 3vw, 42px);
    align-items: stretch;
    min-height: min(680px, calc(100vh - 108px));
  }

  .landing-copy {
    padding: clamp(22px, 3vw, 42px);
    border: 1px solid rgba(158, 217, 255, 0.14);
    border-radius: 34px;
    background:
      linear-gradient(145deg, rgba(9, 17, 25, 0.92), rgba(4, 8, 14, 0.7)),
      linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 42%);
    box-shadow: 0 34px 90px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    backdrop-filter: blur(20px);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 34px;
  }

  .landing-kicker {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    width: fit-content;
    min-height: 28px;
    padding: 0 11px 0 9px;
    border-radius: 999px;
    border: 1px solid rgba(141, 232, 211, 0.14);
    background: rgba(4, 18, 23, 0.56);
    color: #9ee8d7;
    font: 800 11px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.075em;
    text-transform: uppercase;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
  }

  .landing-kicker-mark {
    position: relative;
    width: 15px;
    height: 15px;
    flex: 0 0 auto;
  }

  .landing-kicker-mark::before,
  .landing-kicker-mark::after {
    content: "";
    position: absolute;
    height: 1px;
    border-radius: 999px;
    background: rgba(148, 229, 211, 0.62);
    transform-origin: left center;
  }

  .landing-kicker-mark::before {
    width: 10px;
    left: 3px;
    top: 5px;
    transform: rotate(34deg);
  }

  .landing-kicker-mark::after {
    width: 9px;
    left: 3px;
    top: 10px;
    transform: rotate(-28deg);
  }

  .landing-kicker-node {
    position: absolute;
    width: 5px;
    height: 5px;
    border-radius: 999px;
    background: #8de8d3;
    border: 1px solid rgba(10, 34, 38, 0.88);
    box-shadow: 0 0 10px rgba(141, 232, 211, 0.22);
  }

  .landing-kicker-node:nth-child(1) {
    left: 0;
    top: 4px;
  }

  .landing-kicker-node:nth-child(2) {
    right: 0;
    top: 0;
  }

  .landing-kicker-node:nth-child(3) {
    right: 1px;
    bottom: 0;
  }

  .landing-title {
    max-width: 820px;
    margin: 24px 0 0;
    color: #f3f8ff;
    font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
    font-size: clamp(50px, 6.3vw, 104px);
    line-height: 0.86;
    letter-spacing: -0.085em;
  }

  .landing-title span {
    color: transparent;
    background: linear-gradient(120deg, #eaf5ff 0%, #91e6ff 34%, #a7f3d0 62%, #f5c982 100%);
    -webkit-background-clip: text;
    background-clip: text;
  }

  .landing-subtitle {
    max-width: 720px;
    margin: 22px 0 0;
    color: #a9bdd5;
    font-size: clamp(15px, 1.35vw, 19px);
    line-height: 1.75;
  }

  .landing-launcher {
    display: grid;
    grid-template-columns: minmax(240px, 0.95fr) minmax(280px, 1.05fr);
    gap: 12px;
    margin-top: 30px;
    padding: 12px;
    border: 1px solid rgba(158, 217, 255, 0.12);
    border-radius: 28px;
    background:
      linear-gradient(145deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.018)),
      rgba(0, 0, 0, 0.14);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .landing-launcher-primary,
  .landing-launcher-item {
    border: 1px solid transparent;
    text-align: left;
    cursor: pointer;
    color: #f7fbff;
    transition: transform 160ms ease, border-color 160ms ease, background 160ms ease, box-shadow 160ms ease;
  }

  .landing-launcher-primary {
    position: relative;
    overflow: hidden;
    min-height: 154px;
    padding: 18px;
    border-radius: 22px;
    background:
      radial-gradient(circle at 18% 18%, rgba(169, 246, 219, 0.22), transparent 34%),
      linear-gradient(135deg, rgba(72, 211, 194, 0.34), rgba(73, 155, 255, 0.22)),
      rgba(8, 23, 32, 0.74);
    border-color: rgba(141, 232, 211, 0.28);
    box-shadow: 0 16px 42px rgba(72, 211, 194, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.12);
  }

  .landing-launcher-primary::after {
    content: "";
    position: absolute;
    width: 160px;
    height: 160px;
    right: -70px;
    bottom: -86px;
    border-radius: 999px;
    border: 1px solid rgba(169, 246, 219, 0.18);
    box-shadow: 0 0 0 18px rgba(88, 166, 255, 0.035), 0 0 0 42px rgba(88, 166, 255, 0.025);
  }

  .landing-launcher-primary:hover,
  .landing-launcher-item:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.25);
  }

  .landing-launcher-primary-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .landing-launcher-icon {
    width: 42px;
    height: 42px;
    display: grid;
    place-items: center;
    border-radius: 16px;
    color: #a9f6db;
    background: rgba(169, 246, 219, 0.12);
    border: 1px solid rgba(169, 246, 219, 0.18);
  }

  .landing-launcher-arrow {
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    border-radius: 999px;
    color: #f7fbff;
    background: rgba(255, 255, 255, 0.11);
  }

  .landing-launcher-eyebrow {
    margin-top: 18px;
    color: #a5f7d6;
    font: 800 10px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .landing-launcher-title {
    margin-top: 8px;
    color: #f3f8ff;
    font: 800 24px/1 "Space Grotesk", sans-serif;
    letter-spacing: -0.05em;
  }

  .landing-launcher-copy {
    margin-top: 10px;
    max-width: 36ch;
    color: #b4c9df;
    font-size: 13px;
    line-height: 1.55;
  }

  .landing-launcher-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .landing-launcher-item {
    min-height: 72px;
    border-radius: 18px;
    padding: 12px;
    display: flex;
    align-items: center;
    gap: 11px;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.052), rgba(255, 255, 255, 0.022)),
      rgba(1, 8, 15, 0.42);
    border-color: rgba(158, 217, 255, 0.1);
  }

  .landing-launcher-item-icon {
    width: 34px;
    height: 34px;
    flex: 0 0 auto;
    display: grid;
    place-items: center;
    border-radius: 13px;
    color: #9be8ff;
    background: rgba(91, 214, 255, 0.08);
    border: 1px solid rgba(91, 214, 255, 0.14);
  }

  .landing-launcher-item-title {
    color: #e9f3ff;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: -0.02em;
  }

  .landing-launcher-item-copy {
    margin-top: 4px;
    color: #829ab7;
    font-size: 11px;
    line-height: 1.35;
  }

  .landing-metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }

  .landing-metric {
    min-height: 88px;
    padding: 14px;
    border-radius: 22px;
    border: 1px solid rgba(158, 217, 255, 0.11);
    background: rgba(0, 0, 0, 0.18);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .landing-metric-value {
    color: #eff8ff;
    font: 800 24px/1 "Space Grotesk", sans-serif;
    letter-spacing: -0.05em;
  }

  .landing-metric[data-tone='mint'] .landing-metric-value { color: #9ff6cf; }
  .landing-metric[data-tone='amber'] .landing-metric-value { color: #ffd18f; }
  .landing-metric[data-tone='rose'] .landing-metric-value { color: #ffb1be; }
  .landing-metric[data-tone='cyan'] .landing-metric-value { color: #9be8ff; }

  .landing-metric-label {
    margin-top: 8px;
    color: #829ab7;
    font-size: 12px;
    font-weight: 700;
  }

  .landing-preview {
    position: relative;
    overflow: hidden;
    min-height: 560px;
    border-radius: 34px;
    border: 1px solid rgba(158, 217, 255, 0.16);
    background:
      radial-gradient(circle at 50% 42%, rgba(80, 210, 159, 0.16), transparent 24%),
      radial-gradient(circle at 72% 28%, rgba(255, 179, 109, 0.13), transparent 26%),
      linear-gradient(145deg, rgba(9, 19, 32, 0.92), rgba(4, 9, 16, 0.7));
    box-shadow: 0 34px 90px rgba(0, 0, 0, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  }

  .landing-preview-orbit {
    position: absolute;
    inset: 34px;
    border-radius: 42px;
    opacity: 0.9;
  }

  .landing-preview-orbit svg {
    width: 100%;
    height: 100%;
    overflow: visible;
  }

  .landing-preview-line {
    stroke: rgba(116, 211, 255, 0.34);
    stroke-width: 1.4;
    fill: none;
  }

  .landing-preview-line--warm {
    stroke: rgba(255, 192, 115, 0.34);
  }

  .landing-node {
    transform-origin: center;
    animation: landing-float 7s ease-in-out infinite;
  }

  .landing-node:nth-child(2n) {
    animation-delay: -2.2s;
  }

  .landing-command-card,
  .landing-dossier-card,
  .landing-timeline-card {
    position: absolute;
    border: 1px solid rgba(158, 217, 255, 0.16);
    background: rgba(2, 8, 15, 0.72);
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(18px);
  }

  .landing-command-card {
    top: 28px;
    left: 28px;
    right: 28px;
    min-height: 68px;
    border-radius: 22px;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .landing-command-icon {
    width: 38px;
    height: 38px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    color: #9ff6cf;
    background: rgba(92, 230, 177, 0.12);
    border: 1px solid rgba(92, 230, 177, 0.18);
  }

  .landing-command-label {
    color: #f3f8ff;
    font-size: 14px;
    font-weight: 800;
  }

  .landing-command-meta {
    margin-top: 4px;
    color: #829ab7;
    font: 600 11px/1 "JetBrains Mono", monospace;
  }

  .landing-dossier-card {
    right: 28px;
    bottom: 116px;
    width: min(280px, calc(100% - 56px));
    border-radius: 26px;
    padding: 18px;
  }

  .landing-dossier-kicker {
    color: #89f7c9;
    font: 800 11px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .landing-dossier-title {
    margin-top: 10px;
    color: #f3f8ff;
    font: 800 26px/1 "Space Grotesk", sans-serif;
    letter-spacing: -0.05em;
  }

  .landing-dossier-row {
    margin-top: 14px;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    color: #9fb2ca;
    font-size: 12px;
  }

  .landing-dossier-row strong {
    color: #ffd18f;
  }

  .landing-timeline-card {
    left: 28px;
    right: 28px;
    bottom: 28px;
    border-radius: 22px;
    padding: 14px;
  }

  .landing-timeline-track {
    position: relative;
    height: 6px;
    border-radius: 999px;
    background: rgba(158, 217, 255, 0.12);
    overflow: hidden;
  }

  .landing-timeline-track::after {
    content: "";
    position: absolute;
    inset: 0 34% 0 0;
    border-radius: inherit;
    background: linear-gradient(90deg, #56d364, #58a6ff, #f2b66d);
  }

  .landing-timeline-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 10px;
    color: #829ab7;
    font: 700 11px/1 "JetBrains Mono", monospace;
  }

  .landing-capability-band {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    padding: 14px;
    border: 1px solid rgba(158, 217, 255, 0.12);
    border-radius: 30px;
    background: rgba(3, 9, 17, 0.54);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    backdrop-filter: blur(18px);
  }

  .landing-capability-label {
    color: #f3f8ff;
    font: 800 12px/1 "JetBrains Mono", monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-right: 6px;
  }

  .landing-capability {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 34px;
    padding: 0 11px;
    border-radius: 999px;
    color: #b7cbe4;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(158, 217, 255, 0.11);
    font-size: 12px;
    font-weight: 800;
  }

  @keyframes landing-float {
    0%, 100% { transform: translateY(0) scale(1); }
    50% { transform: translateY(-7px) scale(1.04); }
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

    .landing-hero {
      grid-template-columns: 1fr;
      min-height: auto;
    }

    .landing-preview {
      min-height: 520px;
    }

    .landing-launcher {
      grid-template-columns: 1fr;
    }

    .landing-metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 680px) {
    .app-rail {
      width: 72px;
      padding: 14px 9px;
    }

    .landing-page {
      padding: 16px;
    }

    .landing-page::before {
      inset: 0 0 0 72px;
    }

    .landing-page::after {
      inset: 0 0 0 72px;
    }

    .landing-copy {
      padding: 22px;
      border-radius: 26px;
    }

    .landing-title {
      font-size: clamp(42px, 15vw, 64px);
    }

    .landing-launcher-grid,
    .landing-metrics {
      grid-template-columns: 1fr;
    }

    .landing-preview {
      min-height: 460px;
    }

    .landing-dossier-card {
      left: 28px;
      width: auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .landing-node,
    .landing-launcher-primary,
    .landing-launcher-item {
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
  const [stats, setStats] = useState<{ nodes: number | null; edges: number | null; ready: boolean }>({
    nodes: null,
    edges: null,
    ready: false,
  });

  useEffect(() => {
    const controller = new AbortController();

    fetch('/api/graph/stats', { signal: controller.signal })
      .then((response) => (response.ok ? response.json() as Promise<GraphStatsPayload> : null))
      .then((payload) => {
        if (!payload) {
          setStats((current) => ({ ...current, ready: false }));
          return;
        }

        setStats({
          nodes: getNumberStat(payload, ['node_count', 'nodeCount', 'nodes']),
          edges: getNumberStat(payload, ['edge_count', 'edgeCount', 'edges']),
          ready: true,
        });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        setStats((current) => ({ ...current, ready: false }));
      });

    return () => controller.abort();
  }, []);

  const metrics: LandingMetric[] = [
    { label: 'Knowledge nodes', value: formatMetric(stats.nodes, 'Live'), tone: 'cyan' },
    { label: 'Relationships mapped', value: formatMetric(stats.edges, 'Ready'), tone: 'mint' },
    { label: 'Graph modes', value: '3', tone: 'amber' },
    { label: stats.ready ? 'Dataset online' : 'Ready to explore', value: stats.ready ? 'Active' : 'Standby', tone: 'rose' },
  ];

  const secondaryLaunchers: LandingAction[] = [
    {
      label: 'Vocabulary',
      description: 'Schemes and terms',
      icon: Database,
      onClick: onOpenVocabulary,
    },
    {
      label: 'Analyze',
      description: 'Inference and queries',
      icon: BrainCircuit,
      onClick: onOpenReasoning,
    },
    {
      label: 'Decisions',
      description: 'Chains and precedents',
      icon: Scale,
      onClick: onOpenDecisions,
    },
    {
      label: 'Enrich',
      description: 'Import and resolve',
      icon: GitBranchPlus,
      onClick: onOpenImport,
    },
    {
      label: 'Manage',
      description: 'Lineage and ontology',
      icon: ShieldCheck,
      onClick: onOpenManage,
    },
  ];

  return (
    <main className="landing-page">
      <div className="landing-shell">
        <section className="landing-hero">
          <div className="landing-copy">
            <div>
              <div className="landing-kicker">
                <span className="landing-kicker-mark" aria-hidden="true">
                  <span className="landing-kicker-node" />
                  <span className="landing-kicker-node" />
                  <span className="landing-kicker-node" />
                </span>
                Semantic Intelligence System
              </div>
              <h1 className="landing-title">
                Explore knowledge like a <span>living system.</span>
              </h1>
              <p className="landing-subtitle">
                Semantica turns dense knowledge graphs into a navigable command center for discovery,
                reasoning, provenance, distance intelligence, and decision context.
              </p>
              <div className="landing-launcher" aria-label="Workspace launcher">
                <button className="landing-launcher-primary" type="button" onClick={onOpenNetwork}>
                  <div className="landing-launcher-primary-top">
                    <div className="landing-launcher-icon">
                      <Network size={21} />
                    </div>
                    <div className="landing-launcher-arrow">
                      <ArrowRight size={18} />
                    </div>
                  </div>
                  <div className="landing-launcher-eyebrow">Primary workspace</div>
                  <div className="landing-launcher-title">Start in Network Explorer</div>
                  <div className="landing-launcher-copy">
                    Enter the full graph, grouped communities, focused neighborhoods, and distance intelligence.
                  </div>
                </button>

                <div className="landing-launcher-grid">
                  {secondaryLaunchers.map((launcher) => {
                    const Icon = launcher.icon;
                    return (
                      <button
                        key={launcher.label}
                        className="landing-launcher-item"
                        type="button"
                        onClick={launcher.onClick}
                      >
                        <div className="landing-launcher-item-icon">
                          <Icon size={16} />
                        </div>
                        <div>
                          <div className="landing-launcher-item-title">{launcher.label}</div>
                          <div className="landing-launcher-item-copy">{launcher.description}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="landing-metrics" aria-label="Semantica live status">
              {metrics.map((metric) => (
                <div key={metric.label} className="landing-metric" data-tone={metric.tone}>
                  <div className="landing-metric-value">{metric.value}</div>
                  <div className="landing-metric-label">{metric.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="landing-preview" aria-label="Knowledge graph product preview">
            <div className="landing-command-card">
              <div className="landing-command-icon">
                <Search size={18} />
              </div>
              <div>
                <div className="landing-command-label">Search command, node, or concept</div>
                <div className="landing-command-meta">distance heatmap · focused view · causal path</div>
              </div>
            </div>
            <div className="landing-preview-orbit">
              <svg viewBox="0 0 640 540" role="img" aria-hidden="true">
                <path className="landing-preview-line" d="M122 340 C220 120 404 100 516 268" />
                <path className="landing-preview-line landing-preview-line--warm" d="M130 210 C246 290 384 202 514 372" />
                <path className="landing-preview-line" d="M178 408 C284 220 402 238 498 164" />
                <path className="landing-preview-line landing-preview-line--warm" d="M214 138 C328 360 418 398 536 304" />
                <g className="landing-node">
                  <circle cx="122" cy="340" r="11" fill="#56d364" />
                  <circle cx="122" cy="340" r="22" fill="none" stroke="rgba(86,211,100,0.22)" />
                </g>
                <g className="landing-node">
                  <circle cx="214" cy="138" r="8" fill="#58a6ff" />
                  <circle cx="214" cy="138" r="18" fill="none" stroke="rgba(88,166,255,0.2)" />
                </g>
                <g className="landing-node">
                  <circle cx="516" cy="268" r="14" fill="#f2b66d" />
                  <circle cx="516" cy="268" r="28" fill="none" stroke="rgba(242,182,109,0.24)" />
                </g>
                <g className="landing-node">
                  <circle cx="498" cy="164" r="7" fill="#ff9daf" />
                  <circle cx="498" cy="164" r="15" fill="none" stroke="rgba(255,157,175,0.2)" />
                </g>
                <g className="landing-node">
                  <circle cx="514" cy="372" r="10" fill="#7fd0ff" />
                  <circle cx="514" cy="372" r="22" fill="none" stroke="rgba(127,208,255,0.2)" />
                </g>
                <g opacity="0.68">
                  {PREVIEW_DOTS.map((dot, index) => (
                    <circle key={index} cx={dot.cx} cy={dot.cy} r={dot.r} fill={dot.fill} />
                  ))}
                </g>
              </svg>
            </div>
            <div className="landing-dossier-card">
              <div className="landing-dossier-kicker">Entity dossier</div>
              <div className="landing-dossier-title">NSRP1</div>
              <div className="landing-dossier-row">
                <span>Distance band</span>
                <strong>Near</strong>
              </div>
              <div className="landing-dossier-row">
                <span>Path coherence</span>
                <strong>0.84</strong>
              </div>
              <div className="landing-dossier-row">
                <span>Provenance</span>
                <strong>Audited</strong>
              </div>
            </div>
            <div className="landing-timeline-card">
              <div className="landing-timeline-track" />
              <div className="landing-timeline-labels">
                <span>1970</span>
                <span>Temporal evidence</span>
                <span>2030</span>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-capability-band" aria-label="Intelligence capabilities">
          <div className="landing-capability-label">Intelligence layer</div>
          <div className="landing-capability"><Radar size={14} />Distance Heatmap</div>
          <div className="landing-capability"><Network size={14} />Focused Neighborhood</div>
          <div className="landing-capability"><GitMerge size={14} />Grouped Communities</div>
          <div className="landing-capability"><Route size={14} />Trace Causal Path</div>
          <div className="landing-capability"><ShieldCheck size={14} />Provenance Dossier</div>
        </section>

      </div>
    </main>
  );
}

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>('welcome');
  const [exploreView, setExploreView] = useState<ExploreView>('graph');
  const [analyzeView, setAnalyzeView] = useState<AnalyzeView>('reasoning');
  const [enrichView, setEnrichView] = useState<EnrichView>('import');
  const [manageView, setManageView] = useState<ManageView>('lineage');
  const [graphFocusRequest, setGraphFocusRequest] = useState<{ nodeId: string; token: number } | null>(null);


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
            {exploreView === 'graph' ? (
              <GraphWorkspace
                externalFocusNodeId={graphFocusRequest?.nodeId}
                externalFocusToken={graphFocusRequest?.token}
              />
            ) : <VocabularyWorkspace />}
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

    if (activeWorkspace === 'ontology-hub') {
      return (
        <WorkspaceShell
          title="Ontology Hub"
          subtitle="Load, browse, edit, and govern ontologies and vocabularies."
          kicker="Schema Governance"
          compact
        >
          <Suspense fallback={<WorkspaceFallback />}>
            <OntologyWorkspace
              onJumpToGraphNode={(nodeId: string) => {
                setGraphFocusRequest({ nodeId, token: Date.now() });
                setActiveWorkspace('explore');
                setExploreView('graph');
              }}
            />
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
