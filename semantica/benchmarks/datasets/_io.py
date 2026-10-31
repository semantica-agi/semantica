"""Small file-reading helpers shared by the dataset loaders.

Every loader reads a local file the user downloaded themselves — the harness
never fetches datasets over the network, because the benchmark suites have
different licences (see each loader's docstring) and shipping bytes would
re-distribute them.
"""

import json
from pathlib import Path
from typing import Any, Iterator, Union

PathLike = Union[str, Path]


def read_json(path: PathLike) -> Any:
    """Parse a JSON file, or raise ``FileNotFoundError`` with a useful hint."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"dataset file not found: {p}. Download it yourself and pass the "
            f"local path; the harness does not fetch datasets."
        )
    with p.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: PathLike) -> Iterator[dict]:
    """Yield one parsed object per non-blank line of a JSON Lines file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"dataset file not found: {p}. Download it yourself and pass the "
            f"local path; the harness does not fetch datasets."
        )
    with p.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{p}:{lineno}: invalid JSON ({exc})") from exc


def as_list(value: Any) -> list:
    """Coerce ``None`` to ``[]`` and a bare string to a one-element list.

    Upstream datasets are inconsistent about singular vs plural answer fields
    (``answer`` vs ``answers``) and about wrapping, so normalizing here keeps
    every loader from repeating the same three-branch dance.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def as_answers(*values: Any) -> list:
    """Collect non-blank gold answers from one or more upstream fields.

    Upstream files occasionally carry an empty ``answer`` string or a blank
    alias. Those must not become a case: an empty gold would make every
    prediction score zero and quietly poison the aggregate. Order is preserved
    and duplicates are dropped, so the first field listed wins.
    """
    out: list = []
    for value in values:
        for item in as_list(value):
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
    return out
