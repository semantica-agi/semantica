# Semantica Plugins (Community Guide)

Semantica ships a shared plugin bundle under `plugins/` with skills, agents, and hooks for knowledge graphs, context graphs, decision intelligence, reasoning, explainability, provenance, ontology, and export workflows.

This README is for community users who want to install or reuse the plugin package across Claude, Cursor, and Codex.

## Supported Platforms

- Claude Code
- Cursor
- Codex

## Prerequisites

1. Clone the repository:

```bash
git clone https://github.com/Hawksight-AI/semantica.git
cd semantica
```

2. Ensure the plugin bundle exists at:

```text
plugins/
  skills/
  agents/
  hooks/
  .claude-plugin/
  .cursor-plugin/
  .codex-plugin/
```

## Plugin Contents

- `skills/`: 17 domain skills (`causal`, `decision`, `explain`, `reason`, `temporal`, etc.)
- `agents/`: specialized agents (`decision-advisor`, `explainability`, `kg-assistant`)
- `hooks/hooks.json`: plugin hook configuration
- `.claude-plugin/plugin.json`: Claude manifest
- `.cursor-plugin/plugin.json`: Cursor manifest
- `.codex-plugin/plugin.json`: Codex manifest
- `*/marketplace.json`: local marketplace definitions

## Install and Use in Claude Code

### Local install (fastest)

From the repository root:

```bash
claude --plugin-dir ./plugins
```

If your Claude setup uses plugin commands in-session, use:

```bash
/plugin install ./plugins
```

### Install from a GitHub marketplace

Add a marketplace hosted in git:

```bash
/plugin marketplace add <owner>/semantica
```

Install Semantica from that marketplace:

```bash
/plugin install semantica@<marketplace-name>
```

### Verify in Claude

Run one of these in chat:

```text
/semantica:decision list
/semantica:explain decision <decision_id>
```

If the plugin is installed correctly, Claude should recognize the `/semantica:*` skills.

## Install and Use in Codex

1. Ensure your repo marketplace exists at `.agents/plugins/marketplace.json`.
2. Point the plugin entry `source.path` to `./plugins` (or your chosen plugin directory).
3. Restart Codex and install from the marketplace UI.

Codex manifest used by this bundle:

- `.codex-plugin/plugin.json`

### Verify in Codex

After install, run a Semantica skill command in chat, for example:

```text
/semantica:causal chain --subject <decision_id> --depth 3
```

## Install and Use in Cursor

Cursor reads plugin metadata from:

- `.cursor-plugin/plugin.json`
- `.cursor-plugin/marketplace.json`

If you maintain a team/community plugin repo, publish this `plugins/` directory and refresh/reinstall in Cursor Marketplace to pick up updates.

### Verify in Cursor

Try one of these commands:

```text
/semantica:reason deductive "IF Person(x) THEN Mortal(x)"
/semantica:visualize topology
```

## First Commands to Try

After installing on any platform, these are good smoke tests:

1. `/semantica:decision record <category> "<scenario>" "<reasoning>" <outcome> <confidence>`
2. `/semantica:decision list`
3. `/semantica:causal chain --subject <decision_id> --depth 3`
4. `/semantica:explain decision <decision_id>`
5. `/semantica:validate graph`

## Community Notes

- Keep plugin name/version/keywords updated in each manifest before publishing.
- Keep skill frontmatter consistent (`name` + `description`) for reliable discovery.
- For open-source sharing, include this folder as-is so skills, agents, and hooks remain bundled.
