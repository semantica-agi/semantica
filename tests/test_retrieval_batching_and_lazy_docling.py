"""Tests for batched ranking embeddings and the deferred docling import."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from semantica.context.context_retriever import ContextRetriever, RetrievedContext
from semantica.parse import docling_parser


class _Store:
    def __init__(self, batch_result=None):
        self.single_calls = []
        self.batch_calls = []
        self._batch_result = batch_result

    def embed(self, text):
        self.single_calls.append(text)
        return np.array([1.0, float(len(text))])

    def embed_batch(self, texts):
        self.batch_calls.append(list(texts))
        if isinstance(self._batch_result, Exception):
            raise self._batch_result
        if self._batch_result is not None:
            return self._batch_result
        return [np.array([1.0, float(len(text))]) for text in texts]


def _rank(store):
    results = [
        RetrievedContext(content=text, score=0.5, source=f"vector:{text}")
        for text in ("a", "bbb", "cc")
    ]
    ranked = ContextRetriever(vector_store=store)._rank_and_merge(results, "query")
    return [(item.content, round(float(item.score), 6)) for item in ranked]


def test_ranking_embeds_results_in_one_batch():
    store = _Store()
    _rank(store)
    assert store.single_calls == ["query"]
    assert [sorted(call) for call in store.batch_calls] == [["a", "bbb", "cc"]]


@pytest.mark.parametrize(
    "batch_result", [RuntimeError("batch unavailable"), [np.array([1.0, 1.0])]]
)
def test_ranking_falls_back_to_single_embeddings(batch_result):
    store = _Store(batch_result)
    assert _rank(store) == _rank(_Store())
    assert sorted(store.single_calls) == ["a", "bbb", "cc", "query"]


def test_importing_parse_does_not_load_docling():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, semantica.parse; "
            "print('docling.document_converter' in sys.modules)",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False"


def test_docling_load_failure_is_recorded(monkeypatch):
    for name in ("DocumentConverter", "InputFormat", "PdfPipelineOptions", "PdfFormatOption"):
        monkeypatch.setattr(docling_parser, name, None)
    monkeypatch.setattr(docling_parser, "DOCLING_AVAILABLE", True)
    monkeypatch.setattr(docling_parser, "DOCLING_IMPORT_ERROR", None)
    monkeypatch.setitem(sys.modules, "docling.datamodel.base_models", None)

    with pytest.raises(ImportError):
        docling_parser._load_docling()

    assert docling_parser.DOCLING_AVAILABLE is False
    assert "docling.datamodel.base_models" in docling_parser.DOCLING_IMPORT_ERROR
