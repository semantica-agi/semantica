"""
Tests for ContextGraph Decision Support

This module tests the ContextGraph class and its decision tracking
enhancements including decision nodes and causal relationships.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from semantica.context.context_graph import ContextGraph, ContextNode, ContextEdge
from semantica.context.decision_models import Decision, Policy


class TestContextGraphDecisions:
    """Test ContextGraph decision support functionality."""
    
    @pytest.fixture
    def context_graph(self):
        """Create ContextGraph instance for testing."""
        return ContextGraph()
    
    @pytest.fixture
    def sample_decision(self):
        """Create sample decision for testing."""
        return Decision(
            decision_id="decision_001",
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history",
            outcome="approved",
            confidence=0.85,
            timestamp=datetime.now(),
            decision_maker="ai_agent_001",
            metadata={"risk_level": "low", "customer_tier": "premium"}
        )
    
    def test_add_decision_success(self, context_graph, sample_decision):
        """Test successful decision addition."""
        context_graph.add_decision(sample_decision)
        
        assert "decision_001" in context_graph.nodes
        node = context_graph.nodes["decision_001"]
        assert node.node_type == "Decision"
        assert node.content == sample_decision.scenario
        assert node.properties["category"] == sample_decision.category
        assert node.properties["confidence"] == sample_decision.confidence
        assert node.properties["decision_maker"] == sample_decision.decision_maker
    
    def test_add_decision_kwargs_form(self, context_graph):
        """add_decision() accepts kwargs directly (no Decision object required)."""
        decision_id = context_graph.add_decision(
            category="loan_approval",
            scenario="Mortgage application — 780 credit score",
            reasoning="Strong credit history, low DTI",
            outcome="approved",
            confidence=0.95,
        )

        assert isinstance(decision_id, str)
        assert len(decision_id) > 0
        node = context_graph.nodes[decision_id]
        assert node.node_type in ("Decision", "decision")
        assert node.properties["category"] == "loan_approval"
        assert node.properties["outcome"] == "approved"
        assert node.properties["confidence"] == 0.95

    def test_add_decision_kwargs_and_object_both_return_id(self, context_graph, sample_decision):
        """Both call forms return a non-empty decision ID string."""
        id_from_object = context_graph.add_decision(sample_decision)
        id_from_kwargs = context_graph.add_decision(
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="approved",
            confidence=0.8,
        )

        assert isinstance(id_from_object, str) and len(id_from_object) > 0
        assert isinstance(id_from_kwargs, str) and len(id_from_kwargs) > 0

    def test_add_decision_with_embeddings(self, context_graph):
        """Test adding decision with embeddings."""
        decision = Decision(
            decision_id="decision_001",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent",
            reasoning_embedding=[0.1, 0.2, 0.3],
            node2vec_embedding=[0.4, 0.5, 0.6]
        )
        
        context_graph.add_decision(decision)
        
        node = context_graph.nodes["decision_001"]
        assert node.properties["reasoning_embedding"] == [0.1, 0.2, 0.3]
        assert node.properties["node2vec_embedding"] == [0.4, 0.5, 0.6]
    
    def test_add_causal_relationship_success(self, context_graph, sample_decision):
        """Test successful causal relationship addition."""
        # Add decisions first
        decision2 = Decision(
            decision_id="decision_002",
            category="test",
            scenario="test scenario 2",
            reasoning="test reasoning 2",
            outcome="test outcome 2",
            confidence=0.7,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(sample_decision)
        context_graph.add_decision(decision2)
        
        # Add causal relationship
        context_graph.add_causal_relationship(
            "decision_001", "decision_002", "CAUSED"
        )
        
        # Verify relationship was added
        edges = list(context_graph.edges)
        assert len(edges) == 1
        edge = edges[0]
        assert edge.source_id == "decision_001"
        assert edge.target_id == "decision_002"
        assert edge.edge_type == "CAUSED"
        assert edge.weight == 1.0
    
    def test_add_causal_relationship_invalid_type(self, context_graph, sample_decision):
        """Test adding causal relationship with invalid type."""
        decision2 = Decision(
            decision_id="decision_002",
            category="test",
            scenario="test scenario 2",
            reasoning="test reasoning 2",
            outcome="test outcome 2",
            confidence=0.7,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(sample_decision)
        context_graph.add_decision(decision2)
        
        with pytest.raises(ValueError, match="Relationship type must be one of"):
            context_graph.add_causal_relationship(
                "decision_001", "decision_002", "INVALID_TYPE"
            )
    
    def test_add_causal_relationship_nonexistent_decision(self, context_graph, sample_decision):
        """Test adding causal relationship with nonexistent decision."""
        context_graph.add_decision(sample_decision)
        
        # Should not raise error, but relationship won't be added
        context_graph.add_causal_relationship(
            "decision_001", "nonexistent_decision", "CAUSED"
        )
        
        # No edges should be added
        assert len(list(context_graph.edges)) == 0
    
    def test_get_causal_chain_upstream(self, context_graph):
        """Test getting upstream causal chain."""
        # Create decision chain: decision_001 -> decision_002 -> decision_003
        decisions = [
            Decision(
                decision_id=f"decision_{i:03d}",
                category="test",
                scenario=f"scenario {i}",
                reasoning=f"reasoning {i}",
                outcome="approved",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(hours=i),
                decision_maker="test_agent"
            )
            for i in range(1, 4)
        ]
        
        # Add decisions
        for decision in decisions:
            context_graph.add_decision(decision)
        
        # Add causal relationships
        context_graph.add_causal_relationship("decision_001", "decision_002", "CAUSED")
        context_graph.add_causal_relationship("decision_002", "decision_003", "CAUSED")
        
        # Get upstream chain from decision_003
        chain = context_graph.get_causal_chain("decision_003", direction="upstream", max_depth=5)
        
        assert len(chain) == 2  # decision_001 and decision_002
        assert chain[0].decision_id == "decision_001"
        assert chain[1].decision_id == "decision_002"
        assert chain[0].metadata["causal_distance"] == 2
        assert chain[1].metadata["causal_distance"] == 1
    
    def test_get_causal_chain_downstream(self, context_graph):
        """Test getting downstream causal chain."""
        # Create decision chain: decision_001 -> decision_002 -> decision_003
        decisions = [
            Decision(
                decision_id=f"decision_{i:03d}",
                category="test",
                scenario=f"scenario {i}",
                reasoning=f"reasoning {i}",
                outcome="approved",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(hours=i),
                decision_maker="test_agent"
            )
            for i in range(1, 4)
        ]
        
        # Add decisions
        for decision in decisions:
            context_graph.add_decision(decision)
        
        # Add causal relationships
        context_graph.add_causal_relationship("decision_001", "decision_002", "CAUSED")
        context_graph.add_causal_relationship("decision_002", "decision_003", "CAUSED")
        
        # Get downstream chain from decision_001
        chain = context_graph.get_causal_chain("decision_001", direction="downstream", max_depth=5)
        
        assert len(chain) == 2  # decision_002 and decision_003
        assert chain[0].decision_id == "decision_002"
        assert chain[1].decision_id == "decision_003"
        assert chain[0].metadata["causal_distance"] == 1
        assert chain[1].metadata["causal_distance"] == 2
    
    def test_get_causal_chain_invalid_direction(self, context_graph):
        """Test getting causal chain with invalid direction."""
        with pytest.raises(ValueError, match="Direction must be 'upstream' or 'downstream'"):
            context_graph.get_causal_chain("decision_001", "invalid", 5)
    
    def test_get_causal_chain_max_depth(self, context_graph):
        """Test causal chain with max depth limit."""
        # Create longer chain: decision_001 -> decision_002 -> decision_003 -> decision_004
        decisions = [
            Decision(
                decision_id=f"decision_{i:03d}",
                category="test",
                scenario=f"scenario {i}",
                reasoning=f"reasoning {i}",
                outcome="approved",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(hours=i),
                decision_maker="test_agent"
            )
            for i in range(1, 5)
        ]
        
        # Add decisions
        for decision in decisions:
            context_graph.add_decision(decision)
        
        # Add causal relationships
        for i in range(1, 4):
            context_graph.add_causal_relationship(f"decision_{i:03d}", f"decision_{i+1:03d}", "CAUSED")
        
        # Get chain with max depth 2
        chain = context_graph.get_causal_chain("decision_001", "downstream", max_depth=2)
        
        assert len(chain) == 2  # Only first 2 decisions due to depth limit
    
    def test_get_causal_chain_nonexistent_decision(self, context_graph):
        """Test getting causal chain for nonexistent decision."""
        chain = context_graph.get_causal_chain("nonexistent_decision", "upstream", 5)
        
        assert len(chain) == 0
    
    def test_find_precedents_success(self, context_graph):
        """Test finding precedent decisions."""
        # Add decisions
        source_decision = Decision(
            decision_id="source_decision",
            category="credit_approval",
            scenario="Credit limit increase",
            reasoning="Good payment history",
            outcome="approved",
            confidence=0.9,
            timestamp=datetime.now(),
            decision_maker="ai_agent"
        )
        
        precedent_decisions = [
            Decision(
                decision_id=f"precedent_{i}",
                category="credit_approval",
                scenario=f"Similar credit case {i}",
                reasoning=f"Similar reasoning {i}",
                outcome="approved",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(days=i),
                decision_maker="ai_agent"
            )
            for i in range(1, 4)
        ]
        
        context_graph.add_decision(source_decision)
        for decision in precedent_decisions:
            context_graph.add_decision(decision)
        
        # Add precedent relationships
        for decision in precedent_decisions:
            context_graph.add_causal_relationship(
                decision.decision_id, "source_decision", "PRECEDENT_FOR"
            )
        
        # Find precedents
        precedents = context_graph.find_precedents("source_decision", limit=10)
        
        assert len(precedents) == 3
        precedent_ids = [p.decision_id for p in precedents]
        assert "precedent_1" in precedent_ids
        assert "precedent_2" in precedent_ids
        assert "precedent_3" in precedent_ids
    
    def test_find_precedents_limit(self, context_graph):
        """Test finding precedents with limit."""
        # Add source decision
        source_decision = Decision(
            decision_id="source_decision",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(source_decision)
        
        # Add many precedent decisions
        for i in range(10):
            precedent = Decision(
                decision_id=f"precedent_{i}",
                category="test",
                scenario=f"precedent scenario {i}",
                reasoning=f"precedent reasoning {i}",
                outcome="test outcome",
                confidence=0.8,
                timestamp=datetime.now(),
                decision_maker="test_agent"
            )
            context_graph.add_decision(precedent)
            context_graph.add_causal_relationship(
                f"precedent_{i}", "source_decision", "PRECEDENT_FOR"
            )
        
        # Find precedents with limit
        precedents = context_graph.find_precedents("source_decision", limit=5)
        
        assert len(precedents) == 5
    
    def test_find_precedents_nonexistent_decision(self, context_graph):
        """Test finding precedents for nonexistent decision."""
        precedents = context_graph.find_precedents("nonexistent_decision", limit=10)
        
        assert len(precedents) == 0
    
    def test_find_precedents_no_precedent_relationships(self, context_graph):
        """Test finding precedents when no precedent relationships exist."""
        decision = Decision(
            decision_id="decision_001",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(decision)
        
        precedents = context_graph.find_precedents("decision_001", limit=10)
        
        assert len(precedents) == 0

    def test_find_precedents_by_scenario_filters_superseded_as_of(self, context_graph):
        """Decisions outside the validity window should be excluded for as_of queries."""
        expired_id = context_graph.record_decision(
            category="policy",
            scenario="Use old underwriting threshold",
            reasoning="Legacy policy",
            outcome="approved",
            confidence=0.7,
            valid_until="2023-01-01T00:00:00",
        )
        active_id = context_graph.record_decision(
            category="policy",
            scenario="Use new underwriting threshold",
            reasoning="Replacement policy",
            outcome="approved",
            confidence=0.9,
            valid_from="2023-01-02T00:00:00",
        )

        results = context_graph.find_precedents_by_scenario(
            scenario="underwriting threshold",
            category="policy",
            as_of="2024-01-01T00:00:00",
            similarity_threshold=0.0,
        )

        returned_ids = {item["decision"]["id"] for item in results}
        assert expired_id not in returned_ids
        assert active_id in returned_ids

    def test_find_precedents_by_scenario_can_include_superseded(self, context_graph):
        """Superseded decisions remain queryable when explicitly requested."""
        expired_id = context_graph.record_decision(
            category="policy",
            scenario="Use old threshold",
            reasoning="Legacy rule",
            outcome="approved",
            confidence=0.7,
            valid_until="2023-01-01T00:00:00",
        )

        results = context_graph.find_precedents_by_scenario(
            scenario="old threshold",
            category="policy",
            include_superseded=True,
            similarity_threshold=0.0,
        )

        returned_ids = {item["decision"]["id"] for item in results}
        assert expired_id in returned_ids

    def test_state_at_returns_only_valid_items_and_is_serializable(self, context_graph):
        """state_at should filter by validity window without mutating the graph."""
        context_graph.add_node(
            "entity_active",
            "entity",
            content="Active entity",
            valid_from="2024-01-01T00:00:00",
            valid_until="2024-12-31T23:59:59",
        )
        context_graph.add_node(
            "entity_expired",
            "entity",
            content="Expired entity",
            valid_until="2023-12-31T23:59:59",
        )
        context_graph.add_edge(
            "entity_active",
            "entity_expired",
            "related_to",
            valid_until="2023-12-31T23:59:59",
        )
        decision_id = context_graph.record_decision(
            category="policy",
            scenario="Current policy",
            reasoning="Current reasoning",
            outcome="approved",
            confidence=0.95,
            valid_from="2024-01-01T00:00:00",
        )

        snapshot = context_graph.state_at("2024-06-01T00:00:00")

        assert decision_id in context_graph.nodes
        node_ids = {node["id"] for node in snapshot["nodes"]}
        decision_ids = {decision["id"] for decision in snapshot["decisions"]}
        assert "entity_active" in node_ids
        assert "entity_expired" not in node_ids
        assert decision_id in decision_ids

        import json
        json.dumps(snapshot)
    
    def test_complex_causal_network(self, context_graph):
        """Test complex causal network with multiple relationship types."""
        # Create a complex network
        decisions = [
            Decision(
                decision_id=f"decision_{i:03d}",
                category="test",
                scenario=f"scenario {i}",
                reasoning=f"reasoning {i}",
                outcome="approved",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(hours=i),
                decision_maker="test_agent"
            )
            for i in range(1, 7)
        ]
        
        # Add decisions
        for decision in decisions:
            context_graph.add_decision(decision)
        
        # Add various causal relationships
        relationships = [
            ("decision_001", "decision_002", "CAUSED"),
            ("decision_002", "decision_003", "INFLUENCED"),
            ("decision_001", "decision_004", "INFLUENCED"),
            ("decision_003", "decision_005", "CAUSED"),
            ("decision_004", "decision_006", "PRECEDENT_FOR"),
            ("decision_002", "decision_006", "INFLUENCED")
        ]
        
        for source, target, rel_type in relationships:
            context_graph.add_causal_relationship(source, target, rel_type)
        
        # Test upstream chain from decision_006
        upstream_chain = context_graph.get_causal_chain("decision_006", "upstream", max_depth=10)
        
        # Should find multiple upstream decisions
        upstream_ids = [d.decision_id for d in upstream_chain]
        assert "decision_001" in upstream_ids
        assert "decision_002" in upstream_ids
        assert "decision_004" in upstream_ids
        
        # Test downstream chain from decision_001
        downstream_chain = context_graph.get_causal_chain("decision_001", "downstream", max_depth=10)
        
        # Should find multiple downstream decisions
        downstream_ids = [d.decision_id for d in downstream_chain]
        assert "decision_002" in downstream_ids
        assert "decision_003" in downstream_ids
        assert "decision_004" in downstream_ids
        assert "decision_005" in downstream_ids
        assert "decision_006" in downstream_ids
    
    def test_causal_loop_detection(self, context_graph):
        """Test handling of causal loops."""
        # Create decisions that form a loop
        decisions = [
            Decision(
                decision_id=f"decision_{i:03d}",
                category="test",
                scenario=f"scenario {i}",
                reasoning=f"reasoning {i}",
                outcome="approved",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(hours=i),
                decision_maker="test_agent"
            )
            for i in range(1, 4)
        ]
        
        # Add decisions
        for decision in decisions:
            context_graph.add_decision(decision)
        
        # Create a loop: decision_001 -> decision_002 -> decision_003 -> decision_001
        context_graph.add_causal_relationship("decision_001", "decision_002", "CAUSED")
        context_graph.add_causal_relationship("decision_002", "decision_003", "CAUSED")
        context_graph.add_causal_relationship("decision_003", "decision_001", "CAUSED")
        
        # Should handle loop without infinite recursion
        chain = context_graph.get_causal_chain("decision_001", "downstream", max_depth=10)
        
        # Should find other decisions but not get stuck in loop
        decision_ids = [d.decision_id for d in chain]
        assert "decision_002" in decision_ids
        assert "decision_003" in decision_ids
    
    def test_decision_with_large_metadata(self, context_graph):
        """Test adding decision with large metadata."""
        large_metadata = {
            f"field_{i}": f"value_{i}" for i in range(1000)
        }
        
        decision = Decision(
            decision_id="decision_001",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent",
            metadata=large_metadata
        )
        
        context_graph.add_decision(decision)
        
        node = context_graph.nodes["decision_001"]
        assert len(node.properties) > 1000  # Should include all metadata
    
    def test_decision_with_special_characters(self, context_graph):
        """Test adding decision with special characters."""
        decision = Decision(
            decision_id="decision_001",
            category="test_category",
            scenario="Scenario with special chars: @#$%^&*()",
            reasoning="Reasoning with unicode: café résumé 测试",
            outcome="Approved 🎉",
            confidence=0.85,
            timestamp=datetime.now(),
            decision_maker="AI Agent 001",
            metadata={"unicode": "测试", "emoji": "🚀", "quotes": "'single' and \"double\""}
        )
        
        context_graph.add_decision(decision)
        
        node = context_graph.nodes["decision_001"]
        assert node.content == decision.scenario
        assert node.properties["reasoning"] == decision.reasoning
        assert node.properties["outcome"] == decision.outcome
    
    def test_mixed_node_types_with_decisions(self, context_graph):
        """Test graph with mixed node types including decisions."""
        # Add regular entities
        context_graph.add_node("customer_001", "Person", "Customer Jessica Norris")
        context_graph.add_node("credit_card_001", "CreditCard", "Premium Credit Card")
        
        # Add decision
        decision = Decision(
            decision_id="decision_001",
            category="credit_approval",
            scenario="Credit limit increase",
            reasoning="Good payment history",
            outcome="approved",
            confidence=0.9,
            timestamp=datetime.now(),
            decision_maker="ai_agent"
        )
        context_graph.add_decision(decision)
        
        # Add relationships between entities and decision
        context_graph.add_edge("customer_001", "decision_001", "SUBJECT_OF")
        context_graph.add_edge("credit_card_001", "decision_001", "RELATED_TO")
        
        # Verify all nodes exist
        assert "customer_001" in context_graph.nodes
        assert "credit_card_001" in context_graph.nodes
        assert "decision_001" in context_graph.nodes
        
        # Verify relationships
        edges = list(context_graph.edges)
        assert len(edges) == 2
        edge_types = [e.edge_type for e in edges]
        assert "SUBJECT_OF" in edge_types
        assert "RELATED_TO" in edge_types
    
    def test_decision_node_serialization(self, context_graph, sample_decision):
        """Test serialization of decision nodes."""
        context_graph.add_decision(sample_decision)
        
        # Convert to dictionary
        graph_dict = context_graph.to_dict()
        
        # Find decision node in dictionary
        decision_node = None
        for node in graph_dict["nodes"]:
            if node["id"] == "decision_001":
                decision_node = node
                break
        
        assert decision_node is not None
        assert decision_node["type"] == "Decision"
        assert decision_node["content"] == sample_decision.scenario
        assert decision_node["properties"]["category"] == sample_decision.category
        assert decision_node["properties"]["confidence"] == sample_decision.confidence
    
    def test_decision_node_deserialization(self, context_graph):
        """Test deserialization of decision nodes."""
        # Create graph dictionary with decision node
        graph_dict = {
            "nodes": [
                {
                    "id": "decision_001",
                    "type": "Decision",
                    "content": "Credit limit increase",
                    "properties": {
                        "category": "credit_approval",
                        "reasoning": "Good payment history",
                        "outcome": "approved",
                        "confidence": 0.9,
                        "timestamp": datetime.now().isoformat(),
                        "decision_maker": "ai_agent"
                    }
                }
            ],
            "edges": []
        }
        
        # Load from dictionary
        context_graph.from_dict(graph_dict)
        
        # Verify decision was loaded
        assert "decision_001" in context_graph.nodes
        node = context_graph.nodes["decision_001"]
        assert node.node_type == "Decision"
        assert node.content == "Credit limit increase"
        assert node.properties["category"] == "credit_approval"


class TestContextGraphDecisionsEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def context_graph(self):
        """Create ContextGraph instance for testing."""
        return ContextGraph()
    
    def test_empty_decision_id(self, context_graph):
        """Test adding decision with empty ID."""
        decision = Decision(
            decision_id="",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        # Should still add the decision (auto-generates UUID for empty string)
        context_graph.add_decision(decision)
        
        # Should have generated UUID for empty string (not preserve empty string)
        assert len(context_graph.nodes) == 1
        assert "" not in context_graph.nodes  # Empty string should be replaced with UUID
    
    def test_decision_with_null_fields(self, context_graph):
        """Test adding decision with null fields."""
        decision = Decision(
            decision_id="decision_001",
            category=None,  # Null category
            scenario="test scenario",
            reasoning="",  # Empty reasoning
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent",
            metadata=None  # Null metadata
        )
        
        context_graph.add_decision(decision)
        
        node = context_graph.nodes["decision_001"]
        assert node.properties["category"] is None
        assert node.properties["reasoning"] == ""
        assert "metadata" not in node.properties or node.properties["metadata"] is None
    
    def test_extreme_confidence_values(self, context_graph):
        """Test adding decision with extreme confidence values."""
        # Test maximum confidence
        decision_max = Decision(
            decision_id="decision_max",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=1.0,  # Maximum
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        # Test minimum confidence
        decision_min = Decision(
            decision_id="decision_min",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.0,  # Minimum
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(decision_max)
        context_graph.add_decision(decision_min)
        
        node_max = context_graph.nodes["decision_max"]
        node_min = context_graph.nodes["decision_min"]
        
        assert node_max.properties["confidence"] == 1.0
        assert node_min.properties["confidence"] == 0.0
    
    def test_very_long_decision_content(self, context_graph):
        """Test adding decision with very long content."""
        long_scenario = "test " * 10000  # Very long scenario
        long_reasoning = "reasoning " * 5000  # Very long reasoning
        
        decision = Decision(
            decision_id="decision_001",
            category="test",
            scenario=long_scenario,
            reasoning=long_reasoning,
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(decision)
        
        node = context_graph.nodes["decision_001"]
        assert len(node.content) == len(long_scenario)
        assert len(node.properties["reasoning"]) == len(long_reasoning)
    
    def test_future_timestamps(self, context_graph):
        """Test adding decision with future timestamps."""
        future_time = datetime.now() + timedelta(days=1)
        
        decision = Decision(
            decision_id="decision_001",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=future_time,  # Future timestamp
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(decision)
        
        node = context_graph.nodes["decision_001"]
        # Should store future timestamp as-is
        assert node.properties["timestamp"] == future_time.isoformat()
    
    def test_duplicate_decision_addition(self, context_graph):
        """Test adding the same decision twice."""
        decision = Decision(
            decision_id="decision_001",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        # Add decision twice
        context_graph.add_decision(decision)
        context_graph.add_decision(decision)
        
        # Should only have one node
        assert len([n for n in context_graph.nodes.values() if n.node_type == "Decision"]) == 1
        assert "decision_001" in context_graph.nodes
    
    def test_causal_relationship_with_nonexistent_nodes(self, context_graph):
        """Test adding causal relationship when nodes don't exist."""
        # Should not raise error
        context_graph.add_causal_relationship("nonexistent_1", "nonexistent_2", "CAUSED")
        
        # Should not create any edges
        assert len(list(context_graph.edges)) == 0
    
    def test_causal_chain_with_mixed_relationship_types(self, context_graph):
        """Test causal chain with mixed relationship types."""
        # Add decisions
        for i in range(1, 5):
            decision = Decision(
                decision_id=f"decision_{i:03d}",
                category="test",
                scenario=f"scenario {i}",
                reasoning=f"reasoning {i}",
                outcome="test outcome",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(hours=i),
                decision_maker="test_agent"
            )
            context_graph.add_decision(decision)
        
        # Add mixed relationship types
        context_graph.add_causal_relationship("decision_001", "decision_002", "CAUSED")
        context_graph.add_causal_relationship("decision_002", "decision_003", "INFLUENCED")
        context_graph.add_causal_relationship("decision_003", "decision_004", "PRECEDENT_FOR")
        
        # Should follow all causal relationship types
        chain = context_graph.get_causal_chain("decision_001", "downstream", max_depth=5)
        
        assert len(chain) == 3  # Should find all downstream decisions
        decision_ids = [d.decision_id for d in chain]
        assert "decision_002" in decision_ids
        assert "decision_003" in decision_ids
        assert "decision_004" in decision_ids
    
    def test_very_deep_causal_chain(self, context_graph):
        """Test very deep causal chain."""
        # Create deep chain of 50 decisions
        decisions = []
        for i in range(1, 51):
            decision = Decision(
                decision_id=f"decision_{i:03d}",
                category="test",
                scenario=f"scenario {i}",
                reasoning=f"reasoning {i}",
                outcome="test outcome",
                confidence=0.8,
                timestamp=datetime.now() - timedelta(hours=i),
                decision_maker="test_agent"
            )
            decisions.append(decision)
            context_graph.add_decision(decision)
        
        # Add chain relationships
        for i in range(1, 50):
            context_graph.add_causal_relationship(f"decision_{i:03d}", f"decision_{i+1:03d}", "CAUSED")
        
        # Test with reasonable depth limit
        chain = context_graph.get_causal_chain("decision_001", "downstream", max_depth=20)
        
        assert len(chain) == 20  # Limited by max_depth
    
    def self_referencing_causal_relationship(self, context_graph):
        """Test self-referencing causal relationship."""
        decision = Decision(
            decision_id="decision_001",
            category="test",
            scenario="test scenario",
            reasoning="test reasoning",
            outcome="test outcome",
            confidence=0.8,
            timestamp=datetime.now(),
            decision_maker="test_agent"
        )
        
        context_graph.add_decision(decision)
        
        # Add self-referencing relationship
        context_graph.add_causal_relationship("decision_001", "decision_001", "INFLUENCED")
        
        # Should handle self-reference gracefully
        chain = context_graph.get_causal_chain("decision_001", "downstream", max_depth=5)
        
        # Should not include self in causal chain
        assert len(chain) == 0


