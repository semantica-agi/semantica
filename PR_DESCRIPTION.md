# PR: Explorer Welcome Message, Version Bump & Plugin README Overhaul

**Branch:** `utils` → `main`
**Version:** `0.3.0` → `0.4.0`

---

## Summary

This PR delivers three focused changes:

1. **Explorer root welcome endpoint** — `GET /` on the backend API now returns a structured welcome response instead of `{"detail": "Not Found"}`.
2. **Version bump to 0.4.0** — `semantica/__init__.py` synced with `pyproject.toml`.
3. **Plugin README overhaul** — All 8 platform plugin READMEs updated to reflect v0.4.0, the Knowledge Explorer, and corrected skill/tool counts.

---

## Changes

### `semantica/explorer/app.py`
- Added `GET /` route returning a JSON welcome message with `message`, `version`, `ui`, and `docs` fields.
- Replaces the unhelpful 404 that users saw when hitting the backend root directly.

### `semantica/__init__.py`
- Bumped `__version__` from `"0.3.0"` to `"0.4.0"` to match `pyproject.toml`.

### Plugin READMEs (6 files)

#### `plugins/.claude-plugin/README.md` (main community guide)
- Full rewrite with a numbered platform table covering all **8 plugins**.
- Annotated `plugins/` directory tree.
- Dedicated **Knowledge Explorer** section listing all dashboard tabs (Graph, Decisions, Reasoning, SPARQL, Vocabulary, Lineage, Import/Export).
- Per-platform install + verify steps for every supported tool.

#### `plugins/.cline-plugin/README.md`
- Added v0.4.0 badge and Knowledge Explorer section.
- Fixed tool count: `12` → `17`.
- Python requirement: `3.8+` → `3.10+`.

#### `plugins/.continue-plugin/README.md`
- Added v0.4.0 badge and Knowledge Explorer section.
- Updated tool count to 17.
- Python requirement: `3.8+` → `3.10+`.

#### `plugins/.windsurf-plugin/README.md`
- Added v0.4.0 badge and Knowledge Explorer section.
- Fixed tool count: `12` → `17`.
- Added full skills list as inline tags.
- Python requirement: `3.8+` → `3.10+`.

#### `plugins/.openclaw-plugin/README.md`
- Added v0.4.0 badge.
- Fixed tool/agent count: `12 tools and 3 resources` → `17 tools and 3 agents`.
- Python requirement: `3.8+` → `3.10+`.

#### `plugins/.vscode-plugin/README.md`
- Added v0.4.0 badge and Knowledge Explorer section.
- Updated tool description to 17 skills and 3 agents.
- Python requirement: `3.8+` → `3.10+`.

---

## Files Changed

| File | Change |
|------|--------|
| `semantica/__init__.py` | Version `0.3.0` → `0.4.0` |
| `semantica/explorer/app.py` | Added `GET /` welcome route |
| `plugins/.claude-plugin/README.md` | Full rewrite — 8 plugins, Explorer, install guide |
| `plugins/.cline-plugin/README.md` | v0.4.0 badge, Explorer, fix tool count |
| `plugins/.continue-plugin/README.md` | v0.4.0 badge, Explorer, fix tool count |
| `plugins/.windsurf-plugin/README.md` | v0.4.0 badge, Explorer, fix tool count |
| `plugins/.openclaw-plugin/README.md` | v0.4.0 badge, fix agent count |
| `plugins/.vscode-plugin/README.md` | v0.4.0 badge, Explorer section |
| `explorer/package-lock.json` | Updated after `npm install` |

---

## Testing

- Backend: `GET http://localhost:8000/` returns `{"message": "Welcome to Semantica Knowledge Explorer", "version": "0.4.0", ...}`
- Frontend: `http://localhost:5174` serves the full Explorer UI (Graph, Decisions, Reasoning, SPARQL, Vocabulary, Lineage, Import/Export tabs)
- Graph loaded: 425 nodes, 896 edges (Threat Intelligence KG)

---

## Checklist

- [x] Version bumped in `__init__.py` and matches `pyproject.toml`
- [x] Welcome route added and verified
- [x] All 8 platform plugin READMEs updated
- [x] Skill count consistent (17) across all READMEs
- [x] Python requirement updated to 3.10+ across all READMEs
- [x] No changes to `main` branch
