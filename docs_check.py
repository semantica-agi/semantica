"""Mintlify docs integrity checker — run before merging any docs PR."""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from typing import Any, Callable, cast

DOCS = "docs"
ALL_MD: list[str] = glob.glob(f"{DOCS}/**/*.md", recursive=True)

failures: list[str] = []


def check(label: str) -> Callable[[Callable[[], list[str]]], None]:
    """Decorator: run a check function, print result, collect failures."""
    def decorator(fn: Callable[[], list[str]]) -> None:
        issues = fn()
        if issues:
            print(f"FAIL  {label}")
            for msg in issues:
                print(f"      - {msg}")
            failures.extend(issues)
        else:
            print(f"pass  {label}")
    return decorator


def read(path: str) -> str:
    return open(path, encoding="utf-8").read()


# ── 1. docs.json is valid JSON ────────────────────────────────────────────────
@check("docs.json is valid JSON")
def _() -> list[str]:
    try:
        json.loads(read(f"{DOCS}/docs.json"))
        return []
    except Exception as e:
        return [str(e)]


# ── 2. Every nav page exists on disk ─────────────────────────────────────────
@check("All nav pages exist on disk")
def _() -> list[str]:
    cfg: Any = json.loads(read(f"{DOCS}/docs.json"))

    def nav_pages(obj: Any) -> list[str]:
        """Recursively collect strings from 'pages' arrays only."""
        result: list[str] = []
        if isinstance(obj, dict):
            d = cast(dict[str, Any], obj)
            for page in cast(list[Any], d.get("pages", [])):
                if isinstance(page, str):
                    result.append(page)
                else:
                    result.extend(nav_pages(page))
            for v in d.values():
                if isinstance(v, (dict, list)):
                    result.extend(nav_pages(v))
        elif isinstance(obj, list):
            for item in cast(list[Any], obj):
                result.extend(nav_pages(item))
        return result

    return [
        f"missing: {p}"
        for p in set(nav_pages(cfg))
        if not p.startswith("http") and not os.path.exists(f"{DOCS}/{p}.md")
    ]


# ── 3. Internal Card hrefs resolve ───────────────────────────────────────────
@check("All internal Card hrefs resolve")
def _() -> list[str]:
    issues: list[str] = []
    for fpath in ALL_MD:
        for m in re.finditer(r'href=["\'](?!http)([^"\'#]+)["\']', read(fpath)):
            href = m.group(1).strip()
            target = os.path.normpath(os.path.join(os.path.dirname(fpath), href)) + ".md"
            if not os.path.exists(target):
                issues.append(f"{fpath}: href '{href}'")
    return issues


# ── 4. No stale repo URLs ─────────────────────────────────────────────────────
@check("No stale repo URLs")
def _() -> list[str]:
    stale = ["Hawksight-AI/semantica", "semantica-dev/semantica"]
    files = ALL_MD + [f"{DOCS}/docs.json"]
    return [
        f"{f}: '{pat}'"
        for f in files
        for pat in stale
        if pat in read(f)
    ]


# ── 5. All reference pages have frontmatter ───────────────────────────────────
@check("All reference pages have frontmatter")
def _() -> list[str]:
    return [
        os.path.basename(f)
        for f in glob.glob(f"{DOCS}/reference/*.md")
        if not read(f).startswith("---")
    ]


# ── 6. No known-wrong class names ────────────────────────────────────────────
@check("No known-wrong class names in reference pages")
def _() -> list[str]:
    banned: list[tuple[str, str]] = [
        (r"\bBaseIngestor\b",    "docs/architecture.md"),
        (r"\bBaseExtractor\b",   "docs/architecture.md"),
        (r"\bBasePlugin\b",      "docs/architecture.md"),
        (r"\bDataNormalizer\b",  "docs/reference/normalize.md"),
        (r"\bEntityResolver\b",  "docs/reference/deduplication.md"),
        (r"\bDeductiveEngine\b", "docs/reference/reasoning.md"),
        (r"\bAbductiveEngine\b", "docs/reference/reasoning.md"),
        (r"\bGraphMLExporter\b", "docs/reference/export.md"),
        (r"\bArangoExporter\b(?!.*AQL)",                        "docs/reference/export.md"),
        (r"(?<!Temporal)(?<!Graph)\bReasoningEngine\b",         "docs/reference/reasoning.md"),
    ]
    return [
        f"{fpath}: '{pat}'"
        for pat, fpath in banned
        if os.path.exists(fpath) and re.search(pat, read(fpath))
    ]


# ── 7. No Python 3.9+ type syntax in code blocks ─────────────────────────────
@check("No Python 3.9+ type syntax in code blocks (3.8 compat)")
def _() -> list[str]:
    issues: list[str] = []
    for fpath in ALL_MD:
        in_block = False
        for i, line in enumerate(open(fpath, encoding="utf-8"), 1):
            if line.strip().startswith("```"):
                in_block = not in_block
            if in_block and re.search(r":\s*(list|dict|tuple|set)\[", line):
                issues.append(f"{fpath}:{i}: {line.rstrip()}")
    return issues


# ── 8. index.md covers all 27 modules ────────────────────────────────────────
@check("All 27 modules present in index.md")
def _() -> list[str]:
    modules = [
        "semantica.ingest", "semantica.parse", "semantica.split", "semantica.normalize",
        "semantica.semantic_extract", "semantica.kg", "semantica.ontology", "semantica.reasoning",
        "semantica.embeddings", "semantica.vector_store", "semantica.graph_store",
        "semantica.triplet_store", "semantica.context", "semantica.provenance",
        "semantica.change_management", "semantica.deduplication", "semantica.conflicts",
        "semantica.export", "semantica.visualization", "semantica.pipeline", "semantica.seed",
        "semantica.llms", "semantica.mcp_server", "semantica.explorer", "semantica.evals",
        "semantica.utils", "semantica.core",
    ]
    index = read(f"{DOCS}/index.md")
    return [m for m in modules if m not in index]


# ── Summary ───────────────────────────────────────────────────────────────────
print()
if failures:
    print(f"FAILED  {len(failures)} issue(s) found")
    sys.exit(1)
else:
    print("All checks passed")
