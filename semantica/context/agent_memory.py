"""
Agent Memory Manager

This module provides comprehensive agent memory management and context retrieval,
integrating RAG (Retrieval-Augmented Generation) with knowledge graphs to give
agents persistent context across conversations and interactions.

Algorithms Used:

Memory Storage:
    - Vector Embedding: Embedding generation for memory items using embedding models
    - Vector Indexing: Vector store indexing for efficient similarity search
    - Memory Indexing: Deque-based memory index for efficient temporal access
    - Knowledge Graph Integration: Entity and relationship updates to knowledge graph
    - Metadata Storage: Dictionary-based metadata storage and retrieval

Memory Retrieval:
    - Vector Similarity Search: Cosine similarity search in vector space
    - Keyword Search: Fallback keyword-based search using word overlap
    - Score Ranking: Relevance score-based result ranking
    - Filter Matching: Metadata-based filtering (type, date range, etc.)
    - Result Deduplication: Content-based deduplication of results

Memory Management:
    - Retention Policy: Time-based memory retention and cleanup
    - Memory Statistics: Counter-based statistics tracking
    - Conversation History: Temporal-based conversation history retrieval
    - Memory Deletion: Cascading deletion from vector store and memory index

Key Features:
    - Persistent memory storage for agents
    - Vector-based context retrieval with embedding support
    - Knowledge graph context integration
    - Conversation history management
    - Context accumulation over time
    - Memory retrieval for agent decision-making
    - Retention policy management (time-based cleanup)
    - Memory statistics and analytics
    - Metadata-based filtering and search
    - Fallback keyword search when vector store unavailable

Main Classes:
    - MemoryItem: Memory item data structure with content, timestamp, metadata,
      entities, relationships
    - AgentMemory: Agent memory manager with RAG integration

Example Usage:
    >>> from semantica.context import AgentMemory
    >>> memory = AgentMemory(vector_store=vs, knowledge_graph=kg)
    >>> memory_id = memory.store(
    ...     "User asked about Python", metadata={"type": "conversation"}
    ... )
    >>> results = memory.retrieve("Python", max_results=5)
    >>> history = memory.get_conversation_history(conversation_id="conv_123")
    >>> stats = memory.get_statistics()

Author: Semantica Contributors
License: MIT
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import numpy as np

from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from ..utils.types import EntityDict, RelationshipDict


@dataclass
class MemoryItem:
    """Memory item structure."""

    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    entities: List[EntityDict] = field(default_factory=list)
    relationships: List[RelationshipDict] = field(default_factory=list)
    embedding: Optional[Any] = None
    memory_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dict. Embeddings are dropped (not JSON-safe)."""
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "entities": self.entities,
            "relationships": self.relationships,
            "memory_id": self.memory_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """Reconstruct a MemoryItem from a serialised dict."""
        raw_ts = data.get("timestamp")
        try:
            ts = datetime.fromisoformat(raw_ts) if raw_ts else datetime.utcnow()
        except (ValueError, TypeError):
            ts = datetime.utcnow()
        return cls(
            content=data.get("content", ""),
            timestamp=ts,
            metadata=data.get("metadata", {}),
            entities=data.get("entities", []),
            relationships=data.get("relationships", []),
            embedding=None,  # embeddings are not persisted; regenerate on demand
            memory_id=data.get("memory_id"),
        )


