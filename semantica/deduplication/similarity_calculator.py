"""
Similarity Calculator Module

This module provides comprehensive similarity calculation capabilities for the
Semantica framework, computing semantic similarity between entities using multiple
metrics including string similarity, property similarity, relationship similarity,
and embedding similarity.

Algorithms Used:
    - Blocking Strategy: Prefix-based entity grouping to reduce O(n²) comparisons
    - Pre-processing: Vectorized preparation of lowercase names and relationship sets
    - Short-circuiting: Early exit for dissimilar pairs based on name similarity
    - Levenshtein Distance: Dynamic programming algorithm for edit distance calculation
    - Jaro Similarity: Character-based similarity with match window algorithm
    - Jaro-Winkler Similarity: Jaro with prefix bonus (up to 4 characters, 0.1 weight)
    - Cosine Similarity: Vector dot product divided by magnitudes for embeddings
    - Jaccard Similarity: Intersection over union for relationship sets
    - Property Matching: Weighted comparison of property values with type-aware matching
    - Multi-factor Aggregation: Weighted sum of similarity components with normalization

Key Features:
    - Blocking strategy and short-circuiting for high-performance large-scale processing
    - Multi-factor similarity calculation (string, property, relationship, embedding)
    - Multiple string similarity algorithms (Levenshtein, Jaro-Winkler, cosine)
    - Weighted aggregation of similarity components with automatic normalization
    - Batch similarity calculation for efficiency (O(n²) optimized)
    - Configurable similarity thresholds and component weights
    - Support for exact matching, fuzzy matching, and semantic matching

Main Classes:
    - SimilarityCalculator: Main similarity calculation engine
    - SimilarityResult: Similarity calculation result with component scores

Example Usage:
    >>> from semantica.deduplication import SimilarityCalculator
    >>> calculator = SimilarityCalculator(
    ...     string_weight=0.4,
    ...     property_weight=0.3,
    ...     embedding_weight=0.3
    ... )
    >>> similarity = calculator.calculate_similarity(entity1, entity2)
    >>> batch_results = calculator.batch_calculate_similarity(entities, threshold=0.7)
    >>> 
    >>> # String similarity methods
    >>> lev_score = calculator.calculate_string_similarity("Apple", "Apple Inc.", method="levenshtein")
    >>> jaro_score = calculator.calculate_string_similarity("Apple", "Apple Inc.", method="jaro_winkler")

Author: Semantica Contributors
License: MIT
"""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


@dataclass
class SimilarityResult:
    """Similarity calculation result."""

    score: float
    method: str
    components: Dict[str, float] = None
    metadata: Dict[str, Any] = None


