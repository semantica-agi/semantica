"""
Tests for Causal Chain Analyzer

This module tests the CausalChainAnalyzer class and its methods
for analyzing decision causality and influence chains.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from semantica.context.decision_models import Decision
from semantica.context.causal_analyzer import CausalChainAnalyzer
from semantica.context.context_graph import ContextGraph


class TestCausalChainAnalyzer:
    """Test CausalChainAnalyzer class."""
    
    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store for testing."""
        mock_store = Mock()
        mock_store.execute_query = Mock()
        return mock_store
    
    @pytest.fixture
    def causal_analyzer(self, mock_graph_store):
        """Create CausalChainAnalyzer instance with mocked dependencies."""
        return CausalChainAnalyzer(graph_store=mock_graph_store)
    
    @pytest.fixture
    def sample_decisions(self):
        """Create sample decisions for testing."""
        base_time = datetime.now()
        return [
            Decision(
                decision_id="decision_001",
                category="credit_approval",
                scenario="Initial credit assessment",
                reasoning="Customer has good credit history",
                outcome="approved",
                confidence=0.9,
                timestamp=base_time - timedelta(days=3),
                decision_maker="ai_agent_001"
            ),
            Decision(
                decision_id="decision_002",
                category="credit_approval",
                scenario="Credit limit increase",
                reasoning="Based on previous approval and good payment history",
                outcome="approved",
                confidence=0.85,
                timestamp=base_time - timedelta(days=2),
                decision_maker="ai_agent_002"
            ),
            Decision(
                decision_id="decision_003",
                category="fraud_detection",
                scenario="Fraud review triggered",
                reasoning="Unusual activity pattern detected",
                outcome="flagged",
                confidence=0.8,
                timestamp=base_time - timedelta(days=1),
                decision_maker="ai_agent_001"
            )
        ]
    
    def test_causal_analyzer_initialization(self, mock_graph_store):
        """Test CausalChainAnalyzer initialization."""
        analyzer = CausalChainAnalyzer(graph_store=mock_graph_store)
        
        assert analyzer.graph_store == mock_graph_store
    
    def test_get_causal_chain_upstream_success(self, causal_analyzer, mock_graph_store):
        """Test successful upstream causal chain retrieval."""
        decision_id = "decision_002"
        direction = "upstream"
        max_depth = 5
        
        # Mock graph query results for upstream chain
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "credit_approval",
                "scenario": "Initial credit assessment",
                "reasoning": "Customer has good credit history",
                "outcome": "approved",
                "confidence": 0.9,
                "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
                "decision_maker": "ai_agent_001",
                "causal_distance": 1
            }
        ]
        
        chain = causal_analyzer.get_causal_chain(decision_id, direction, max_depth)
        
        assert len(chain) == 1
        assert chain[0].decision_id == "decision_001"
        assert chain[0].category == "credit_approval"
        
        # Verify graph query was called
        mock_graph_store.execute_query.assert_called()
    
    def test_get_causal_chain_downstream_success(self, causal_analyzer, mock_graph_store):
        """Test successful downstream causal chain retrieval."""
        decision_id = "decision_001"
        direction = "downstream"
        max_depth = 5
        
        # Mock graph query results for downstream chain
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_002",
                "category": "credit_approval",
                "scenario": "Credit limit increase",
                "reasoning": "Based on previous approval",
                "outcome": "approved",
                "confidence": 0.85,
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                "decision_maker": "ai_agent_002",
                "causal_distance": 1
            }
        ]
        
        chain = causal_analyzer.get_causal_chain(decision_id, direction, max_depth)
        
        assert len(chain) == 1
        assert chain[0].decision_id == "decision_002"
    
    def test_get_causal_chain_invalid_direction(self, causal_analyzer):
        """Test causal chain retrieval with invalid direction."""
        with pytest.raises(ValueError, match="Direction must be 'upstream' or 'downstream'"):
            causal_analyzer.get_causal_chain("decision_001", "invalid", 5)
    
    def test_get_causal_chain_invalid_max_depth(self, causal_analyzer):
        """Test causal chain retrieval with invalid max depth."""
        with pytest.raises(ValueError, match="max_depth must be between 1 and 20"):
            causal_analyzer.get_causal_chain("decision_001", "upstream", 0)

        with pytest.raises(ValueError, match="max_depth must be between 1 and 20"):
            causal_analyzer.get_causal_chain("decision_001", "upstream", 101)
    
    def test_get_causal_chain_empty_results(self, causal_analyzer, mock_graph_store):
        """Test causal chain retrieval with no results."""
        mock_graph_store.execute_query.return_value = []
        
        chain = causal_analyzer.get_causal_chain("decision_001", "upstream", 5)
        
        assert len(chain) == 0
    
    def test_get_influenced_decisions_success(self, causal_analyzer, mock_graph_store):
        """Test getting influenced decisions."""
        decision_id = "decision_001"
        max_depth = 5
        
        # Mock graph query results
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_002",
                "category": "credit_approval",
                "scenario": "Credit limit increase",
                "reasoning": "Based on previous approval",
                "outcome": "approved",
                "confidence": 0.85,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "ai_agent_002",
                "influence_strength": 0.8
            },
            {
                "decision_id": "decision_003",
                "category": "fraud_detection",
                "scenario": "Fraud review",
                "reasoning": "Triggered by credit activity",
                "outcome": "flagged",
                "confidence": 0.7,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "ai_agent_001",
                "influence_strength": 0.6
            }
        ]
        
        influenced = causal_analyzer.get_influenced_decisions(decision_id, max_depth)
        
        assert len(influenced) == 2
        assert influenced[0].decision_id == "decision_002"
        assert influenced[1].decision_id == "decision_003"
    
    def test_get_precedent_chain_success(self, causal_analyzer, mock_graph_store):
        """Test getting precedent chain."""
        decision_id = "decision_001"
        max_depth = 5
        
        # Mock graph query results
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "precedent_001",
                "category": "credit_approval",
                "scenario": "Similar credit case",
                "reasoning": "Similar circumstances",
                "outcome": "approved",
                "confidence": 0.9,
                "timestamp": (datetime.now() - timedelta(days=10)).isoformat(),
                "decision_maker": "ai_agent_001",
                "precedent_strength": 0.85
            }
        ]
        
        precedents = causal_analyzer.get_precedent_chain(decision_id, max_depth)
        
        assert len(precedents) == 1
        assert precedents[0].decision_id == "precedent_001"
    
    def test_find_causal_loops_success(self, causal_analyzer, mock_graph_store):
        """Test finding causal loops."""
        # Mock graph query results showing a loop
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "decision_scenario": "Approve LATAM expansion",
                "loop_path": [
                    {"decision_id": "decision_001", "scenario": "Approve LATAM expansion", "category": "strategy"},
                    {"decision_id": "decision_002", "scenario": "Fund regional hiring", "category": "finance"},
                    {"decision_id": "decision_003", "scenario": "Open Sao Paulo office", "category": "operations"},
                    {"decision_id": "decision_001", "scenario": "Approve LATAM expansion", "category": "strategy"},
                ],
                "loop_length": 3,
                "cycle_strength": 0.7
            }
        ]
        
        loops = causal_analyzer.find_causal_loops()
        
        assert len(loops) == 1
        assert loops[0]["decision_id"] == "decision_001"
        assert loops[0]["decision_scenario"] == "Approve LATAM expansion"
        assert loops[0]["loop_path"][0]["scenario"] == "Approve LATAM expansion"
        assert len(loops[0]["loop_path"]) == 4  # Including return to start
        assert loops[0]["loop_length"] == 3
    
    def test_find_causal_loops_no_loops(self, causal_analyzer, mock_graph_store):
        """Test finding causal loops when none exist."""
        mock_graph_store.execute_query.return_value = []
        
        loops = causal_analyzer.find_causal_loops()
        
        assert len(loops) == 0
    
    def test_get_causal_impact_score_success(self, causal_analyzer, mock_graph_store):
        """Test getting causal impact score."""
        decision_id = "decision_001"
        
        # Mock graph query results for impact calculation
        mock_graph_store.execute_query.return_value = [
            {"influence_count": 5, "avg_influence_strength": 0.7},
            {"precedent_count": 3, "avg_precedent_strength": 0.8}
        ]
        
        # Mock the internal calculation
        with patch.object(causal_analyzer, '_calculate_impact_score', return_value=0.75):
            score = causal_analyzer.get_causal_impact_score(decision_id)
        
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_get_causal_impact_score_no_influence(self, causal_analyzer, mock_graph_store):
        """Test getting causal impact score for decision with no influence."""
        decision_id = "decision_001"
        
        # Mock empty results
        mock_graph_store.execute_query.return_value = []
        
        score = causal_analyzer.get_causal_impact_score(decision_id)
        
        assert score == 0.0
    
    def test_find_root_causes_success(self, causal_analyzer, mock_graph_store):
        """Test finding root causes."""
        decision_id = "decision_001"
        max_depth = 5
        
        # Mock graph query results for root causes
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "root_cause_001",
                "category": "initial_assessment",
                "scenario": "Initial customer assessment",
                "reasoning": "First interaction with customer",
                "outcome": "processed",
                "confidence": 0.95,
                "timestamp": (datetime.now() - timedelta(days=30)).isoformat(),
                "decision_maker": "human_agent",
                "root_cause_strength": 0.9
            }
        ]
        
        root_causes = causal_analyzer.find_root_causes(decision_id, max_depth)
        
        assert len(root_causes) == 1
        assert root_causes[0].decision_id == "root_cause_001"
    
    def test_find_root_causes_no_roots(self, causal_analyzer, mock_graph_store):
        """Test finding root causes when none exist."""
        mock_graph_store.execute_query.return_value = []
        
        root_causes = causal_analyzer.find_root_causes("decision_001", 5)
        
        assert len(root_causes) == 0
    
    def test_analyze_causal_network_success(self, causal_analyzer, mock_graph_store):
        """Test causal network analysis."""
        # Mock network analysis results
        mock_graph_store.execute_query.return_value = [
            {"node_count": 10, "edge_count": 15, "avg_clustering": 0.3},
            {"centrality_scores": {"decision_001": 0.8, "decision_002": 0.6}},
            {"community_structure": {"community_1": ["decision_001", "decision_002"]}}
        ]
        
        network_analysis = causal_analyzer.analyze_causal_network()
        
        assert "node_count" in network_analysis
        assert "edge_count" in network_analysis
        assert "centrality_scores" in network_analysis
        assert "community_structure" in network_analysis
    
    def test_analyze_causal_network_empty(self, causal_analyzer, mock_graph_store):
        """Test causal network analysis with empty network."""
        mock_graph_store.execute_query.return_value = []
        
        network_analysis = causal_analyzer.analyze_causal_network()
        
        assert network_analysis["node_count"] == 0
        assert network_analysis["edge_count"] == 0
    
    def test_calculate_influence_strength(self, causal_analyzer):
        """Test influence strength calculation."""
        # Test direct influence
        strength = causal_analyzer._calculate_influence_strength(
            relationship_type="CAUSED",
            confidence=0.9,
            temporal_distance=1
        )
        assert strength > 0.8
        
        # Test indirect influence
        strength = causal_analyzer._calculate_influence_strength(
            relationship_type="INFLUENCED",
            confidence=0.7,
            temporal_distance=5
        )
        assert strength < 0.7
    
    def test_calculate_precedent_strength(self, causal_analyzer):
        """Test precedent strength calculation."""
        # Test strong precedent
        strength = causal_analyzer._calculate_precedent_strength(
            similarity_score=0.9,
            category_match=True,
            outcome_match=True
        )
        assert strength > 0.8
        
        # Test weak precedent
        strength = causal_analyzer._calculate_precedent_strength(
            similarity_score=0.3,
            category_match=False,
            outcome_match=False
        )
        assert strength < 0.5
    
    def test_detect_causal_cycle(self, causal_analyzer):
        """Test causal cycle detection."""
        # Create a cycle path
        path = ["decision_001", "decision_002", "decision_003", "decision_001"]
        
        cycle = causal_analyzer._detect_causal_cycle(path)
        
        assert cycle is not None
        assert len(cycle) == 4  # Including return to start
    
    def test_detect_causal_cycle_no_cycle(self, causal_analyzer):
        """Test causal cycle detection with no cycle."""
        # Create a path without cycle
        path = ["decision_001", "decision_002", "decision_003"]
        
        cycle = causal_analyzer._detect_causal_cycle(path)
        
        assert cycle is None
    
    def test_calculate_network_metrics(self, causal_analyzer):
        """Test network metrics calculation."""
        nodes = ["decision_001", "decision_002", "decision_003"]
        edges = [
            ("decision_001", "decision_002", "CAUSED"),
            ("decision_002", "decision_003", "INFLUENCED")
        ]
        
        metrics = causal_analyzer._calculate_network_metrics(nodes, edges)
        
        assert "density" in metrics
        assert "avg_path_length" in metrics
        assert "clustering_coefficient" in metrics
        assert 0 <= metrics["density"] <= 1
    
    def test_calculate_centrality_scores(self, causal_analyzer):
        """Test centrality score calculation."""
        nodes = ["decision_001", "decision_002", "decision_003"]
        edges = [
            ("decision_001", "decision_002"),
            ("decision_001", "decision_003"),
            ("decision_002", "decision_003")
        ]
        
        centrality = causal_analyzer._calculate_centrality_scores(nodes, edges)
        
        assert len(centrality) == len(nodes)
        for node in nodes:
            assert node in centrality
            assert 0 <= centrality[node] <= 1
    
    def test_identify_communities(self, causal_analyzer):
        """Test community identification."""
        nodes = ["decision_001", "decision_002", "decision_003", "decision_004"]
        edges = [
            ("decision_001", "decision_002"),
            ("decision_002", "decision_003"),
            ("decision_003", "decision_001"),  # First community
            ("decision_004",)  # Isolated node
        ]
        
        communities = causal_analyzer._identify_communities(nodes, edges)
        
        assert isinstance(communities, dict)
        assert len(communities) >= 1
    
    def test_query_execution_error_handling(self, causal_analyzer, mock_graph_store):
        """Test error handling during query execution."""
        mock_graph_store.execute_query.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            causal_analyzer.get_causal_chain("decision_001", "upstream", 5)
    
    def test_malformed_query_results(self, causal_analyzer, mock_graph_store):
        """Test handling of malformed query results."""
        # Return result missing optional fields — should be handled gracefully
        mock_graph_store.execute_query.return_value = [
            {"decision_id": "test"}  # Missing other optional fields
        ]

        chain = causal_analyzer.get_causal_chain("decision_001", "upstream", 5)
        assert len(chain) == 1
        assert chain[0].decision_id == "test"
    
    def test_large_causal_chain_handling(self, causal_analyzer, mock_graph_store):
        """Test handling of large causal chains."""
        # Mock large result set
        large_results = [
            {
                "decision_id": f"decision_{i}",
                "category": "test",
                "scenario": f"Scenario {i}",
                "reasoning": f"Reasoning {i}",
                "outcome": "approved",
                "confidence": 0.8,
                "timestamp": (datetime.now() - timedelta(days=i)).isoformat(),
                "decision_maker": "ai_agent",
                "causal_distance": i
            }
            for i in range(1, 101)  # 100 decisions
        ]
        
        mock_graph_store.execute_query.return_value = large_results
        
        chain = causal_analyzer.get_causal_chain("decision_001", "upstream", 100)
        
        assert len(chain) == 100
    
    def test_temporal_causal_analysis(self, causal_analyzer, mock_graph_store):
        """Test temporal causal analysis."""
        # Mock results with temporal information
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                "decision_maker": "test",
                "temporal_distance": 1
            },
            {
                "decision_id": "decision_002",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                "decision_maker": "test",
                "temporal_distance": 24
            }
        ]
        
        chain = causal_analyzer.get_causal_chain("decision_003", "upstream", 5)
        
        # Should be ordered by temporal distance
        assert len(chain) == 2
        # Recent decision should come first
        assert chain[0].decision_id == "decision_001"
        assert chain[1].decision_id == "decision_002"

    def test_trace_at_time_excludes_late_recorded_facts(self):
        """trace_at_time should filter by relationship recorded_at, not valid time."""
        graph = ContextGraph()
        decision_1 = Decision(
            decision_id="decision_001",
            category="ops",
            scenario="Initial review",
            reasoning="Start",
            outcome="approved",
            confidence=0.9,
            timestamp=datetime.now(),
            decision_maker="agent",
        )
        decision_2 = Decision(
            decision_id="decision_002",
            category="ops",
            scenario="Follow-up",
            reasoning="Depends on initial review",
            outcome="approved",
            confidence=0.9,
            timestamp=datetime.now(),
            decision_maker="agent",
        )
        graph.add_decision(decision_1)
        graph.add_decision(decision_2)
        graph.add_edge(
            "decision_001",
            "decision_002",
            "CAUSED",
            recorded_at="2024-01-10T00:00:00",
        )

        analyzer = CausalChainAnalyzer(graph_store=graph)

        early_chain = analyzer.trace_at_time("decision_002", "2024-01-05T00:00:00")
        later_chain = analyzer.trace_at_time("decision_002", "2024-01-15T00:00:00")

        assert early_chain == []
        assert [decision.decision_id for decision in later_chain] == ["decision_001"]

    def test_trace_at_time_returns_empty_before_any_facts_recorded(self):
        """When the cutoff predates all facts, trace_at_time should return an empty chain."""
        graph = ContextGraph()
        graph.add_decision(
            Decision(
                decision_id="decision_001",
                category="ops",
                scenario="Initial review",
                reasoning="Start",
                outcome="approved",
                confidence=0.9,
                timestamp=datetime.now(),
                decision_maker="agent",
            )
        )
        graph.add_decision(
            Decision(
                decision_id="decision_002",
                category="ops",
                scenario="Follow-up",
                reasoning="Depends on initial review",
                outcome="approved",
                confidence=0.9,
                timestamp=datetime.now(),
                decision_maker="agent",
            )
        )
        graph.add_edge(
            "decision_001",
            "decision_002",
            "CAUSED",
            recorded_at="2024-02-01T00:00:00",
        )

        analyzer = CausalChainAnalyzer(graph_store=graph)

        assert analyzer.trace_at_time("decision_002", "2024-01-01T00:00:00") == []


class TestCausalAnalyzerEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store for testing."""
        mock_store = Mock()
        mock_store.execute_query = Mock()
        return mock_store

    @pytest.fixture
    def causal_analyzer(self, mock_graph_store):
        """Create CausalChainAnalyzer with minimal dependencies."""
        return CausalChainAnalyzer(graph_store=mock_graph_store)
    
    def test_self_referencing_decision(self, causal_analyzer, mock_graph_store):
        """Test handling of self-referencing decisions."""
        # Mock self-referencing result
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test",
                "causal_distance": 0  # Self-reference
            }
        ]
        
        chain = causal_analyzer.get_causal_chain("decision_001", "upstream", 5)
        
        # Should handle self-reference gracefully
        assert len(chain) == 1
        assert chain[0].decision_id == "decision_001"
    
    def test_circular_causality_complex(self, causal_analyzer, mock_graph_store):
        """Test handling of complex circular causality."""
        # Mock complex circular chain
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": f"decision_{i}",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test",
                "causal_distance": i % 5  # Create pattern
            }
            for i in range(10)
        ]
        
        chain = causal_analyzer.get_causal_chain("decision_001", "upstream", 10)
        
        # Should handle circular references without infinite loops
        assert len(chain) == 10
    
    def test_extreme_temporal_distances(self, causal_analyzer, mock_graph_store):
        """Test handling of extreme temporal distances."""
        # Mock decisions with extreme temporal distances
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": (datetime.now() - timedelta(days=365)).isoformat(),  # 1 year ago
                "decision_maker": "test",
                "causal_distance": 365
            },
            {
                "decision_id": "decision_002",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": (datetime.now() - timedelta(seconds=1)).isoformat(),  # 1 second ago
                "decision_maker": "test",
                "causal_distance": 1
            }
        ]
        
        chain = causal_analyzer.get_causal_chain("decision_003", "upstream", 10)
        
        # Should handle extreme temporal distances
        assert len(chain) == 2
    
    def test_missing_decision_metadata(self, causal_analyzer, mock_graph_store):
        """Test handling of decisions with missing metadata."""
        # Mock result with missing optional fields
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test"
                # Missing causal_distance and other optional fields
            }
        ]
        
        chain = causal_analyzer.get_causal_chain("decision_001", "upstream", 5)
        
        # Should handle missing metadata gracefully
        assert len(chain) == 1
        assert chain[0].decision_id == "decision_001"

    def test_dict_to_decision_json_string_metadata(self, causal_analyzer):
        """CausalChainAnalyzer._dict_to_decision decodes JSON string metadata into a dict."""
        data = {
            "decision_id": "causal_dec_001",
            "category": "security",
            "scenario": "auth change",
            "reasoning": "prevent bypass",
            "outcome": "enforced",
            "confidence": 0.95,
            "timestamp": datetime.now().isoformat(),
            "decision_maker": "sec_agent",
            "metadata": '{"tier": "critical", "incident_id": "INC-99"}'
        }
        dec = causal_analyzer._dict_to_decision(data)
        assert isinstance(dec.metadata, dict)
        assert dec.metadata["tier"] == "critical"
        assert dec.metadata["incident_id"] == "INC-99"
        # Verify mutation works
        dec.metadata["analyzed"] = True
        assert dec.metadata["analyzed"] is True
    
    def test_invalid_confidence_values(self, causal_analyzer, mock_graph_store):
        """Test handling of invalid confidence values."""
        # Mock results with invalid confidence values
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 1.5,  # Invalid > 1
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test",
                "causal_distance": 1
            },
            {
                "decision_id": "decision_002",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": -0.5,  # Invalid < 0
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test",
                "causal_distance": 2
            }
        ]
        
        # Should handle invalid confidence values
        chain = causal_analyzer.get_causal_chain("decision_003", "upstream", 5)
        
        assert len(chain) == 2
        # Values should be normalized or handled appropriately
    
    def test_empty_decision_id(self, causal_analyzer, mock_graph_store):
        """Test handling of empty decision ID."""
        mock_graph_store.execute_query.return_value = []
        
        chain = causal_analyzer.get_causal_chain("", "upstream", 5)
        
        assert len(chain) == 0
    
    def test_null_timestamps(self, causal_analyzer, mock_graph_store):
        """Test handling of null timestamps."""
        # Mock result with null timestamp
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": None,  # Null timestamp
                "decision_maker": "test",
                "causal_distance": 1
            }
        ]
        
        chain = causal_analyzer.get_causal_chain("decision_002", "upstream", 5)
        
        # Should handle null timestamp gracefully
        assert len(chain) == 1


if __name__ == "__main__":
    pytest.main([__file__])
