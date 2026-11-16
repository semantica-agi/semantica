"""
Decision Tracking Convenience Functions

This module provides convenience functions for decision tracking operations,
offering simple interfaces for common use cases.
"""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional, Union

from ..graph_store import GraphStore
from ..utils.logging import get_logger
from .agent_context import AgentContext
from .decision_models import Decision, Policy
from .decision_recorder import DecisionRecorder
from .decision_query import DecisionQuery
from .causal_analyzer import CausalChainAnalyzer
from .policy_engine import PolicyEngine


def record_decision(
    graph_store: GraphStore,
    category: str,
    scenario: str,
    reasoning: str,
    outcome: str,
    confidence: float,
    entities: Optional[List[str]] = None,
    cross_system_context: Optional[Dict[str, Any]] = None,
    decision_maker: Optional[str] = "ai_agent"
) -> str:
    """
    Convenience function for recording decisions.
    
    Args:
        graph_store: Graph database instance
        category: Decision category
        scenario: Decision scenario
        reasoning: Decision reasoning
        outcome: Decision outcome
        confidence: Confidence score (0-1)
        entities: Optional list of entity IDs
        cross_system_context: Optional cross-system context
        decision_maker: Decision maker identifier
        
    Returns:
        Decision ID
    """
    logger = get_logger(__name__)
    
    try:
        recorder = DecisionRecorder(graph_store)
        
        from .decision_models import Decision
        import uuid
        
        decision = Decision(
            decision_id=str(uuid.uuid4()),
            category=category,
            scenario=scenario,
            reasoning=reasoning,
            outcome=outcome,
            confidence=confidence,
            timestamp=datetime.now(),
            decision_maker=decision_maker or "ai_agent"
        )
        
        entities = entities or []
        source_documents = []  # Could be enhanced to capture source docs
        
        decision_id = recorder.record_decision(decision, entities, source_documents)
        
        # Capture cross-system context if provided
        if cross_system_context:
            recorder.capture_cross_system_context(decision_id, cross_system_context)
        
        logger.info(f"Recorded decision: {decision_id}")
        return decision_id
        
    except Exception as e:
        logger.error(f"Failed to record decision: {e}")
        raise


def find_precedents(
    graph_store: GraphStore,
    scenario: str,
    category: Optional[str] = None,
    limit: int = 10,
    use_hybrid_search: bool = True
) -> List[Decision]:
    """
    Convenience function for finding precedents.
    
    Args:
        graph_store: Graph database instance
        scenario: Scenario to find precedents for
        category: Optional category filter
        limit: Maximum number of results
        use_hybrid_search: Use hybrid search
        
    Returns:
        List of similar decisions
    """
    logger = get_logger(__name__)
    
    try:
        query_engine = DecisionQuery(graph_store)
        
        if use_hybrid_search:
            return query_engine.find_precedents_hybrid(scenario, category, limit)
        else:
            if category:
                return query_engine.find_by_category(category, limit)
            else:
                return query_engine.find_precedents_hybrid(scenario, category, limit)
        
    except Exception as e:
        logger.error(f"Failed to find precedents: {e}")
        raise


def get_causal_chain(
    graph_store: GraphStore,
    decision_id: str,
    direction: str = "upstream",
    max_depth: int = 10
) -> List[Decision]:
    """
    Convenience function for getting causal chains.
    
    Args:
        graph_store: Graph database instance
        decision_id: Decision ID to analyze
        direction: "upstream", "downstream" or "both"
        max_depth: Maximum traversal depth
        
    Returns:
        List of decisions in causal chain
    """
    logger = get_logger(__name__)
    
    try:
        analyzer = CausalChainAnalyzer(graph_store)
        return analyzer.get_causal_chain(decision_id, direction, max_depth)
        
    except Exception as e:
        logger.error(f"Failed to get causal chain: {e}")
        raise


