"""
Tests for GraphRAG CLI commands: 'semantica kg global' and 'semantica kg drift' (PR #3).
"""

import json
from pathlib import Path
import tempfile

from click.testing import CliRunner
import pytest

import semantica.cli as cli_module


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def silence_logging(monkeypatch):
    monkeypatch.setattr(cli_module, "setup_logging", lambda *a, **kw: None)


class TestCliGraphRAG:
    """Tests for CLI subcommands kg global and kg drift."""

    def test_kg_global_help(self, runner: CliRunner):
        result = runner.invoke(cli_module.main, ["kg", "global", "--help"])
        assert result.exit_code == 0
        assert "--reports" in result.output
        assert "--hierarchy" in result.output
        assert "--level" in result.output
        assert "--max-tokens" in result.output
        assert "--json" in result.output

    def test_kg_drift_help(self, runner: CliRunner):
        result = runner.invoke(cli_module.main, ["kg", "drift", "--help"])
        assert result.exit_code == 0
        assert "--reports" in result.output
        assert "--graph" in result.output
        assert "--depth" in result.output
        assert "--drift-threshold" in result.output
        assert "--json" in result.output

    def test_kg_global_with_reports_json(self, runner: CliRunner):
        sample_reports = [
            {
                "community_id": "c_cli_1",
                "level": 0,
                "title": "Quantum Physics Research",
                "summary": "Quantum entanglement and superposition findings.",
                "findings": [{"summary": "Entanglement verified"}],
                "member_entities": ["Photon", "Qubit"],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            rep_path = Path(tmp_dir) / "reports.json"
            with open(rep_path, "w", encoding="utf-8") as f:
                json.dump(sample_reports, f)

            result = runner.invoke(
                cli_module.main,
                [
                    "kg",
                    "global",
                    "quantum entanglement",
                    "--reports",
                    str(rep_path),
                    "--json",
                ],
            )

            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert "response" in payload
            assert payload["level"] == 0
            assert "c_cli_1" in payload["community_reports_used"]
            assert len(payload["key_points"]) >= 1

    def test_kg_global_plain_text(self, runner: CliRunner):
        sample_reports = [
            {
                "community_id": "c_cli_2",
                "level": 0,
                "title": "Autonomous Robotics",
                "summary": "Motion planning, SLAM, and LiDAR sensors.",
                "findings": [{"summary": "LiDAR enables 3D mapping"}],
                "member_entities": ["LiDAR", "Robot"],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            rep_path = Path(tmp_dir) / "reports.json"
            with open(rep_path, "w", encoding="utf-8") as f:
                json.dump(sample_reports, f)

            result = runner.invoke(
                cli_module.main,
                ["kg", "global", "robotics motion", "--reports", str(rep_path)],
            )

            assert result.exit_code == 0
            assert "Global Search Results" in result.output
            assert "c_cli_2" in result.output

    def test_kg_drift_with_graph_and_reports_json(self, runner: CliRunner):
        sample_reports = [
            {
                "community_id": "c_drift_cli",
                "level": 0,
                "title": "Graph Algorithms",
                "summary": "Network traversal and PageRank scoring.",
                "findings": [{"summary": "PageRank scores node influence"}],
                "member_entities": ["PageRank", "Graph"],
            }
        ]
        sample_graph = {
            "nodes": [{"id": "Graph"}, {"id": "PageRank"}],
            "edges": [
                {
                    "source": "Graph",
                    "target": "PageRank",
                    "relation": "EVALUATED_BY",
                    "description": "Ranking algorithm",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            rep_path = Path(tmp_dir) / "reports.json"
            with open(rep_path, "w", encoding="utf-8") as f:
                json.dump(sample_reports, f)

            graph_path = Path(tmp_dir) / "graph.json"
            with open(graph_path, "w", encoding="utf-8") as f:
                json.dump(sample_graph, f)

            result = runner.invoke(
                cli_module.main,
                [
                    "kg",
                    "drift",
                    "Graph algorithms PageRank",
                    "--reports",
                    str(rep_path),
                    "--graph",
                    str(graph_path),
                    "--json",
                ],
            )

            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert "answer" in payload
            assert payload["depth_reached"] >= 1
            assert len(payload["verified_local_contexts"]) >= 1

    def test_kg_drift_plain_text(self, runner: CliRunner):
        result = runner.invoke(cli_module.main, ["kg", "drift", "general question"])
        assert result.exit_code == 0
        assert "DRIFT Hybrid Search Results" in result.output

    def test_kg_global_invalid_json_reports(self, runner: CliRunner):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_path = Path(tmp_dir) / "corrupt.json"
            bad_path.write_text("{ this is not valid json }", encoding="utf-8")

            result = runner.invoke(
                cli_module.main,
                ["kg", "global", "query", "--reports", str(bad_path)],
            )
            assert result.exit_code != 0

    def test_kg_drift_invalid_json_graph(self, runner: CliRunner):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_path = Path(tmp_dir) / "corrupt_graph.json"
            bad_path.write_text("[ invalid json", encoding="utf-8")

            result = runner.invoke(
                cli_module.main,
                ["kg", "drift", "query", "--graph", str(bad_path)],
            )
            assert result.exit_code != 0

    def test_kg_global_without_reports_raises_error(self, runner: CliRunner):
        result = runner.invoke(
            cli_module.main,
            ["kg", "global", "query"],
        )
        assert result.exit_code != 0
        assert "Global retrieval requires --reports" in result.output