class AgentMemory:
    """
    Agent memory manager with RAG integration and Hierarchical Memory.

    • Short-term Memory: In-memory buffer for recent context
    • Long-term Memory: Vector store for persistent semantic history
    • Knowledge Graph: Structured context integration
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize agent memory.

        Args:
            config: Configuration dictionary
            **kwargs: Additional configuration options:
                - vector_store: Vector store instance
                - knowledge_graph: Knowledge graph instance
                - retention_policy: Memory retention policy
                - max_memory_size: Max items in memory index
                - short_term_limit: Size of short-term memory buffer (default: 10)
        """
        self.logger = get_logger("agent_memory")
        self.config = config or {}
        self.config.update(kwargs)

        self.vector_store = self.config.get("vector_store")
        self.knowledge_graph = self.config.get("knowledge_graph")

        self.retention_policy = self.config.get("retention_policy", "unlimited")
        self.max_memory_size = self.config.get("max_memory_size", 10000)
        self.short_term_limit = self.config.get("short_term_limit", 10)
        self.token_limit = self.config.get("token_limit", 2000)

        # In-memory storage
        self.memory_items: Dict[str, MemoryItem] = {}
        self.memory_index: deque = deque(maxlen=self.max_memory_size)

        # Hierarchical Memory: Short-term buffer
        # Note: We use a list for flexible pruning (tokens & count).
        self.short_term_memory: List[MemoryItem] = []

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        # Statistics
        self.stats = {"total_items": 0, "items_by_type": {}, "last_accessed": None}

    def save(self, path: str) -> None:
        """
        Save memory state to disk.

        Args:
            path: Directory path to save to
        """
        import json
        import os

        os.makedirs(path, exist_ok=True)

        data = {
            "memory_items": {k: v.to_dict() for k, v in self.memory_items.items()},
            "memory_index": list(self.memory_index),
            "short_term_memory": [item.to_dict() for item in self.short_term_memory],
            "stats": self.stats,
        }

        with open(os.path.join(path, "agent_memory.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)

        self.logger.info(f"Saved agent memory to {path}")

    def load(self, path: str) -> None:
        """
        Load memory state from disk.

        Args:
            path: Directory path to load from
        """
        import json
        import os

        # Support new JSON format; fall back to legacy filename only if it exists
        json_path = os.path.join(path, "agent_memory.json")
        legacy_path = os.path.join(path, "agent_memory.pkl")

        if os.path.exists(json_path):
            file_path = json_path
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif os.path.exists(legacy_path):
            # Legacy pickle files: refuse to load them to prevent deserialization attacks.
            # Users must re-save memory in the new JSON format.
            self.logger.warning(
                f"Legacy pickle file found at {legacy_path}. "
                "Pickle loading is disabled for security. Re-save memory to migrate."
            )
            return
        else:
            self.logger.warning(f"Memory file not found in: {path}")
            return

        raw_items = data.get("memory_items", {})
        self.memory_items = {
            k: MemoryItem.from_dict(v) for k, v in raw_items.items()
        }
        raw_index = data.get("memory_index", [])
        self.memory_index = deque(raw_index, maxlen=self.max_memory_size)
        self.short_term_memory = [
            MemoryItem.from_dict(item) for item in data.get("short_term_memory", [])
        ]
        self.stats = data.get(
            "stats",
            {"total_items": 0, "items_by_type": {}, "last_accessed": None},
        )

        self.logger.info(f"Loaded agent memory from {path}")

    def store(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        entities: Optional[List[EntityDict]] = None,
        relationships: Optional[List[RelationshipDict]] = None,
        **options,
    ) -> str:
        """
        Store memory item (Write-Through to Short-term and Long-term).

        Args:
            content: Memory content
            metadata: Additional metadata
            entities: Related entities
            relationships: Related relationships
            **options: Additional options:
                - memory_id: Custom memory ID
                - timestamp: Custom timestamp
                - skip_vector: If True, skip vector store (Short-term only)

        Returns:
            Memory ID
        """
        # Track memory storage
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="context",
            submodule="AgentMemory",
            message=f"Storing memory: {content[:50]}...",
        )

        try:
            memory_id = options.get("memory_id") or self._generate_memory_id()
            timestamp = options.get("timestamp") or datetime.now()

            # Create memory item
            memory_item = MemoryItem(
                content=content,
                timestamp=timestamp,
                metadata=metadata or {},
                entities=entities or [],
                relationships=relationships or [],
                memory_id=memory_id,
            )

            # 1. Update Short-Term Memory
            self.short_term_memory.append(memory_item)
            self._prune_short_term_memory()

            # 2. Update Long-Term Memory (Vector Store)
            skip_vector = options.get("skip_vector", False)
            if self.vector_store and not skip_vector:
                try:
                    self.progress_tracker.update_tracking(
                        tracking_id, message="Generating embedding..."
                    )
                    embedding = self._generate_embedding(content)
                    memory_item.embedding = embedding

                    # Store in vector store
                    if hasattr(self.vector_store, "store_vectors"):
                        # Use concrete VectorStore implementation
                        if isinstance(memory_item.embedding, list):
                            vectors = [np.array(memory_item.embedding)]
                        else:
                            vectors = [memory_item.embedding]
                        meta = [memory_item.metadata]
                        self.vector_store.store_vectors(vectors=vectors, metadata=meta)
                    elif hasattr(self.vector_store, "add"):
                        # Use VectorStore protocol
                        self.vector_store.add([memory_item])
                except Exception as e:
                    self.logger.warning(f"Failed to store in vector store: {e}")

            # Store in main memory dict (Persistent Layer Abstraction)
            self.memory_items[memory_id] = memory_item
            self.memory_index.append(memory_id)

            # 3. Update Knowledge Graph
            if self.knowledge_graph and entities:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Updating knowledge graph..."
                )
                self._update_knowledge_graph(entities, relationships)

            # Update statistics
            self.stats["total_items"] += 1
            item_type = metadata.get("type", "general") if metadata else "general"
            self.stats["items_by_type"][item_type] = (
                self.stats["items_by_type"].get(item_type, 0) + 1
            )

            self.logger.debug(f"Stored memory item: {memory_id}")

            # Apply retention policy
            self._apply_retention_policy()

            self.progress_tracker.stop_tracking(
                tracking_id, status="completed", message=f"Stored memory: {memory_id}"
            )
            return memory_id

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def forget(self, memory_id: str) -> bool:
        """Forget a memory (Implementation of MemoryManager)."""
        return self.delete_memory(memory_id)

    def retrieve(
        self, query: str, max_results: int = 5, min_score: float = 0.0, **filters
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories.

        Args:
            query: Search query
            max_results: Maximum number of results
            min_score: Minimum relevance score
            **filters: Additional filters:
                - type: Filter by memory type
                - start_date: Filter by start date
                - end_date: Filter by end date

        Returns:
            List of retrieved memory items
        """
        # Track memory retrieval
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="context",
            submodule="AgentMemory",
            message=f"Retrieving memories for: {query[:50]}...",
        )

        try:
            results = []
            seen_ids = set()

            # 1. Check Short-Term Memory (Recent Context)
            short_term_results = self._search_short_term(query, filters)
            for res in short_term_results:
                if res["memory_id"] not in seen_ids:
                    results.append(res)
                    seen_ids.add(res["memory_id"])

            # 2. Vector-based retrieval (Long-Term Memory)
            if self.vector_store:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Searching vector store..."
                )
                try:
                    vector_results = []
                    if hasattr(self.vector_store, "search_vectors"):
                        # Use concrete VectorStore implementation
                        query_vector = self._generate_embedding(query)
                        if isinstance(query_vector, list):
                            query_vector = np.array(query_vector)

                        raw_results = self.vector_store.search_vectors(
                            query_vector=query_vector, k=max_results * 2
                        )
                        # Convert dict results to objects with .id attribute

                        class ResultObj:
                            def __init__(self, d):
                                self.id = d.get("id")
                                self.score = d.get("score")
                                self.metadata = d.get("metadata")

                        vector_results = [ResultObj(r) for r in raw_results]

                    elif hasattr(self.vector_store, "search"):
                        vector_results = self.vector_store.search(
                            query=query, limit=max_results * 2
                        )

                        for result in vector_results:
                            memory_id = result.id

                            # Skip if already found in short-term
                            if memory_id in seen_ids:
                                continue

                            if memory_id in self.memory_items:
                                memory_item = self.memory_items[memory_id]

                                # Apply filters
                                if not self._matches_filters(memory_item, filters):
                                    continue

                                results.append(
                                    {
                                        "memory_id": memory_id,
                                        "content": memory_item.content,
                                        "score": result.score,
                                        "timestamp": memory_item.timestamp.isoformat(),
                                        "metadata": memory_item.metadata,
                                        "entities": memory_item.entities,
                                        "relationships": memory_item.relationships,
                                    }
                                )
                                seen_ids.add(memory_id)
                except Exception as e:
                    self.logger.warning(f"Vector retrieval failed: {e}")

            # 3. Fallback to keyword search if no results yet
            if not results:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Performing keyword search..."
                )
                results = self._keyword_search(query, max_results, filters)

            # Sort by score and return top results
            self.progress_tracker.update_tracking(
                tracking_id, message="Ranking results..."
            )
            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            filtered_results = [r for r in results if r.get("score", 0.0) >= min_score]

            self.stats["last_accessed"] = datetime.now().isoformat()

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Retrieved {len(filtered_results[:max_results])} memories",
            )
            return filtered_results[:max_results]

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific memory item.

        Args:
            memory_id: Memory identifier

        Returns:
            Memory item dictionary or None if not found
        """
        if memory_id not in self.memory_items:
            return None

        memory_item = self.memory_items[memory_id]

        return {
            "memory_id": memory_id,
            "content": memory_item.content,
            "timestamp": memory_item.timestamp.isoformat(),
            "metadata": memory_item.metadata,
            "entities": memory_item.entities,
            "relationships": memory_item.relationships,
        }

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete memory item.

        Args:
            memory_id: Memory identifier

        Returns:
            True if deleted successfully
        """
        if memory_id not in self.memory_items:
            return False

        # Remove from vector store
        if self.vector_store and hasattr(self.vector_store, "delete"):
            try:
                self.vector_store.delete(memory_id)
            except Exception as e:
                self.logger.warning(f"Failed to delete from vector store: {e}")

        # Remove from memory
        del self.memory_items[memory_id]

        # Remove from index
        if memory_id in self.memory_index:
            self.memory_index.remove(memory_id)

        self.stats["total_items"] = max(0, self.stats["total_items"] - 1)

        self.logger.debug(f"Deleted memory item: {memory_id}")
        return True

    def clear_memory(self, **filters) -> int:
        """
        Clear memory items matching filters.

        Args:
            **filters: Filter criteria

        Returns:
            Number of items deleted
        """
        deleted_count = 0
        memory_ids_to_delete = []

        for memory_id, memory_item in self.memory_items.items():
            if self._matches_filters(memory_item, filters):
                memory_ids_to_delete.append(memory_id)

        for memory_id in memory_ids_to_delete:
            if self.delete_memory(memory_id):
                deleted_count += 1

        return deleted_count

    def get_conversation_history(
        self, conversation_id: Optional[str] = None, max_items: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history.

        Args:
            conversation_id: Optional conversation ID filter
            max_items: Maximum number of items

        Returns:
            List of conversation items
        """
        history = []

        for memory_id in list(self.memory_index)[-max_items:]:
            memory_item = self.memory_items.get(memory_id)
            if not memory_item:
                continue

            # Filter by conversation ID if provided
            if conversation_id:
                item_conv_id = memory_item.metadata.get("conversation_id")
                if item_conv_id != conversation_id:
                    continue

            # Check if it's a conversation item
            if memory_item.metadata.get("type") == "conversation":
                history.append(
                    {
                        "memory_id": memory_id,
                        "content": memory_item.content,
                        "timestamp": memory_item.timestamp.isoformat(),
                        "metadata": memory_item.metadata,
                    }
                )

        return history

    def _search_short_term(
        self, query: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search short-term memory (simple keyword match)."""
        results = []
        query_terms = query.lower().split()

        # Iterate through short-term memory (most recent first)
        for item in reversed(self.short_term_memory):
            if not self._matches_filters(item, filters):
                continue

            content_lower = item.content.lower()

            # Simple scoring based on term overlap
            matches = sum(1 for term in query_terms if term in content_lower)
            if matches > 0:
                score = matches / len(query_terms)
                # Boost score for recent items (short-term)
                score = min(1.0, score + 0.1)

                results.append(
                    {
                        "memory_id": item.memory_id,
                        "content": item.content,
                        "score": score,
                        "timestamp": item.timestamp.isoformat(),
                        "metadata": item.metadata,
                        "entities": item.entities,
                        "relationships": item.relationships,
                        "source": "short_term",
                    }
                )

        return results

    def _generate_memory_id(self) -> str:
        """Generate unique memory ID."""
        import hashlib
        import time

        timestamp = str(time.time())
        random_str = str(hash(str(self.memory_items)) % 10000)
        memory_hash = hashlib.md5(f"{timestamp}_{random_str}".encode()).hexdigest()[:12]

        return f"mem_{memory_hash}"

    def _prune_short_term_memory(self) -> None:
        """
        Prune short-term memory based on count and token limits.

        Removes oldest items until constraints are met.
        """
        # 1. Prune by count
        while len(self.short_term_memory) > self.short_term_limit:
            self.short_term_memory.pop(0)  # Remove oldest

        # 2. Prune by tokens
        current_tokens = sum(
            self._count_tokens(item.content) for item in self.short_term_memory
        )

        while current_tokens > self.token_limit and self.short_term_memory:
            removed_item = self.short_term_memory.pop(0)  # Remove oldest
            current_tokens -= self._count_tokens(removed_item.content)

    def _count_tokens(self, text: str) -> int:
        """
        Estimate token count (approximation).

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        # Simple approximation: 1 token ≈ 4 characters
        return len(text) // 4

    def _generate_embedding(self, content: str) -> Any:
        """Generate embedding for content."""
        # This would use an embedding model
        # For now, return placeholder
        if hasattr(self.vector_store, "embed"):
            return self.vector_store.embed(content)
        return None

    def _update_knowledge_graph(
        self,
        entities: List[EntityDict],
        relationships: Optional[List[RelationshipDict]],
    ) -> None:
        """Update knowledge graph with new entities and relationships."""
        if not self.knowledge_graph:
            return

        # Check for GraphStore protocol (add_nodes method)
        if hasattr(self.knowledge_graph, "add_nodes"):
            # Convert to dicts for ContextGraph
            graph_nodes = []
            for entity in entities:
                entity_id = entity.get("id") or entity.get("entity_id")
                if entity_id:
                    graph_nodes.append(
                        {
                            "id": entity_id,
                            "type": entity.get("type", "entity"),
                            "properties": {
                                "content": (
                                    entity.get("text")
                                    or entity.get("label")
                                    or entity_id
                                ),
                                **entity,
                            },
                        }
                    )
            if graph_nodes:
                self.knowledge_graph.add_nodes(graph_nodes)

            if relationships:
                graph_edges = []
                for rel in relationships:
                    source = rel.get("source_id")
                    target = rel.get("target_id")
                    if source and target:
                        graph_edges.append(
                            {
                                "source_id": source,
                                "target_id": target,
                                "type": rel.get("type", "related_to"),
                                "weight": rel.get("confidence", 1.0),
                                "properties": rel,
                            }
                        )
                if graph_edges:
                    self.knowledge_graph.add_edges(graph_edges)

            return

        # Legacy dict update
        # Add entities to graph
        graph_entities = self.knowledge_graph.get("entities", [])
        existing_ids = {e.get("id") for e in graph_entities}

        for entity in entities:
            entity_id = entity.get("id")
            if entity_id and entity_id not in existing_ids:
                graph_entities.append(entity)

        self.knowledge_graph["entities"] = graph_entities

        # Add relationships
        if relationships:
            graph_relationships = self.knowledge_graph.get("relationships", [])
            graph_relationships.extend(relationships)
            self.knowledge_graph["relationships"] = graph_relationships

    def _matches_filters(
        self, memory_item: MemoryItem, filters: Dict[str, Any]
    ) -> bool:
        """Check if memory item matches filters."""
        # Filter by type
        if "type" in filters:
            item_type = memory_item.metadata.get("type")
            if item_type != filters["type"]:
                return False

        # Filter by date range
        if "start_date" in filters:
            start_date = filters["start_date"]
            if isinstance(start_date, str):
                from dateutil.parser import parse

                start_date = parse(start_date)
            if memory_item.timestamp < start_date:
                return False

        if "end_date" in filters:
            end_date = filters["end_date"]
            if isinstance(end_date, str):
                from dateutil.parser import parse

                end_date = parse(end_date)
            if memory_item.timestamp > end_date:
                return False

        return True

    def _keyword_search(
        self, query: str, max_results: int, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fallback keyword search."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        results = []

        for memory_id, memory_item in self.memory_items.items():
            if not self._matches_filters(memory_item, filters):
                continue

            content_lower = memory_item.content.lower()
            content_words = set(content_lower.split())

            # Calculate simple word overlap score
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / len(query_words)
                results.append(
                    {
                        "memory_id": memory_id,
                        "content": memory_item.content,
                        "score": score,
                        "timestamp": memory_item.timestamp.isoformat(),
                        "metadata": memory_item.metadata,
                        "entities": memory_item.entities,
                        "relationships": memory_item.relationships,
                    }
                )

        return results

    def _apply_retention_policy(self) -> None:
        """Apply memory retention policy."""
        if self.retention_policy == "unlimited":
            return

        # Parse retention policy
        if isinstance(self.retention_policy, str) and "_days" in self.retention_policy:
            try:
                days = int(self.retention_policy.replace("_days", ""))
            except ValueError:
                days = 30
        else:
            days = 30

        cutoff_date = datetime.now() - timedelta(days=days)

        # Delete old items
        memory_ids_to_delete = []
        for memory_id, memory_item in self.memory_items.items():
            if memory_item.timestamp < cutoff_date:
                memory_ids_to_delete.append(memory_id)

        for memory_id in memory_ids_to_delete:
            self.delete_memory(memory_id)

        if memory_ids_to_delete:
            self.logger.info(
                f"Deleted {len(memory_ids_to_delete)} items based on retention policy"
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get memory statistics.

        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            "current_items": len(self.memory_items),
            "max_size": self.max_memory_size,
            "retention_policy": self.retention_policy,
        }

    # Basic Operations
    def exists(self, memory_id: str) -> bool:
        """
        Check if memory exists.

        Args:
            memory_id: Memory ID to check

        Returns:
            True if exists, False otherwise

        Example:
            >>> if memory.exists("mem123"):
            ...     print("Memory exists")
        """
        return memory_id in self.memory_items

    def count(self, **filters) -> int:
        """
        Get count with filters.

        Args:
            **filters: Filter criteria

        Returns:
            Count of memories matching filters

        Example:
            >>> total = memory.count()
            >>> conv_count = memory.count(conversation_id="conv1")
        """
        if not filters:
            return len(self.memory_items)

        count = 0
        for memory_id, memory_item in self.memory_items.items():
            if self._matches_filters(memory_item, filters):
                count += 1
        return count

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory dict or None if not found

        Example:
            >>> memory = memory.get("mem123")
        """
        return self.get_memory(memory_id)

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> bool:
        """
        Update memory.

        Args:
            memory_id: Memory ID to update
            content: New content (optional)
            metadata: New metadata (optional, merged with existing)
            **kwargs: Additional fields to update

        Returns:
            True if updated, False if not found

        Example:
            >>> memory.update("mem123", content="Updated content")
        """
        if memory_id not in self.memory_items:
            return False

        memory_item = self.memory_items[memory_id]
        current_content = content if content is not None else memory_item.content
        current_metadata = memory_item.metadata.copy()
        if metadata:
            current_metadata.update(metadata)

        # Delete old and create new
        self.delete_memory(memory_id)
        new_id = self.store(
            current_content,
            metadata=current_metadata,
            entities=memory_item.entities,
            relationships=memory_item.relationships,
            **kwargs,
        )

        return new_id is not None

    def delete(self, memory_id: str) -> bool:
        """
        Delete memory (alias for delete_memory).

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found

        Example:
            >>> memory.delete("mem123")
        """
        return self.delete_memory(memory_id)

    def clear(self, **filters) -> int:
        """
        Clear with filters (alias for clear_memory).

        Args:
            **filters: Filter criteria

        Returns:
            Number of memories deleted

        Example:
            >>> deleted = memory.clear(conversation_id="conv1")
        """
        return self.clear_memory(**filters)

    # Search Methods
    def search(self, query: str, **filters) -> List[Dict[str, Any]]:
        """
        Simple search (alias for retrieve).

        Args:
            query: Search query
            **filters: Additional filters

        Returns:
            List of memory dicts

        Example:
            >>> results = memory.search("Python", max_results=10)
        """
        return self.retrieve(query, **filters)

    def find_similar(
        self, content: str, limit: int = 5, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Find similar content.

        Args:
            content: Content to find similar items for
            limit: Maximum results (default: 5)
            **kwargs: Additional options

        Returns:
            List of similar memory dicts

        Example:
            >>> similar = memory.find_similar("Python programming", limit=5)
        """
        return self.retrieve(content, max_results=limit, **kwargs)

    def find_by_entity(self, entity_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find by entity.

        Args:
            entity_id: Entity ID to search for
            limit: Maximum results (default: 10)

        Returns:
            List of memory dicts containing the entity

        Example:
            >>> results = memory.find_by_entity("entity_123")
        """
        results = []
        for memory_id, memory_item in self.memory_items.items():
            for entity in memory_item.entities:
                if entity.get("id") == entity_id:
                    mem_dict = self.get_memory(memory_id)
                    if mem_dict:
                        results.append(mem_dict)
                    break
            if len(results) >= limit:
                break
        return results[:limit]

    def find_by_relationship(
        self, relationship_type: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find by relationship.

        Args:
            relationship_type: Relationship type to search for
            limit: Maximum results (default: 10)

        Returns:
            List of memory dicts containing the relationship

        Example:
            >>> results = memory.find_by_relationship("related_to")
        """
        results = []
        for memory_id, memory_item in self.memory_items.items():
            for relationship in memory_item.relationships:
                if relationship.get("type") == relationship_type:
                    mem_dict = self.get_memory(memory_id)
                    if mem_dict:
                        results.append(mem_dict)
                    break
            if len(results) >= limit:
                break
        return results[:limit]

    # List and Filter Methods
    def list(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        **filters,
    ) -> List[Dict[str, Any]]:
        """
        List memories.

        Args:
            conversation_id: Filter by conversation ID
            user_id: Filter by user ID
            limit: Maximum items (default: 100)
            offset: Number of items to skip (default: 0)
            **filters: Additional filters

        Returns:
            List of memory dicts

        Example:
            >>> memories = memory.list(conversation_id="conv1", limit=50)
        """
        all_filters = {**filters}
        if conversation_id:
            all_filters["conversation_id"] = conversation_id
        if user_id:
            all_filters["user_id"] = user_id

        results = []
        for memory_id in list(self.memory_items.keys())[offset : offset + limit]:
            memory_item = self.memory_items[memory_id]
            if not all_filters or self._matches_filters(memory_item, all_filters):
                # Also check user_id and conversation_id in metadata
                if user_id and memory_item.metadata.get("user_id") != user_id:
                    continue
                if (
                    conversation_id
                    and memory_item.metadata.get("conversation_id") != conversation_id
                ):
                    continue

                mem_dict = self.get_memory(memory_id)
                if mem_dict:
                    results.append(mem_dict)

        return results

    def get_by_conversation(
        self, conversation_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get conversation memories.

        Args:
            conversation_id: Conversation ID
            limit: Maximum items (default: 100)

        Returns:
            List of memory dicts in conversation

        Example:
            >>> memories = memory.get_by_conversation("conv1")
        """
        return self.get_conversation_history(
            conversation_id=conversation_id, max_items=limit
        )

    def get_by_user(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get user memories.

        Args:
            user_id: User ID
            limit: Maximum items (default: 100)

        Returns:
            List of memory dicts for user

        Example:
            >>> memories = memory.get_by_user("user123")
        """
        results = []
        for memory_id, memory_item in self.memory_items.items():
            if memory_item.metadata.get("user_id") == user_id:
                mem_dict = self.get_memory(memory_id)
                if mem_dict:
                    results.append(mem_dict)
                if len(results) >= limit:
                    break
        return results

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent memories.

        Args:
            limit: Maximum items (default: 10)

        Returns:
            List of recent memory dicts

        Example:
            >>> recent = memory.get_recent(limit=20)
        """
        results = []
        sorted_items = sorted(
            self.memory_items.items(), key=lambda x: x[1].timestamp, reverse=True
        )
        for memory_id, _ in sorted_items[:limit]:
            mem_dict = self.get_memory(memory_id)
            if mem_dict:
                results.append(mem_dict)
        return results

    def get_by_date(
        self,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get by date range.

        Args:
            start_date: Start date (ISO string or datetime)
            end_date: End date (ISO string or datetime)
            limit: Maximum items (default: 100)

        Returns:
            List of memory dicts in date range

        Example:
            >>> memories = memory.get_by_date("2024-01-01", "2024-12-31")
        """
        if isinstance(start_date, str):
            from dateutil.parser import parse

            start_date = parse(start_date)
        if isinstance(end_date, str):
            from dateutil.parser import parse

            end_date = parse(end_date)

        results = []
        for memory_id, memory_item in self.memory_items.items():
            if start_date <= memory_item.timestamp <= end_date:
                mem_dict = self.get_memory(memory_id)
                if mem_dict:
                    results.append(mem_dict)
                if len(results) >= limit:
                    break
        return results

    def get_by_type(self, type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get by type.

        Args:
            type: Memory type
            limit: Maximum items (default: 100)

        Returns:
            List of memory dicts of specified type

        Example:
            >>> memories = memory.get_by_type("conversation")
        """
        results = []
        for memory_id, memory_item in self.memory_items.items():
            if memory_item.metadata.get("type") == type:
                mem_dict = self.get_memory(memory_id)
                if mem_dict:
                    results.append(mem_dict)
                if len(results) >= limit:
                    break
        return results

    # Batch Operations
    def batch_store(self, items: List[Union[str, Dict[str, Any]]]) -> List[str]:
        """
        Batch store.

        Args:
            items: List of items to store

        Returns:
            List of memory IDs

        Example:
            >>> ids = memory.batch_store(["Item 1", "Item 2"])
        """
        memory_ids = []
        for item in items:
            if isinstance(item, str):
                memory_id = self.store(item)
                memory_ids.append(memory_id)
            elif isinstance(item, dict):
                content = item.get("content", "")
                if content:
                    extra_fields = {
                        k: v
                        for k, v in item.items()
                        if k not in ["content", "metadata"]
                    }
                    memory_id = self.store(
                        content,
                        metadata=item.get("metadata"),
                        **extra_fields,
                    )
                    memory_ids.append(memory_id)
        return memory_ids

    def batch_delete(self, memory_ids: List[str]) -> int:
        """
        Batch delete.

        Args:
            memory_ids: List of memory IDs to delete

        Returns:
            Number of memories deleted

        Example:
            >>> deleted = memory.batch_delete(["mem1", "mem2"])
        """
        deleted = 0
        for memory_id in memory_ids:
            if self.delete_memory(memory_id):
                deleted += 1
        return deleted

    def batch_update(self, updates: List[Dict[str, Any]]) -> int:
        """
        Batch update.

        Args:
            updates: List of update dicts with 'memory_id' and fields

        Returns:
            Number of memories updated

        Example:
            >>> updated = memory.batch_update([{"memory_id": "mem1", "content": "New"}])
        """
        updated = 0
        for update in updates:
            memory_id = update.get("memory_id")
            update_fields = {k: v for k, v in update.items() if k != "memory_id"}
            if memory_id and self.update(memory_id, **update_fields):
                updated += 1
        return updated

    # Export/Import
    def export(
        self, conversation_id: Optional[str] = None, format: str = "json", **filters
    ) -> Union[str, Dict[str, Any]]:
        """
        Export memories.

        Args:
            conversation_id: Export specific conversation (optional)
            format: Export format ('json' or 'dict', default: 'json')
            **filters: Additional filters

        Returns:
            Exported data

        Example:
            >>> data = memory.export(conversation_id="conv1")
        """
        all_filters = {**filters}
        if conversation_id:
            all_filters["conversation_id"] = conversation_id

        memories = []
        for memory_id, memory_item in self.memory_items.items():
            if not all_filters or self._matches_filters(memory_item, all_filters):
                mem_dict = self.get_memory(memory_id)
                if mem_dict:
                    memories.append(mem_dict)

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "count": len(memories),
            "memories": memories,
        }

        if format == "json":
            import json

            return json.dumps(export_data, indent=2, default=str)
        return export_data

    def import_data(
        self, data: Union[str, Dict[str, Any]], format: str = "json"
    ) -> int:
        """
        Import memories.

        Args:
            data: Data to import
            format: Data format ('json' or 'dict', default: 'json')

        Returns:
            Number of memories imported

        Example:
            >>> imported = memory.import_data(json_string)
        """
        if format == "json":
            import json

            if isinstance(data, str):
                data = json.loads(data)

        if not isinstance(data, dict):
            raise ValueError("Invalid data format")

        memories = data.get("memories", [])
        if not memories:
            return 0

        imported = 0
        for memory in memories:
            try:
                memory_id = self.store(
                    memory.get("content", ""),
                    metadata=memory.get("metadata", {}),
                )
                if memory_id:
                    imported += 1
            except Exception as e:
                self.logger.warning(f"Failed to import memory: {e}")

        return imported

    # Statistics
    def stats(self, **filters) -> Dict[str, Any]:
        """
        Get statistics (enhance existing).

        Args:
            **filters: Optional filters

        Returns:
            Statistics dict

        Example:
            >>> stats = memory.stats()
            >>> conv_stats = memory.stats(conversation_id="conv1")
        """
        base_stats = self.get_statistics()
        if filters:
            base_stats["filtered_count"] = self.count(**filters)
        return base_stats

    def count_by_type(self) -> Dict[str, int]:
        """
        Count by type.

        Returns:
            Dict mapping type to count

        Example:
            >>> counts = memory.count_by_type()
        """
        counts = {}
        for memory_item in self.memory_items.values():
            mem_type = memory_item.metadata.get("type", "unknown")
            counts[mem_type] = counts.get(mem_type, 0) + 1
        return counts

    def count_by_user(self) -> Dict[str, int]:
        """
        Count by user.

        Returns:
            Dict mapping user_id to count

        Example:
            >>> counts = memory.count_by_user()
        """
        counts = {}
        for memory_item in self.memory_items.values():
            user_id = memory_item.metadata.get("user_id", "unknown")
            counts[user_id] = counts.get(user_id, 0) + 1
        return counts

    def count_by_conversation(self) -> Dict[str, int]:
        """
        Count by conversation.

        Returns:
            Dict mapping conversation_id to count

        Example:
            >>> counts = memory.count_by_conversation()
        """
        counts = {}
        for memory_item in self.memory_items.values():
            conv_id = memory_item.metadata.get("conversation_id", "unknown")
            counts[conv_id] = counts.get(conv_id, 0) + 1
        return counts