def get_applicable_policies(
    graph_store: GraphStore,
    category: str,
    entities: Optional[List[str]] = None
) -> List[Policy]:
    """
    Convenience function for getting applicable policies.
    
    Args:
        graph_store: Graph database instance
        category: Policy category
        entities: Optional list of entity IDs
        
    Returns:
        List of applicable policies
    """
    logger = get_logger(__name__)
    
    try:
        policy_engine = PolicyEngine(graph_store)
        return policy_engine.get_applicable_policies(category, entities)
        
    except Exception as e:
        logger.error(f"Failed to get applicable policies: {e}")
        raise


def multi_hop_query(
    graph_store: GraphStore,
    start_entity: str,
    query: str,
    max_hops: int = 3
) -> Dict[str, Any]:
    """
    Multi-hop reasoning convenience function.
    
    Args:
        graph_store: Graph database instance
        start_entity: Starting entity ID
        query: Query context
        max_hops: Maximum hops to traverse
        
    Returns:
        Query results with context
    """
    logger = get_logger(__name__)
    
    try:
        query_engine = DecisionQuery(graph_store)
        decisions = query_engine.multi_hop_reasoning(start_entity, query, max_hops)
        
        return {
            "query": query,
            "start_entity": start_entity,
            "max_hops": max_hops,
            "decisions": decisions,
            "count": len(decisions)
        }
        
    except Exception as e:
        logger.error(f"Failed multi-hop query: {e}")
        raise


def capture_decision_trace(
    decision: Decision,
    cross_system_context: Dict[str, Any],
    graph_store: Optional[GraphStore] = None,
    entities: Optional[List[str]] = None,
    source_documents: Optional[List[str]] = None,
    policy_ids: Optional[Union[str, Dict[str, str], List[Union[str, Dict[str, str]]]]] = None,
    exceptions: Optional[List[Dict[str, Any]]] = None,
    approvals: Optional[List[Dict[str, Any]]] = None,
    precedents: Optional[List[Dict[str, str]]] = None,
    immutable_audit_log: bool = True,
) -> str:
    """
    Complete decision trace capture.
    
    Args:
        decision: Decision object to capture
        cross_system_context: Cross-system context
        graph_store: Optional graph store used to persist full trace
        entities: Optional list of linked entities
        source_documents: Optional list of source documents
        policy_ids: Optional list of policy refs. Supports:
            - "policy_id"
            - {"policy_id": "...", "version": "..."}
        exceptions: Optional list of exception records
        approvals: Optional list of approval records
        precedents: Optional list of precedent links
        immutable_audit_log: Whether to append immutable hash-chained trace events
        
    Returns:
        Decision ID
    """
    logger = get_logger(__name__)
    
    try:
        # Backward-compatible behavior: allow legacy call sites without graph_store.
        if graph_store is None:
            policy_refs = _normalize_policy_refs(policy_ids)
            logger.warning(
                "capture_decision_trace skipped persistence (no graph_store) | "
                f"decision_id={decision.decision_id} "
                f"decision_maker={decision.decision_maker} "
                f"timestamp={decision.timestamp.isoformat() if hasattr(decision.timestamp, 'isoformat') else decision.timestamp} "
                f"category={decision.category} "
                f"outcome={decision.outcome} "
                f"confidence={decision.confidence} "
                f"cross_system_keys={list((cross_system_context or {}).keys())} "
                f"policy_refs={policy_refs} "
                f"exception_count={len(_normalize_record_list(exceptions))} "
                f"approval_count={len(_normalize_record_list(approvals))} "
                f"precedent_count={len(_normalize_precedents(precedents))} "
                "mode=backward_compatible_non_persistent"
            )
            return decision.decision_id

        recorder = DecisionRecorder(graph_store)
        entities = _normalize_string_list(entities)
        source_documents = _normalize_string_list(source_documents)
        policy_refs = _normalize_policy_refs(policy_ids)
        exceptions = _normalize_record_list(exceptions)
        approvals = _normalize_record_list(approvals)
        precedents = _normalize_precedents(precedents)

        decision_id = recorder.record_decision(
            decision=decision,
            entities=entities,
            source_documents=source_documents,
        )

        trace_events: List[Dict[str, Any]] = [
            {
                "event_type": "DECISION_RECORDED",
                "payload": {
                    "decision_id": decision_id,
                    "category": decision.category,
                    "outcome": decision.outcome,
                    "confidence": decision.confidence,
                    "decision_maker": decision.decision_maker,
                    "entities": entities,
                    "source_documents": source_documents,
                },
            }
        ]

        if cross_system_context:
            recorder.capture_cross_system_context(decision_id, cross_system_context)
            trace_events.append(
                {
                    "event_type": "CROSS_SYSTEM_CONTEXT_CAPTURED",
                    "payload": {"systems": list(cross_system_context.keys())},
                }
            )

        if policy_refs:
            applied_policies = recorder.apply_policies(decision_id, policy_refs)
            trace_events.append(
                {
                    "event_type": "POLICIES_APPLIED",
                    "payload": {
                        "policy_ids": [p.get("policy_id") for p in policy_refs],
                        "applied_policies": applied_policies,
                    },
                }
            )

        if exceptions:
            recorded_exception_ids: List[str] = []
            for exception_data in exceptions:
                exception_id = recorder.record_exception(
                    decision_id=decision_id,
                    policy_id=exception_data.get("policy_id", ""),
                    reason=exception_data.get("reason", ""),
                    approver=exception_data.get("approver", "system"),
                    approval_method=exception_data.get("approval_method", "system"),
                    justification=exception_data.get("justification", ""),
                )
                recorded_exception_ids.append(exception_id)
            if recorded_exception_ids:
                trace_events.append(
                    {
                        "event_type": "EXCEPTIONS_RECORDED",
                        "payload": {"exception_ids": recorded_exception_ids},
                    }
                )

        if approvals:
            approvers = [a.get("approver", "system") for a in approvals]
            methods = [a.get("approval_method", "system") for a in approvals]
            contexts = [a.get("approval_context", "") for a in approvals]
            if approvers:
                recorder.record_approval_chain(
                    decision_id=decision_id,
                    approvers=approvers,
                    methods=methods,
                    contexts=contexts,
                )
                trace_events.append(
                    {
                        "event_type": "APPROVAL_CHAIN_RECORDED",
                        "payload": {"approvers": approvers, "methods": methods},
                    }
                )

        if precedents:
            precedent_ids = [p.get("precedent_id", "") for p in precedents if p.get("precedent_id")]
            relationship_types = [
                p.get("relationship_type", "similar_scenario")
                for p in precedents
                if p.get("precedent_id")
            ]
            if precedent_ids:
                recorder.link_precedents(decision_id, precedent_ids, relationship_types)
                trace_events.append(
                    {
                        "event_type": "PRECEDENTS_LINKED",
                        "payload": {"precedent_ids": precedent_ids},
                    }
                )

        if immutable_audit_log:
            _append_immutable_trace_events(graph_store, decision_id, trace_events, logger)

        logger.info(f"Captured decision trace for: {decision_id}")
        return decision_id
        
    except Exception as e:
        logger.error(f"Failed to capture decision trace: {e}")
        raise