if __name__ == "__main__":
    pytest.main([__file__])


class TestRecordDecisionReservedKeys:
    """record_decision() must never return an id for a decision it dropped.

    `_add_decision_to_graph` passes a fixed set of keywords to `add_node()` and
    splats the caller's metadata and **kwargs alongside them. A key under one of
    those names arrived twice and raised TypeError, which the surrounding
    handler logged and swallowed — so the caller got a plausible UUID for a
    decision that was never in the graph, and nothing surfaced until a read.
    """

    @pytest.fixture
    def graph(self):
        return ContextGraph()

    def _record(self, graph, **extra):
        return graph.record_decision(
            category="pilot", scenario="Trial", reasoning="because",
            outcome="recorded", confidence=1.0, **extra
        )

    @pytest.mark.parametrize("key", [
        "valid_from", "valid_until", "content", "recorded_at",
        "category", "scenario", "reasoning", "outcome", "confidence",
        "timestamp", "decision_maker",
        "node_id", "node_type", "self",
    ])
    def test_metadata_may_shadow_any_node_property(self, graph, key):
        """A metadata key matching an add_node argument must not drop the node."""
        decision_id = self._record(graph, metadata={key: "2026-01-01T00:00:00"})

        stored = graph.get_nodes_by_label("decision")
        assert len(stored) == 1, f"metadata key {key!r} lost the decision"
        assert stored[0]["id"] == decision_id

    def test_validity_arguments_alongside_matching_metadata(self, graph):
        """The reported case: validity passed explicitly *and* in metadata."""
        decision_id = self._record(
            graph,
            metadata={"valid_from": "2026-01-01T00:00:00"},
            valid_from="2026-02-01T00:00:00",
            valid_until="2026-03-01T00:00:00",
        )

        stored = graph.get_nodes_by_label("decision")
        assert len(stored) == 1
        assert stored[0]["id"] == decision_id

    @pytest.mark.parametrize("key", ["content", "node_id", "node_type"])
    def test_kwargs_may_shadow_a_node_property(self, graph, key):
        """**kwargs lands in the decision mapping and was filtered separately."""
        decision_id = self._record(graph, **{key: "some other value"})

        stored = graph.get_nodes_by_label("decision")
        assert len(stored) == 1
        assert stored[0]["id"] == decision_id

    def test_kwargs_cannot_replace_the_generated_id(self, graph):
        """An "id" kwarg would make the returned id differ from the stored one."""
        with pytest.raises(ValueError, match="reserved"):
            self._record(graph, id="custom-id")
        assert graph.get_nodes_by_label("decision") == []

    def test_a_recorded_id_is_always_present_in_the_graph(self, graph):
        """The invariant the bug violated: returned id => node exists."""
        decision_id = self._record(graph, metadata={"risk": "low"})
        assert graph.find_node(decision_id) is not None

    def test_failure_to_add_is_raised_not_swallowed(self, graph, monkeypatch):
        """A genuine add failure must reach the caller, not log and return an id."""
        def boom(*args, **kwargs):
            raise RuntimeError("storage is down")

        monkeypatch.setattr(graph, "add_node", boom)
        with pytest.raises(RuntimeError, match="storage is down"):
            self._record(graph)

    def test_partial_failure_leaves_no_orphans_and_retry_is_clean(self, graph, monkeypatch):
        """A failure after the decision node is written must roll it back."""
        real_add_edge = graph.add_edge
        calls = {"n": 0}

        def flaky_add_edge(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("edge store failed")
            return real_add_edge(*args, **kwargs)

        monkeypatch.setattr(graph, "add_edge", flaky_add_edge)
        with pytest.raises(RuntimeError, match="edge store failed"):
            self._record(graph, entities=["acme"], decision_maker="alice")

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert graph.get_nodes_by_label("decision") == []

        # The retry succeeds and is the only decision in the graph.
        decision_id = self._record(graph, entities=["acme"], decision_maker="alice")
        stored = graph.get_nodes_by_label("decision")
        assert [n["id"] for n in stored] == [decision_id]
        assert graph.find_node(decision_id) is not None

    def test_rollback_keeps_pre_existing_nodes(self, graph, monkeypatch):
        """Rollback removes only what this call created."""
        graph.add_node("acme", "entity", name="acme")
        monkeypatch.setattr(
            graph, "add_edge",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        with pytest.raises(RuntimeError):
            self._record(graph, entities=["acme"])

        assert set(graph.nodes) == {"acme"}
