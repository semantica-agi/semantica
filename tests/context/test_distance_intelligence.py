from semantica.context.context_graph import ContextGraph


def test_get_neighbor_distances_tracks_path_decay_and_band():
    graph = ContextGraph(advanced_analytics=False)
    graph.add_node("A", "entity", "Anchor")
    graph.add_node("B", "entity", "Bridge")
    graph.add_node("C", "decision", "Decision")
    graph.add_edge("A", "B", "influences", weight=0.9)
    graph.add_edge("B", "C", "influences", weight=0.7)

    neighbors = graph.get_neighbor_distances("A", hops=2, min_confidence=0.5)
    c_neighbor = next(item for item in neighbors if item["id"] == "C")

    assert c_neighbor["hop"] == 2
    assert c_neighbor["distance_band"] == "near"
    assert c_neighbor["confidence_decay"] == 0.63
    assert c_neighbor["path_to_anchor"] == ["A", "B", "C"]


def test_trace_decision_causality_returns_auditable_chain_dicts():
    graph = ContextGraph(advanced_analytics=False)
    first = graph.record_decision(
        category="risk",
        scenario="Approve initial risk policy",
        reasoning="Baseline risk controls look sound",
        outcome="approved",
        confidence=0.8,
        entities=["account_123"],
    )
    second = graph.record_decision(
        category="risk",
        scenario="Approve follow-up risk exception",
        reasoning="Prior account controls still apply",
        outcome="approved",
        confidence=0.9,
        entities=["account_123"],
    )
    graph._decisions[first]["timestamp"] = 1
    graph._decisions[second]["timestamp"] = 2

    chains = graph.trace_decision_causality(second, max_depth=2)

    assert chains
    assert chains[0]["hop_count"] == 1
    assert chains[0]["distance_band"] == "direct"
    assert chains[0]["weakest_link"]["from"] == first
    assert chains[0]["hops"][0]["to"] == second
    assert "confidence" in chains[0]["interpretation"]
    assert list(chains[0])[0]["from"] == first


def test_analyze_decision_influence_exposes_score_breakdown():
    graph = ContextGraph(advanced_analytics=False)
    source = graph.record_decision(
        category="loan",
        scenario="Approve secured loan",
        reasoning="Collateral and income verified",
        outcome="approved",
        confidence=0.9,
        entities=["borrower_1"],
    )
    graph.record_decision(
        category="loan",
        scenario="Review related refinance",
        reasoning="Same borrower and collateral",
        outcome="review",
        confidence=0.8,
        entities=["borrower_1"],
    )

    result = graph.analyze_decision_influence(source)

    assert result["influence_scores"]
    score = result["influence_scores"][0]
    assert set(score["score_breakdown"]) == {
        "entity_overlap",
        "category_match",
        "temporal_proximity",
    }
    assert score["is_direct"] is True


def test_cross_graph_path_traverses_link_boundary():
    left = ContextGraph(advanced_analytics=False)
    right = ContextGraph(advanced_analytics=False)
    left.add_node("A", "entity", "Left")
    right.add_node("B", "entity", "Right")
    left.link_graph(right, "A", "B")

    path = left.cross_graph_path("A", right, "B")

    assert path["reachable"] is True
    assert path["hop_count"] == 1
    assert path["cross_graph_links_used"] == 1
    assert path["distance_band"] == "direct"
    assert path["path"] == [(left.graph_id, "A"), (right.graph_id, "B")]