def _append_immutable_trace_events(
    graph_store: GraphStore,
    decision_id: str,
    events: List[Dict[str, Any]],
    logger: Any,
) -> None:
    """Append hash-chained trace events for immutable decision lineage."""
    if not events:
        return

    previous_trace_id: Optional[str] = None
    previous_hash = ""
    next_index = 1

    try:
        previous_result = graph_store.execute_query(
            """
            MATCH (d:Decision {decision_id: $decision_id})-[:HAS_TRACE_EVENT]->(t:DecisionTraceEvent)
            RETURN t.trace_id as trace_id, t.event_index as event_index, t.event_hash as event_hash
            ORDER BY t.event_index DESC
            LIMIT 1
            """,
            {"decision_id": decision_id},
        )
        records = previous_result.get("records", []) if isinstance(previous_result, dict) else previous_result
        if records:
            latest = records[0]
            latest_map = latest.get("t", latest) if isinstance(latest, dict) else {}
            previous_trace_id = latest_map.get("trace_id")
            previous_hash = latest_map.get("event_hash", "") or ""
            next_index = int(latest_map.get("event_index", 0) or 0) + 1
    except Exception as e:
        logger.warning(
            "Failed to lookup previous immutable trace event; starting new chain "
            f"for decision_id={decision_id}: {e}"
        )
        # Start a fresh chain if previous trace lookup fails.
        previous_trace_id = None
        previous_hash = ""
        next_index = 1

    for event in events:
        event_type = event.get("event_type", "TRACE_EVENT")
        payload = event.get("payload", {})
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        event_timestamp = datetime.now().isoformat()
        trace_id = f"{decision_id}:{next_index}"
        hash_input = (
            f"{decision_id}|{next_index}|{event_type}|{event_timestamp}|{payload_json}|{previous_hash}"
        )
        event_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        graph_store.execute_query(
            """
            MATCH (d:Decision {decision_id: $decision_id})
            CREATE (t:DecisionTraceEvent {
                trace_id: $trace_id,
                decision_id: $decision_id,
                event_index: $event_index,
                event_type: $event_type,
                event_timestamp: $event_timestamp,
                event_payload: $event_payload,
                previous_hash: $previous_hash,
                event_hash: $event_hash
            })
            MERGE (d)-[:HAS_TRACE_EVENT]->(t)
            """,
            {
                "decision_id": decision_id,
                "trace_id": trace_id,
                "event_index": next_index,
                "event_type": event_type,
                "event_timestamp": event_timestamp,
                "event_payload": payload_json,
                "previous_hash": previous_hash,
                "event_hash": event_hash,
            },
        )

        if previous_trace_id:
            graph_store.execute_query(
                """
                MATCH (prev:DecisionTraceEvent {trace_id: $prev_trace_id})
                MATCH (curr:DecisionTraceEvent {trace_id: $curr_trace_id})
                MERGE (prev)-[:NEXT_TRACE_EVENT]->(curr)
                """,
                {"prev_trace_id": previous_trace_id, "curr_trace_id": trace_id},
            )

        previous_trace_id = trace_id
        previous_hash = event_hash
        next_index += 1

    logger.debug(f"Appended {len(events)} immutable trace events for {decision_id}")


def _normalize_string_list(value: Optional[Union[str, List[str]]]) -> List[str]:
    """Normalize optional string/list payloads to a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item)]
    return []


def _normalize_record_list(
    value: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]
) -> List[Dict[str, Any]]:
    """Normalize optional dict/list payloads to list[dict] for legacy callers."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_policy_refs(
    value: Optional[Union[str, Dict[str, str], List[Union[str, Dict[str, str]]]]]
) -> List[Dict[str, str]]:
    """Normalize policy refs to [{policy_id, version?}] for version-safe matching."""
    if value is None:
        return []

    raw_items: List[Union[str, Dict[str, str]]]
    if isinstance(value, (str, dict)):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        return []

    normalized: List[Dict[str, str]] = []
    for item in raw_items:
        if isinstance(item, str) and item:
            normalized.append({"policy_id": item})
        elif isinstance(item, dict):
            policy_id = item.get("policy_id")
            if not policy_id:
                continue
            ref: Dict[str, str] = {"policy_id": str(policy_id)}
            if item.get("version") is not None and str(item.get("version")):
                ref["version"] = str(item.get("version"))
            normalized.append(ref)
    return normalized


def _normalize_precedents(
    value: Optional[Union[str, Dict[str, str], List[Union[str, Dict[str, str]]]]]
) -> List[Dict[str, str]]:
    """Normalize precedents payload from legacy forms to structured records."""
    if value is None:
        return []

    raw_items: List[Union[str, Dict[str, str]]]
    if isinstance(value, (str, dict)):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        return []

    normalized: List[Dict[str, str]] = []
    for item in raw_items:
        if isinstance(item, str) and item:
            normalized.append(
                {"precedent_id": item, "relationship_type": "similar_scenario"}
            )
        elif isinstance(item, dict) and item.get("precedent_id"):
            normalized.append(
                {
                    "precedent_id": str(item.get("precedent_id")),
                    "relationship_type": str(
                        item.get("relationship_type", "similar_scenario")
                    ),
                }
            )
    return normalized


def find_exception_precedents(
    graph_store: GraphStore,
    exception_reason: str,
    limit: int = 10
) -> List["Exception"]:
    """
    Exception precedent search convenience function.
    
    Args:
        graph_store: Graph database instance
        exception_reason: Reason for exception
        limit: Maximum number of results
        
    Returns:
        List of similar exceptions
    """
    logger = get_logger(__name__)
    
    try:
        query_engine = DecisionQuery(graph_store)
        return query_engine.find_similar_exceptions(exception_reason, limit)
        
    except Exception as e:
        logger.error(f"Failed to find exception precedents: {e}")
        raise


def analyze_decision_impact(
    graph_store: GraphStore,
    decision_id: str
) -> Dict[str, Any]:
    """
    Analyze the impact of a decision.
    
    Args:
        graph_store: Graph database instance
        decision_id: Decision ID to analyze
        
    Returns:
        Impact analysis results
    """
    logger = get_logger(__name__)
    
    try:
        analyzer = CausalChainAnalyzer(graph_store)
        
        # Get causal impact score
        impact_score = analyzer.get_causal_impact_score(decision_id)
        
        # Get influenced decisions
        influenced = analyzer.get_influenced_decisions(decision_id, max_depth=5)
        
        # Get root causes
        root_causes = analyzer.find_root_causes(decision_id, max_depth=5)
        
        def _decision_dict(d) -> Dict[str, Any]:
            return {
                "decision_id": d.decision_id,
                "scenario": d.scenario,
                "category": d.category,
                "outcome": d.outcome,
                "confidence": d.confidence,
            }

        return {
            "decision_id": decision_id,
            "impact_score": impact_score,
            "influenced_decisions": [_decision_dict(d) for d in influenced],
            "root_causes": [_decision_dict(d) for d in root_causes],
            "total_influenced": len(influenced),
            "total_root_causes": len(root_causes),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze decision impact: {e}")
        raise


def create_policy_with_versioning(
    graph_store: GraphStore,
    name: str,
    description: str,
    rules: Dict[str, Any],
    category: str,
    version: str = "1.0"
) -> str:
    """
    Create a policy with automatic versioning.
    
    Args:
        graph_store: Graph database instance
        name: Policy name
        description: Policy description
        rules: Policy rules
        category: Policy category
        version: Initial version
        
    Returns:
        Policy ID
    """
    logger = get_logger(__name__)
    
    try:
        policy_engine = PolicyEngine(graph_store)
        
        import uuid
        policy = Policy(
            policy_id=str(uuid.uuid4()),
            name=name,
            description=description,
            rules=rules,
            category=category,
            version=version,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        policy_id = policy_engine.add_policy(policy)
        logger.info(f"Created policy: {policy_id} version {version}")
        return policy_id
        
    except Exception as e:
        logger.error(f"Failed to create policy: {e}")
        raise


def check_decision_compliance(
    graph_store: GraphStore,
    decision_id: str,
    policy_id: str
) -> Dict[str, Any]:
    """
    Check if a decision complies with a policy.
    
    Args:
        graph_store: Graph database instance
        decision_id: Decision ID to check
        policy_id: Policy ID to check against
        
    Returns:
        Compliance check results
    """
    logger = get_logger(__name__)
    
    try:
        # Get decision details
        query_engine = DecisionQuery(graph_store)
        decisions = query_engine.find_by_time_range(
            datetime.now().replace(year=2000), datetime.now(), limit=1000
        )
        
        decision = None
        for d in decisions:
            if d.decision_id == decision_id:
                decision = d
                break
        
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        # Check compliance
        policy_engine = PolicyEngine(graph_store)
        is_compliant = policy_engine.check_compliance(decision, policy_id)
        
        # Record policy application
        policy = policy_engine.get_policy(policy_id)
        if policy:
            policy_engine.record_policy_application(decision_id, policy_id, policy.version)
        
        return {
            "decision_id": decision_id,
            "policy_id": policy_id,
            "is_compliant": is_compliant,
            "compliance_check_timestamp": datetime.now().isoformat(),
            "decision_category": decision.category,
            "decision_confidence": decision.confidence
        }
        
    except Exception as e:
        logger.error(f"Failed to check decision compliance: {e}")
        raise


def get_decision_statistics(
    graph_store: GraphStore,
    category: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get decision statistics for analysis.
    
    Args:
        graph_store: Graph database instance
        category: Optional category filter
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Decision statistics
    """
    logger = get_logger(__name__)
    
    try:
        query_engine = DecisionQuery(graph_store)
        
        # Get decisions based on filters
        if start_date and end_date:
            decisions = query_engine.find_by_time_range(start_date, end_date, limit=1000)
        elif category:
            decisions = query_engine.find_by_category(category, limit=1000)
        else:
            decisions = query_engine.find_by_time_range(
                datetime.now().replace(year=2020), datetime.now(), limit=1000
            )
        
        # Calculate statistics
        total_decisions = len(decisions)
        
        if total_decisions == 0:
            return {
                "total_decisions": 0,
                "categories": {},
                "outcomes": {},
                "average_confidence": 0.0,
                "date_range": {"start": None, "end": None}
            }
        
        # Category distribution
        categories = {}
        for decision in decisions:
            cat = decision.category
            categories[cat] = categories.get(cat, 0) + 1
        
        # Outcome distribution
        outcomes = {}
        for decision in decisions:
            outcome = decision.outcome
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        # Average confidence
        avg_confidence = sum(d.confidence for d in decisions) / total_decisions
        
        # Date range
        timestamps = [d.timestamp for d in decisions if d.timestamp]
        date_range = {
            "start": min(timestamps).isoformat() if timestamps else None,
            "end": max(timestamps).isoformat() if timestamps else None
        }
        
        return {
            "total_decisions": total_decisions,
            "categories": categories,
            "outcomes": outcomes,
            "average_confidence": avg_confidence,
            "date_range": date_range,
            "filters_applied": {
                "category": category,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get decision statistics: {e}")
        raise


def setup_decision_tracking(
    graph_store: GraphStore,
    create_sample_data: bool = False
) -> bool:
    """
    Set up decision tracking schema and optionally create sample data.
    
    Args:
        graph_store: Graph database instance
        create_sample_data: Whether to create sample data
        
    Returns:
        True if setup successful
    """
    logger = get_logger(__name__)
    
    try:
        from .graph_schema import setup_decision_schema, verify_schema, create_sample_data as create_sample
        
        # Setup schema
        setup_decision_schema(graph_store)
        
        # Verify schema
        if not verify_schema(graph_store):
            raise ValueError("Schema verification failed")
        
        # Create sample data if requested
        if create_sample_data:
            create_sample(graph_store)
        
        logger.info("Decision tracking setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup decision tracking: {e}")
        return False


# Method dispatch support for AgentContext
def enhance_agent_context_with_decisions(agent_context: AgentContext) -> None:
    """
    Enhance AgentContext with decision tracking methods if not already enabled.
    
    Args:
        agent_context: AgentContext instance to enhance
    """
    logger = get_logger(__name__)
    
    try:
        if not agent_context.config.get("decision_tracking"):
            logger.warning("Decision tracking not enabled in AgentContext")
            return
        
        # Verify decision tracking components are available
        if not all([
            agent_context._decision_recorder,
            agent_context._decision_query,
            agent_context._causal_analyzer,
            agent_context._policy_engine
        ]):
            logger.warning("Decision tracking components not properly initialized")
            return
        
        logger.info("AgentContext enhanced with decision tracking")
        
    except Exception as e:
        logger.error(f"Failed to enhance AgentContext: {e}")


# Export all convenience functions
__all__ = [
    "record_decision",
    "find_precedents", 
    "get_causal_chain",
    "get_applicable_policies",
    "multi_hop_query",
    "capture_decision_trace",
    "find_exception_precedents",
    "analyze_decision_impact",
    "create_policy_with_versioning",
    "check_decision_compliance",
    "get_decision_statistics",
    "setup_decision_tracking",
    "enhance_agent_context_with_decisions"
]