class SimilarityCalculator:
    """
    Similarity calculation engine for entity comparison.

    This class provides comprehensive similarity calculation using multiple factors:
    string similarity, property similarity, relationship similarity, and embedding
    similarity. Results are aggregated using configurable weights.

    Similarity Components:
        - String similarity: Name/identifier comparison using various algorithms
        - Property similarity: Comparison of entity properties
        - Relationship similarity: Comparison of entity relationships
        - Embedding similarity: Semantic similarity using vector embeddings

    Example Usage:
        >>> calculator = SimilarityCalculator(
        ...     string_weight=0.4,
        ...     property_weight=0.3,
        ...     embedding_weight=0.3
        ... )
        >>> result = calculator.calculate_similarity(entity1, entity2)
        >>> print(f"Similarity: {result.score:.2f}")
    """

    def __init__(
        self,
        embedding_weight: float = 0.0,
        string_weight: float = 0.6,
        property_weight: float = 0.2,
        relationship_weight: float = 0.2,
        similarity_threshold: float = 0.7,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize similarity calculator.

        Sets up the calculator with configurable weights for different similarity
        components. Weights are normalized automatically if they don't sum to 1.0.

        Args:
            embedding_weight: Weight for embedding similarity (default: 0.4)
            string_weight: Weight for string similarity (default: 0.3)
            property_weight: Weight for property similarity (default: 0.2)
            relationship_weight: Weight for relationship similarity (default: 0.1)
            similarity_threshold: Default similarity threshold for filtering (default: 0.7)
            config: Configuration dictionary (merged with kwargs)
            **kwargs: Additional configuration options
        """
        self.logger = get_logger("similarity_calculator")

        # Merge configuration
        self.config = config or {}
        self.config.update(kwargs)

        # Component weights (used for weighted aggregation)
        self.embedding_weight = embedding_weight
        self.string_weight = string_weight
        self.property_weight = property_weight
        self.relationship_weight = relationship_weight
        self.similarity_threshold = similarity_threshold
        
        # Prefilter
        self.prefilter_enabled = self.config.get("prefilter_enabled", False)
        self.score_breakdown_enabled = self.config.get("score_breakdown_enabled", False)
        self.prefilter_thresholds = self.config.get("prefilter_thresholds", {
            "min_length_ratio": 0.3,
            "min_token_overlap_ratio": 0.0,
            "required_shared_token": False
        })


        # Validate weights sum to approximately 1.0
        total_weight = (
            self.embedding_weight
            + self.string_weight
            + self.property_weight
            + self.relationship_weight
        )
        if abs(total_weight - 1.0) > 0.01:
            self.logger.debug(
                f"Weights sum to {total_weight:.2f}, will be normalized during calculation"
            )

        # Initialize progress tracker and ensure it's enabled
        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Similarity calculator initialized")
    
    def _prefilter_pair(
        self, entity1: Dict[str, Any], entity2: Dict[str, Any], thresholds: Dict[str, float]
    ) -> Tuple[bool, str]:
        """
        Fast prefilter stage to drop obvious non-matches before full semantic scoring.
        Returns a tuple: (passed_prefilter:bool, rejected_reason:str).
        """
        
        # Type mismatch gate
        
        type1 = entity1.get("type")
        type2 = entity2.get("type")
        if type1 and type2 and type1 != type2:
            return False, "type_mismatch"
        
        # Prepare names for string/token gates
        
        name1 = entity1.get("_lower_name") or str(entity1.get("name") or entity1.get("text") or "").lower().strip()
        name2 = entity2.get("_lower_name") or str(entity2.get("name") or entity2.get("text") or "").lower().strip()
        
        # Pass on missing names as we are falling back to property/relationship logic
        if not name1 or not name2:
            return True, ""
        
        # Name length-ratio gate
        
        len1, len2  = len(name1), len(name2)
        
        if len1 > 0 or len2 > 0:
            length_ratio = min(len1, len2) / max(len1, len2)
            min_length_ratio = thresholds.get("min_length_ratio", 0.3)
            
            if length_ratio < min_length_ratio:
                return False, f"length_ratio_below_{min_length_ratio}"

        # Token overlap gate
        
        if thresholds.get("require_shared_token", False) or thresholds.get("min_token_overlap_ratio", 0.0) > 0:
            tokens1 = set(t for t in name1.replace("_", " ").replace("-", " ").split() if len(t) > 2)
            tokens2 = set(t for t in name2.replace("_", " ").replace("-", " ").split() if len(t) > 2)
            
            if tokens1 and tokens2:
                overlap = len(tokens1.intersection(tokens2))
                
                min_overlap_ratio = thresholds.get("min_token_overlap_ratio", 0.0)
                
                if min_overlap_ratio > 0:
                    max_possible_overlap = min(len(tokens1), len(tokens2))
                    overlap_ratio = overlap / max_possible_overlap
                    if overlap_ratio < min_overlap_ratio:
                        return False, f"token_overlap_below_{min_overlap_ratio}"

                elif thresholds.get("require_shared_token", False) and overlap == 0:
                    return False, "no_shared_tokens"
        
        return True, ""
        

    def calculate_similarity(
        self, entity1: Dict[str, Any], entity2: Dict[str, Any], track: bool = True, **options
    ) -> SimilarityResult:
        """
        Calculate overall similarity between two entities.

        This method computes a comprehensive similarity score by combining multiple
        similarity factors: string similarity, property similarity, relationship
        similarity, and embedding similarity (if available). Results are aggregated
        using configurable weights.
        
        Includes an optional Two-Stage prefilter to fast-fail obvious non-matches.

        Args:
            entity1: First entity dictionary
            entity2: Second entity dictionary
            track: Whether to track progress for this individual calculation (default: True)
            **options: Additional calculation options

        Returns:
            SimilarityResult object
        """
        tracking_id = None
        if track:
            tracking_id = self.progress_tracker.start_tracking(
                file=None,
                module="deduplication",
                submodule="SimilarityCalculator",
                message="Calculating similarity between entities",
            )

        try:
            # Fast Prefilter
            merged_options = {**self.config, **options}
            prefilter_enabled = merged_options.get("prefilter_enabled", self.prefilter_enabled)
            
            if prefilter_enabled:
                thresholds = merged_options.get("prefilter_thresholds", self.prefilter_thresholds)
                passed, reason = self._prefilter_pair(entity1, entity2, thresholds)
                
                if not passed:
                    if tracking_id:
                        self.progress_tracker.stop_tracking(
                            tracking_id, status="completed", message=f"Rejected by prefilter: {reason}"
                        )
                    return SimilarityResult(
                        score=0.0,
                        method="prefiltered",
                        metadata={"rejection_reason": reason}
                    )

            components = {}

            # String similarity
            if tracking_id:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Calculating string similarity..."
                )
            
            name1 = entity1.get("_lower_name")
            if name1 is None:
                name1 = entity1.get("name") or entity1.get("text") or ""
            
            name2 = entity2.get("_lower_name")
            if name2 is None:
                name2 = entity2.get("name") or entity2.get("text") or ""
                
            string_score = self.calculate_string_similarity(name1, name2)
            components["string"] = string_score

            # Short-circuit if string similarity is too low
            if self.string_weight > 0.5 and string_score < 0.3 and not ("embedding" in entity1 and "embedding" in entity2):
                overall_score = string_score * self.string_weight
                if overall_score < (merged_options.get("threshold") or self.similarity_threshold) * 0.5:
                    return SimilarityResult(score=overall_score, method="short_circuit", components=components)

            # Property similarity
            if tracking_id:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Calculating property similarity..."
                )
            property_score = self.calculate_property_similarity(entity1, entity2)
            components["property"] = property_score

            # Relationship similarity
            if tracking_id:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Calculating relationship similarity..."
                )
            relationship_score = self.calculate_relationship_similarity(entity1, entity2)
            components["relationship"] = relationship_score

            # Embedding similarity
            embedding_score = 0.0
            if "embedding" in entity1 and "embedding" in entity2:
                if tracking_id:
                    self.progress_tracker.update_tracking(
                        tracking_id, message="Calculating embedding similarity..."
                    )
                embedding_score = self.calculate_embedding_similarity(
                    entity1["embedding"], entity2["embedding"]
                )
                components["embedding"] = embedding_score

            # Weighted aggregation
            if tracking_id:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Aggregating similarity scores..."
                )
            weights = {
                "string": self.string_weight,
                "property": self.property_weight,
                "relationship": self.relationship_weight,
                "embedding": self.embedding_weight if embedding_score > 0 else 0.0,
            }

            total_weight = sum(w for k, w in weights.items() if k in components)
            if total_weight > 0:
                weights = {k: w / total_weight for k, w in weights.items() if k in components}

            overall_score = sum(
                components.get(key, 0.0) * weight for key, weight in weights.items()
            )
            
            # Explainability metadata
            
            metadata = {"weights": weights}
            self.score_breakdown_enabled = merged_options.get("score_breakdown_enabled", self.score_breakdown_enabled)
            if self.score_breakdown_enabled:
                metadata["score_breakdown"] = components
            
            if tracking_id:
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Similarity score: {overall_score:.2f}",
                )
            return SimilarityResult(
                score=overall_score,
                method="multi_factor",
                components=components,
                metadata=metadata,
            )

        except Exception as e:
            if tracking_id:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message=str(e)
                )
            raise
    
    def calculate_string_similarity(
        self, str1: str, str2: str, method: str = "jaro_winkler"
    ) -> float:
        """
        Calculate string similarity between two strings.
        """
        if not str1 or not str2:
            return 0.0

        str1_lower = str1.lower().strip()
        str2_lower = str2.lower().strip()

        if str1_lower == str2_lower:
            return 1.0

        if method == "levenshtein":
            return self._levenshtein_similarity(str1_lower, str2_lower)
        elif method == "jaro_winkler":
            return self._jaro_winkler_similarity(str1_lower, str2_lower)
        elif method == "cosine":
            return self._cosine_similarity(str1_lower, str2_lower)
        else:
            return self._levenshtein_similarity(str1_lower, str2_lower)

    def calculate_property_similarity(
        self, entity1: Dict[str, Any], entity2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity based on entity properties.

        Args:
            entity1: First entity
            entity2: Second entity

        Returns:
            Property similarity score (0-1)
        """
        props1 = entity1.get("properties", {})
        props2 = entity2.get("properties", {})

        if not props1 and not props2:
            return 1.0

        all_keys = set(props1.keys()) | set(props2.keys())
        if not all_keys:
            return 0.0

        matches = 0
        total = 0

        for key in all_keys:
            val1 = props1.get(key)
            val2 = props2.get(key)

            if val1 is None or val2 is None:
                # Missing value in one entity is not a mismatch, but lack of evidence
                # Assign neutral score (0.5) instead of 0.0
                matches += 0.5
                total += 1
                continue

            if isinstance(val1, str) and isinstance(val2, str):
                sim = self.calculate_string_similarity(str(val1), str(val2))
                matches += sim
            elif val1 == val2:
                matches += 1.0
            else:
                matches += 0.5  # Partial match

            total += 1

        return matches / total if total > 0 else 0.0

    def calculate_relationship_similarity(
        self, entity1: Dict[str, Any], entity2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity based on relationships.

        Args:
            entity1: First entity
            entity2: Second entity

        Returns:
            Relationship similarity score (0-1)
        """
        # Use pre-calculated hashable relationships if available
        if "_hashable_rels" in entity1:
            rels1 = entity1["_hashable_rels"]
        else:
            rels1 = set(self._make_hashable(r) for r in entity1.get("relationships", []))
            
        if "_hashable_rels" in entity2:
            rels2 = entity2["_hashable_rels"]
        else:
            rels2 = set(self._make_hashable(r) for r in entity2.get("relationships", []))

        if not rels1 and not rels2:
            return 0.5

        if not rels1 or not rels2:
            return 0.0

        intersection = rels1 & rels2
        union = rels1 | rels2

        return len(intersection) / len(union) if union else 0.0

    def _make_hashable(self, item: Any) -> Any:
        """Convert item to hashable form for set operations."""
        if isinstance(item, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in item.items()))
        if isinstance(item, list):
            return tuple(self._make_hashable(x) for x in item)
        return item

    def calculate_embedding_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity (0-1)
        """
        if len(embedding1) != len(embedding2):
            return 0.0

        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = math.sqrt(sum(a * a for a in embedding1))
        magnitude2 = math.sqrt(sum(b * b for b in embedding2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        cosine_sim = dot_product / (magnitude1 * magnitude2)

        # Normalize to 0-1 range
        return (cosine_sim + 1) / 2

    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein distance-based similarity."""
        if not s1 or not s2:
            return 0.0

        if s1 == s2:
            return 1.0

        distance = self._levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))

        return 1.0 - (distance / max_len) if max_len > 0 else 0.0

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _jaro_winkler_similarity(self, s1: str, s2: str) -> float:
        """Calculate Jaro-Winkler similarity."""
        if s1 == s2:
            return 1.0

        jaro = self._jaro_similarity(s1, s2)

        # Winkler prefix bonus
        prefix_len = 0
        min_len = min(len(s1), len(s2))
        for i in range(min_len):
            if s1[i] == s2[i]:
                prefix_len += 1
            else:
                break

        prefix_bonus = min(prefix_len, 4) * 0.1
        return jaro + prefix_bonus * (1 - jaro)

    def _jaro_similarity(self, s1: str, s2: str) -> float:
        """Calculate Jaro similarity."""
        if s1 == s2:
            return 1.0

        match_window = max(len(s1), len(s2)) // 2 - 1
        if match_window < 0:
            match_window = 0

        s1_matches = [False] * len(s1)
        s2_matches = [False] * len(s2)

        matches = 0
        transpositions = 0

        # Find matches
        for i in range(len(s1)):
            start = max(0, i - match_window)
            end = min(i + match_window + 1, len(s2))

            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        # Count transpositions
        k = 0
        for i in range(len(s1)):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        jaro = (
            matches / len(s1)
            + matches / len(s2)
            + (matches - transpositions / 2) / matches
        ) / 3.0
        return jaro

    def _cosine_similarity(self, s1: str, s2: str) -> float:
        """Cosine similarity of character-pair counts."""

        def pair_counts(text):
            return Counter(text[i : i + 2] for i in range(len(text) - 1))

        counts1 = pair_counts(s1)
        counts2 = pair_counts(s2)
        if not counts1 or not counts2:
            return 0.0

        dot = sum(counts1[pair] * counts2[pair] for pair in counts1)
        mag1 = math.sqrt(sum(count * count for count in counts1.values()))
        mag2 = math.sqrt(sum(count * count for count in counts2.values()))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)
    
    def _soundex(self, word: str) -> str:
        """Soundex algorithm for phonetic blocking."""
        if not word: return ""
        word = word.upper()
        soundex_mapping = {"BFPV": "1", "CGJKQSXZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
        result = [word[0]]
        for char in word[1:]:
            for key, val in soundex_mapping.items():
                if char in key:
                    if val != result[-1]: 
                        result.append(val)
                    break
                
        result = [result[0]] + [c for c in result[1:] if c.isdigit()]
        return ("".join(result) + "000")[:4]
    
    def _build_block_indexes(
        self, processed_entities: List[Dict[str, Any]], options: Dict[str, Any]
    ) -> Dict[str, List[int]]:
        """ Builds blocks of candidate indices based on the configured strategy."""
        blocks: Dict[str, List[int]] = {}
        strategy = options.get("candidate_strategy", "legacy")
        
        for idx, entity in enumerate(processed_entities):
            name = entity.get("_lower_name", "")
            
            if not name:
                blocks.setdefault("___empty___", []).append(idx)
                continue
            
            if strategy == "legacy":
                blocks.setdefault(name[0], []).append(idx)
            
            elif strategy in ("blocking_v2", "hybrid_v2"):
                
                keys_to_add = set()
                tokens = [t for t in name.replace("_", " ").replace("-", " ").split() if len(t) > 2]
                
                if not tokens:
                    tokens = [name]
                
                for t in tokens:
                    keys_to_add.add(f"tok:{t[:4]}")
                
                blocking_keys = options.get("blocking_keys", ["prefix", "token"])
                if "type" in blocking_keys:
                    e_type = str(entity.get("type", "unknown")).lower()
                    if tokens:
                        keys_to_add.add(f"type:{e_type}:{tokens[0][:4]}")
                
                if options.get("enable_phonetic_blocking", False):
                    for t in tokens:
                        keys_to_add.add(f"pho:{self._soundex(t)}")
                        
                for k in keys_to_add:
                    blocks.setdefault(k, []).append(idx)
        
        return blocks
    
    def _generate_candidate_pairs(
        self, blocks: Dict[str, List[int]]
    ) -> Set[Tuple[int, int]]:
        """ Generates a deduplicated set of candidate pair IDs from all blocks."""
        candidate_pairs = set()
        
        for indices in blocks.values():
            n = len(indices)
            
            for i_idx in range(n):
                for j_idx in range(i_idx+1, n):
                    i = indices[i_idx]
                    j = indices[j_idx]
                    
                    candidate_pairs.add((min(i, j), max(i, j)))
        
        return candidate_pairs
        
    
    def _cap_candidate_pairs(
        self, candidate_pairs: Set[Tuple[int, int]], max_candidates: int
    ) -> Set[Tuple[int, int]]:
        """ Enforces a deterministic truncation policy per entity."""
        
        if not max_candidates or max_candidates <=0:
            return candidate_pairs
        
        connections: Dict[int, List[int]] = {}
        
        for i, j in candidate_pairs:
            connections.setdefault(i, []).append(j)
            connections.setdefault(j, []).append(i)
            
        capped_pairs = set()
        for entity_idx, neighbors in connections.items():
            kept_neighbors = sorted(neighbors)[:max_candidates]
            
            for n in kept_neighbors:
                capped_pairs.add((min(entity_idx, n), max(entity_idx, n)))
        
        return capped_pairs
            
        
                    
        

    def batch_calculate_similarity(
        self, entities: List[Dict[str, Any]], threshold: Optional[float] = None, **kwargs
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
        """
        Calculate similarity for all entity pairs in a batch using configurable candidate generation.
        """
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="deduplication",
            submodule="SimilarityCalculator",
            message=f"Calculating similarity for {len(entities)} entities",
        )

        try:
            threshold = threshold or self.similarity_threshold
            results = []

            options = {**self.config, **kwargs}

            # Legacy logic
            processed_entities = []
            for entity in entities:
                if hasattr(entity, "__dict__"):
                    processed_entity = vars(entity).copy()
                elif isinstance(entity, dict):
                    processed_entity = entity.copy()
                else:
                    processed_entity = {"_original": entity}
                
                rels = processed_entity.get("relationships")
                if rels is None and "metadata" in processed_entity:
                    rels = processed_entity.get("metadata", {}).get("relationships")
                
                if rels:
                    processed_entity["_hashable_rels"] = set(self._make_hashable(r) for r in rels)
                else:
                    processed_entity["_hashable_rels"] = set()
                
                name = processed_entity.get("name") or processed_entity.get("text") or ""
                processed_entity["_lower_name"] = name.lower().strip()
                processed_entities.append(processed_entity)

            # v2 pipeline
            
            blocks = self._build_block_indexes(processed_entities, options)
            
            candidate_pairs = self._generate_candidate_pairs(blocks)
            
            max_candidates = options.get("max_candidates_per_entity")
            if max_candidates is not None:
                candidate_pairs = self._cap_candidate_pairs(candidate_pairs, max_candidates)

            total_pairs = len(candidate_pairs)
            processed = 0
            update_interval = 1 if total_pairs <= 10 else max(1, min(100, total_pairs // 100))
            
            self.progress_tracker.update_tracking(
                tracking_id,
                status="running",
                message=f"Comparing {total_pairs} generated pairs..."
            )
            
    
            for i, j in sorted(list(candidate_pairs)):
                similarity = self.calculate_similarity(
                    processed_entities[i], processed_entities[j], track=False, threshold=threshold
                )

                if similarity.score >= threshold:
                    results.append((entities[i], entities[j], similarity.score))
                
                processed += 1
                if processed % update_interval == 0 or processed == total_pairs:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=processed,
                        total=total_pairs,
                        message=f"Comparing candidates... {processed}/{total_pairs}"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Found {len(results)} similar pairs out of {total_pairs} candidates",
            )
            return results

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise