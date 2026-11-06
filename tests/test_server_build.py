"""Tests for the POST /build endpoint in semantica.server (#2218)."""

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from fastapi.testclient import TestClient

from semantica import server

client = TestClient(server.app)


def test_build_with_missing_source_returns_error():
    response = client.post("/build", json={"sources": ["does_not_exist.pdf"]})

    assert response.status_code == 422
    assert "No valid sources" in response.json()["detail"]


def test_build_with_real_source_returns_result(tmp_path):
    note = tmp_path / "note.txt"
    note.write_text("Dr. Arjun Rao is a pediatrician in Mysuru.", encoding="utf-8")

    response = client.post(
        "/build",
        json={"sources": [str(note)], "config": {"embeddings": False}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["statistics"]["sources_processed"] == 1
    assert body["embeddings"] is None  # config was forwarded


def test_build_returns_numpy_values_as_json(monkeypatch):
    def fake_build(sources, **kwargs):
        return {"embeddings": [np.array([0.5, 0.25])], "count": np.int64(1)}

    monkeypatch.setattr(server.framework, "build_knowledge_base", fake_build)

    response = client.post("/build", json={"sources": ["any.txt"]})

    assert response.status_code == 200
    assert response.json() == {"embeddings": [[0.5, 0.25]], "count": 1}
