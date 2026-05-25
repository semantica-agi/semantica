"""
RDF Triplet Extraction Module

This module provides comprehensive RDF triplet extraction capabilities, enabling
conversion of entities and relations into RDF triplets using multiple extraction
methods, with validation and serialization support.

Supported Methods:
    - "pattern": Pattern-based triplet extraction from relations (default)
    - "rules": Rule-based triplet extraction using linguistic rules
    - "huggingface": Custom HuggingFace triplet extraction models
    - "llm": LLM-based triplet extraction using various providers

Algorithms Used:
    - Pattern Matching: Regex-based subject-predicate-object extraction
    - Rule-based Extraction: Linguistic rule application for triplet formation
    - Sequence-to-Sequence Models: Transformer-based seq2seq for triplet generation
    - Large Language Models: GPT, Claude, Gemini for structured triplet extraction
    - RDF Serialization: Graph serialization algorithms (Turtle, N-Triples, JSON-LD)
    - URI Normalization: String normalization and URI formatting algorithms
    - Weighted Confidence Scoring:
        * Formula: Score = (0.5 * Method_Confidence) + (0.5 * Type_Similarity_Score)
        * Method_Confidence: Confidence score from the extraction algorithm
        * Type_Similarity_Score: Semantic match with user-provided triplet types (Exact=1.0, Synonym=0.95, Embedding=Cosine_Sim)
    - Hybrid Similarity Matching: Exact -> Synonym -> Substring -> Semantic Embedding (Batch Optimized)
    - Last Resort Fallback: Relation-to-Triplet conversion when all other methods fail

Key Features:
    - Multiple extraction methods:
        * Pattern-based: Pattern matching for triplet extraction (default)
        * Rules-based: Rule-based triplet extraction
        * HuggingFace: Custom HuggingFace triplet models
        * LLM-based: LLM-powered triplet extraction
    - Fallback chain support: Try methods in order until one succeeds
    - Robust Fallbacks: Prevents empty results via Primary -> Relation-to-Triplet -> Pattern chain
    - RDF triplet generation from entities and relations
    - Subject-predicate-object extraction
    - Triplet validation and quality checking
    - RDF serialization (Turtle, N-Triples, JSON-LD, RDF/XML)
    - Batch triplet processing
    - URI formatting and normalization
    - Quality assessment and scoring

Main Classes:
    - TripletExtractor: Main triplet extraction coordinator with method selection
    - TripletValidator: Triplet validation engine
    - RDFSerializer: RDF serialization handler
    - TripletQualityChecker: Triplet quality assessment
    - Triplet: RDF triplet representation dataclass

Example Usage:
    >>> from semantica.semantic_extract import TripletExtractor
    >>> # Using pattern method (default)
    >>> extractor = TripletExtractor(method="pattern")
    >>> triplets = extractor.extract_triplets(text, entities, relations)
    >>> 
    >>> # Using LLM method
    >>> extractor = TripletExtractor(method="llm", provider="openai", llm_model="gpt-4")
    >>> triplets = extractor.extract_triplets(text, entities, relations)
    >>> 
    >>> # Using HuggingFace model
    >>> extractor = TripletExtractor(method="huggingface", huggingface_model="custom/triplet-model")
    >>> triplets = extractor.extract_triplets(text)
    >>> 
    >>> # Serialize to RDF
    >>> rdf_turtle = extractor.serialize_triplets(triplets, format="turtle")
    >>> validated = extractor.validate_triplets(triplets)

Author: Semantica Contributors
License: MIT
"""

from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .types import Entity, Relation, Triplet


class TripletExtractor:
    """RDF triplet extraction handler."""

    def __init__(
        self,
        method: Union[str, List[str]] = "pattern",
        triplet_types: Optional[List[str]] = None,
        include_temporal: bool = False,
        include_provenance: bool = False,
        config=None,
        **kwargs
    ):
        """
        Initialize triplet extractor.

        Args:
            method: Extraction method(s). Can be:
                - "pattern": Pattern-based extraction (default)
                - "rules": Rule-based extraction
                - "huggingface": HuggingFace model
                - "llm": LLM-based extraction
                - List of methods for fallback chain
            triplet_types: Specific triplet types/predicates to extract (e.g., ["foundedBy", "locatedIn"])
            include_temporal: Whether to include temporal information in triplets
            include_provenance: Whether to track source sentences for provenance
            config: Legacy config dict (deprecated, use kwargs)
            **kwargs: Configuration options:
                - model: Model name (for HuggingFace methods)
                - huggingface_model: HuggingFace model name
                - provider: LLM provider (for LLM method)
                - llm_model: LLM model name
                - device: Device for HuggingFace models
                - min_confidence: Minimum confidence threshold
                - validate: Enable validation (default: True)
        """
        self.logger = get_logger("triplet_extractor")
        self.config = config or {}
        self.config.update(kwargs)
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        if method is not None:
            self.config["ner_method"] = method
            self.config["relation_method"] = method

        self._ner_extractor = None
        self._relation_extractor = None

        # Store parameters
        self.triplet_types = triplet_types
        self.include_temporal = include_temporal
        self.include_provenance = include_provenance

        # Method configuration
        self.method = method if isinstance(method, list) else [method]
        self.min_confidence = self.config.get("min_confidence", 0.5)
        self._should_validate = self.config.get("validate", True)

        self.triplet_validator = TripletValidator(**self.config.get("validator", {}))
        self.rdf_serializer = RDFSerializer(**self.config.get("serializer", {}))
        self.quality_checker = TripletQualityChecker(**self.config.get("quality", {}))

        self.supported_formats = ["turtle", "ntriples", "jsonld", "xml"]

    def extract(
        self,
        text: Union[str, List[str], List[Dict[str, Any]]],
        entities: Optional[Union[List[Entity], List[List[Entity]]]] = None,
        relations: Optional[Union[List[Relation], List[List[Relation]]]] = None,
        pipeline_id: Optional[str] = None,
        **kwargs
    ) -> Union[List[Triplet], List[List[Triplet]]]:
        """
        Extract triplets from text or list of documents.
        Handles batch processing with progress tracking.

        Args:
            text: Input text or list of documents
            entities: Optional pre-extracted entities (single list or list of lists)
            relations: Optional pre-extracted relations (single list or list of lists)
            pipeline_id: Optional pipeline ID for progress tracking
            **kwargs: Extraction options

        Returns:
            Union[List[Triplet], List[List[Triplet]]]: Extracted triplets
        """
        if isinstance(text, list):
            # Handle batch extraction with progress tracking
            tracking_id = self.progress_tracker.start_tracking(
                module="semantic_extract",
                submodule="TripletExtractor",
                message=f"Batch extracting triplets from {len(text)} documents",
                pipeline_id=pipeline_id,
            )

            try:
                results = [None] * len(text)
                total_items = len(text)
                total_triplets_count = 0
                processed_count = 0
                
                # Determine update interval
                if total_items <= 10:
                    update_interval = 1
                else:
                    update_interval = max(1, min(10, total_items // 100))
                
                # Initial progress update
                self.progress_tracker.update_progress(
                    tracking_id,
                    processed=0,
                    total=total_items,
                    message=f"Starting batch extraction... 0/{total_items}"
                )

                from .config import resolve_max_workers
                max_workers = resolve_max_workers(
                    explicit=kwargs.get("max_workers"),
                    local_config=self.config,
                    methods=self.method,
                )

                def process_item(idx, item):
                    try:
                        # Prepare arguments for single item
                        doc_text = item["content"] if isinstance(item, dict) and "content" in item else str(item)
                        
                        doc_entities = None
                        if entities and isinstance(entities, list) and idx < len(entities):
                            doc_entities = entities[idx]
                        
                        doc_relations = None
                        if relations and isinstance(relations, list) and idx < len(relations):
                            doc_relations = relations[idx]

                        # Extract
                        current_triplets = self.extract_triplets(
                            doc_text, 
                            entities=doc_entities, 
                            relations=doc_relations, 
                            **kwargs
                        )

                        # Add provenance metadata
                        for triplet in current_triplets:
                            if triplet.metadata is None:
                                triplet.metadata = {}
                            triplet.metadata["batch_index"] = idx
                            if isinstance(item, dict) and "id" in item:
                                triplet.metadata["document_id"] = item["id"]
                        
                        return idx, current_triplets
                    except Exception as e:
                        self.logger.warning(f"Failed to process item {idx}: {e}")
                        return idx, []

                if max_workers > 1:
                    import concurrent.futures
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submit tasks
                        future_to_idx = {
                            executor.submit(process_item, idx, item): idx 
                            for idx, item in enumerate(text)
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_idx):
                            idx, triplets = future.result()
                            results[idx] = triplets
                            total_triplets_count += len(triplets)
                            processed_count += 1
                            
                            if processed_count % update_interval == 0 or processed_count == total_items:
                                remaining = total_items - processed_count
                                self.progress_tracker.update_progress(
                                    tracking_id,
                                    processed=processed_count,
                                    total=total_items,
                                    message=f"Processing... {processed_count}/{total_items} (remaining: {remaining}) - Extracted {total_triplets_count} triplets"
                                )
                else:
                    # Sequential processing
                    for idx, item in enumerate(text):
                        _, triplets = process_item(idx, item)
                        results[idx] = triplets
                        total_triplets_count += len(triplets)
                        processed_count += 1
                        
                        if processed_count % update_interval == 0 or processed_count == total_items:
                            remaining = total_items - processed_count
                            self.progress_tracker.update_progress(
                                tracking_id,
                                processed=processed_count,
                                total=total_items,
                                message=f"Processing... {processed_count}/{total_items} (remaining: {remaining}) - Extracted {total_triplets_count} triplets"
                            )

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Batch extraction completed. Processed {len(results)} documents, extracted {total_triplets_count} triplets.",
                )
                return results

            except Exception as e:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message=str(e)
                )
                raise

        else:
            # Single item
            return self.extract_triplets(text, entities=entities, relations=relations, **kwargs)

    def extract_triplets(
        self,
        text: Union[str, List[str], List[Dict[str, Any]]],
        entities: Optional[Union[List[Entity], List[List[Entity]]]] = None,
        relations: Optional[Union[List[Relation], List[List[Relation]]]] = None,
        pipeline_id: Optional[str] = None,
        **options,
    ) -> Union[List[Triplet], List[List[Triplet]]]:
        """
        Extract RDF triplets from text.

        Args:
            text: Input text
            entities: Pre-extracted entities (optional)
            relations: Pre-extracted relations (optional)
            pipeline_id: Optional pipeline ID for progress tracking (batch mode)
            **options: Extraction options

        Returns:
            list: List of extracted triplets
        """
        if isinstance(text, list):
            entities_batch = entities
            if entities is not None and isinstance(entities, list) and (not entities or all(isinstance(e, Entity) for e in entities)):
                entities_batch = [entities for _ in range(len(text))] if entities else [[] for _ in range(len(text))]

            relations_batch = relations
            if relations is not None and isinstance(relations, list) and (not relations or all(isinstance(r, Relation) for r in relations)):
                relations_batch = [relations for _ in range(len(text))] if relations else [[] for _ in range(len(text))]

            return self.extract(
                text,
                entities=entities_batch,
                relations=relations_batch,
                pipeline_id=pipeline_id,
                **options,
            )

        from .methods import get_triplet_method

        tracking_id = self.progress_tracker.start_tracking(
            module="semantic_extract",
            submodule="TripletExtractor",
            message="Extracting RDF triplets from text",
        )

        try:
            from .ner_extractor import NERExtractor
            from .relation_extractor import RelationExtractor

            # Use method-based extraction
            methods = options.get("method", self.method)
            if isinstance(methods, str):
                methods = [methods]

            # Determine if we need to extract entities/relations based on method
            # HuggingFace (Seq2Seq) does not need pre-extracted entities/relations
            needs_entities_relations = any(m not in ["huggingface"] for m in methods)

            # Extract entities if not provided
            if entities is None and needs_entities_relations:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Extracting entities..."
                )
                if self._ner_extractor is None:
                    ner_config = self.config.get("ner", {})
                    if "ner_method" in self.config:
                        ner_config = {**ner_config, "method": self.config["ner_method"]}
                    
                    # Filter out 'model' and 'huggingface_model' from shared config
                    # to prevent passing triplet model to NER extractor
                    shared_config = {
                        k: v
                        for k, v in self.config.items()
                        if k not in ["ner", "relation", "validator", "serializer", "quality", "model", "huggingface_model"]
                    }

                    self._ner_extractor = NERExtractor(
                        **ner_config,
                        **shared_config,
                    )
                entities = self._ner_extractor.extract_entities(text)

            # Extract relations if not provided
            if relations is None and needs_entities_relations:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Extracting relations..."
                )
                if self._relation_extractor is None:
                    rel_config = self.config.get("relation", {})
                    if "relation_method" in self.config:
                        rel_config = {**rel_config, "method": self.config["relation_method"]}
                    
                    # Filter out 'model' and 'huggingface_model' from shared config
                    shared_config = {
                        k: v
                        for k, v in self.config.items()
                        if k not in ["ner", "relation", "validator", "serializer", "quality", "model", "huggingface_model"]
                    }

                    self._relation_extractor = RelationExtractor(
                        **rel_config,
                        **shared_config,
                    )
                relations = self._relation_extractor.extract_relations(text, entities)

            triplet_types = options.get("triplet_types", self.triplet_types)
            
            # Merge config with options
            all_options = {**self.config, **options}

            # Try each method in order (fallback chain)
            all_triplets = []
            total_methods = len(methods)
            if total_methods <= 10:
                method_update_interval = 1  # Update every method for small datasets
            else:
                method_update_interval = max(1, min(5, total_methods // 20))
            
            # Initial progress update for methods
            remaining_methods = total_methods
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_methods,
                message=f"Starting triplet extraction... 0/{total_methods} methods (remaining: {remaining_methods})"
            )
            
            for method_idx, method_name in enumerate(methods, 1):
                try:
                    remaining_methods = total_methods - method_idx
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=method_idx,
                        total=total_methods,
                        message=f"Extracting triplets using {method_name}... ({method_idx}/{total_methods}, remaining: {remaining_methods} methods)"
                    )
                    method_func = get_triplet_method(method_name)

                    # Prepare method-specific options
                    method_options = all_options.copy()
                    
                    # Pass triplet_types to all methods
                    if triplet_types:
                        method_options["triplet_types"] = triplet_types

                    if method_name == "huggingface":
                        # Prioritize runtime options over config/defaults
                        method_options["model"] = (
                            options.get("huggingface_model") 
                            or options.get("model")
                            or self.config.get("huggingface_model") 
                            or self.config.get("model")
                        )
                        method_options["device"] = all_options.get("device")
                    elif method_name == "llm":
                        method_options["provider"] = all_options.get(
                            "provider", "openai"
                        )
                        method_options["model"] = all_options.get(
                            "llm_model", all_options.get("model")
                        )
                        # Ensure api_key is populated: check explicitly provided or fallback to env
                        current_key = method_options.get("api_key")
                        if not current_key:
                            # Not found or empty/None, try environment
                            import os
                            provider_name = method_options.get("provider", "openai")
                            env_key = f"{provider_name.upper()}_API_KEY"
                            api_key = os.getenv(env_key)
                            if api_key:
                                method_options["api_key"] = api_key

                    # Print progress if verbose mode is enabled (only for LLM method to avoid spam)
                    verbose_mode = options.get("verbose", False) or self.config.get("verbose", False)
                    if verbose_mode and method_name == "llm":
                        import sys
                        print(f"    [TripletExtractor] Processing with {method_name}...", flush=True, file=sys.stdout)

                    triplets = method_func(
                        text,
                        entities=entities,
                        relations=relations,
                        **method_options,
                    )

                    # Print result count if verbose (only for LLM method)
                    if verbose_mode and method_name == "llm" and len(triplets) > 0:
                        import sys
                        print(f"    [TripletExtractor] Extracted {len(triplets)} triplets", flush=True, file=sys.stdout)

                    # Apply weighted scoring if triplet_types are provided
                    if triplet_types:
                        try:
                            from .methods import calculate_weighted_confidence
                            for t in triplets:
                                t.confidence = calculate_weighted_confidence(
                                    item_type=t.predicate,
                                    original_confidence=t.confidence,
                                    valid_types=triplet_types,
                                    item_text=t.predicate # For triplets, predicate is the key text
                                )
                        except ImportError:
                            pass

                    # Filter by confidence
                    min_conf = options.get("min_confidence", self.min_confidence)
                    filtered = [t for t in triplets if t.confidence >= min_conf]

                    if filtered:
                        all_triplets.append((method_name, filtered))

                        # If not using ensemble, return first successful result
                        if len(methods) == 1:
                            result = filtered
                            if options.get("validate", self._should_validate):
                                result = self.triplet_validator.validate_triplets(result)
                            self.progress_tracker.stop_tracking(
                                tracking_id,
                                status="completed",
                                message=f"Extracted {len(result)} triplets using {method_name}",
                            )
                            return result

                except Exception as e:
                    self.logger.warning(f"Method {method_name} failed: {e}")
                    verbose_mode = options.get("verbose", False) or self.config.get("verbose", False)
                    if verbose_mode:
                        import sys
                        print(f"    [TripletExtractor] ERROR: Method {method_name} failed: {e}", flush=True, file=sys.stderr)
                        import traceback
                        traceback.print_exc(file=sys.stderr)
                    continue

            # Use first successful method or fallback to relation conversion
            if all_triplets:
                triplets = all_triplets[0][1]
            else:
                # Fallback: Convert relations to triplets
                if relations:
                    self.progress_tracker.update_tracking(
                        tracking_id,
                        message=f"Converting {len(relations)} relations to triplets...",
                    )
                    triplets = []
                    for relation in relations:
                        triplet = Triplet(
                            subject=self._format_uri(relation.subject.text),
                            predicate=self._format_uri(relation.predicate),
                            object=self._format_uri(relation.object.text),
                            confidence=relation.confidence,
                            metadata={"context": relation.context, **relation.metadata},
                        )
                        triplets.append(triplet)
                else:
                    # Last resort: Try rule-based extraction if no relations exist
                    self.progress_tracker.update_tracking(
                        tracking_id,
                        message="No relations found. Trying rule-based triplet extraction...",
                    )
                    method_func = get_triplet_method("rules")
                    triplets = method_func(text, entities=entities, relations=[], **all_options)

            # Validate triplets
            if options.get("validate", self._should_validate):
                self.progress_tracker.update_tracking(
                    tracking_id, message="Validating triplets..."
                )
                triplets = self.triplet_validator.validate_triplets(triplets)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Extracted {len(triplets)} triplets",
            )
            return triplets

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _format_uri(self, value: str) -> str:
        """Format value as URI."""
        # Simple URI formatting
        if value.startswith("http://") or value.startswith("https://"):
            return value

        # Format as local URI
        formatted = quote(value.replace(" ", "_"), safe="")
        return f"http://example.org/{formatted}"

    def validate_triplets(self, triplets: List[Triplet], **criteria) -> List[Triplet]:
        """
        Validate triplet quality and consistency using the internal validator.

        Args:
            triplets: List of triplets to validate
            **criteria: Validation criteria (e.g., min_confidence=0.5)

        Returns:
            List[Triplet]: List of validated triplets that meet the criteria
            
        Example:
            >>> extractor = TripletExtractor()
            >>> validated = extractor.validate_triplets(triplets, min_confidence=0.8)
        """
        return self.triplet_validator.validate_triplets(triplets, **criteria)

    def serialize_triplets(
        self, triplets: List[Triplet], format: str = "turtle", **options
    ) -> str:
        """
        Serialize triplets to RDF format.

        Args:
            triplets: List of triplets
            format: RDF format (turtle, ntriples, jsonld, xml)
            **options: Serialization options

        Returns:
            str: Serialized RDF
        """
        return self.rdf_serializer.serialize_to_rdf(triplets, format, **options)

    def process_batch(self, texts: List[str], **options) -> List[List[Triplet]]:
        """
        Process multiple texts for triplet extraction.

        Args:
            texts: List of input texts
            **options: Processing options

        Returns:
            list: List of triplet lists for each text
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="semantic_extract",
            submodule="TripletExtractor",
            message=f"Batch extracting triplets from {len(texts)} documents",
        )
        
        results = []
        total_triplets_count = 0
        total_items = len(texts)
        
        try:
            # Determine update interval
            if total_items <= 10:
                update_interval = 1
            else:
                update_interval = max(1, min(10, total_items // 100))
                
            for idx, text in enumerate(texts, 1):
                # Extract triplets
                triplets = self.extract_triplets(text, **options)
                
                # Add provenance metadata
                for triplet in triplets:
                    if triplet.metadata is None:
                        triplet.metadata = {}
                    triplet.metadata["batch_index"] = idx - 1

                results.append(triplets)
                total_triplets_count += len(triplets)
                
                # Update progress
                should_update = (
                    idx % update_interval == 0 or 
                    idx == total_items or 
                    idx == 1 or
                    total_items <= 10
                )
                
                if should_update:
                    remaining = total_items - idx
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=idx,
                        total=total_items,
                        message=f"Processing documents... {idx}/{total_items} (remaining: {remaining}) - Extracted {total_triplets_count} triplets so far"
                    )
            
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Batch extraction completed. Processed {len(results)} documents, extracted {total_triplets_count} triplets.",
            )
            return results
            
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise


class TripletValidator:
    """Triplet validation engine."""

    def __init__(self, **config):
        """Initialize triplet validator."""
        self.logger = get_logger("triplet_validator")
        self.config = config

    def validate_triplet(self, triplet: Triplet, **criteria) -> bool:
        """
        Validate individual triplet.

        Args:
            triplet: Triplet to validate
            **criteria: Validation criteria

        Returns:
            bool: True if valid
        """
        # Check structure
        if not triplet.subject or not triplet.predicate or not triplet.object:
            return False

        # Check confidence
        min_confidence = criteria.get("min_confidence", 0.5)
        if triplet.confidence < min_confidence:
            return False

        return True

    def validate_triplets(self, triplets: List[Triplet], **criteria) -> List[Triplet]:
        """
        Validate list of triplets.

        Args:
            triplets: List of triplets
            **criteria: Validation criteria

        Returns:
            list: Valid triplets
        """
        return [t for t in triplets if self.validate_triplet(t, **criteria)]


class RDFSerializer:
    """RDF serialization handler."""

    def __init__(self, **config):
        """Initialize RDF serializer."""
        self.logger = get_logger("rdf_serializer")
        self.config = config

    def serialize_to_rdf(
        self, triplets: List[Triplet], format: str = "turtle", **options
    ) -> str:
        """
        Serialize triplets to RDF format.

        Args:
            triplets: List of triplets
            format: RDF format
            **options: Serialization options

        Returns:
            str: Serialized RDF
        """
        if format == "turtle":
            return self._serialize_turtle(triplets, **options)
        elif format == "ntriples":
            return self._serialize_ntriples(triplets, **options)
        elif format == "jsonld":
            return self._serialize_jsonld(triplets, **options)
        elif format == "xml":
            return self._serialize_xml(triplets, **options)
        else:
            raise ValidationError(f"Unsupported RDF format: {format}")

    def _serialize_turtle(self, triplets: List[Triplet], **options) -> str:
        """Serialize to Turtle format."""
        lines = ["@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> ."]

        for triplet in triplets:
            line = f"{triplet.subject} <{triplet.predicate}> {triplet.object} ."
            lines.append(line)

        return "\n".join(lines)

    def _serialize_ntriples(self, triplets: List[Triplet], **options) -> str:
        """Serialize to N-Triples format."""
        lines = []
        for triplet in triplets:
            line = f"<{triplet.subject}> <{triplet.predicate}> <{triplet.object}> ."
            lines.append(line)
        return "\n".join(lines)

    def _serialize_jsonld(self, triplets: List[Triplet], **options) -> str:
        """Serialize to JSON-LD format."""
        import json

        graph = []
        for triplet in triplets:
            graph.append({"@id": triplet.subject, triplet.predicate: triplet.object})

        return json.dumps({"@graph": graph}, indent=2)

    def _serialize_xml(self, triplets: List[Triplet], **options) -> str:
        """Serialize to RDF/XML format."""
        lines = [
            '<?xml version="1.0"?>',
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        ]

        for triplet in triplets:
            lines.append(f'  <rdf:Description rdf:about="{triplet.subject}">')
            lines.append(
                f"    <{triplet.predicate}>{triplet.object}</{triplet.predicate}>"
            )
            lines.append("  </rdf:Description>")

        lines.append("</rdf:RDF>")
        return "\n".join(lines)


class TripletQualityChecker:
    """Triplet quality assessment engine."""

    def __init__(self, **config):
        """Initialize triplet quality checker."""
        self.logger = get_logger("triplet_quality_checker")
        self.config = config

    def assess_triplet_quality(self, triplet: Triplet, **metrics) -> Dict[str, Any]:
        """
        Assess quality of individual triplet.

        Args:
            triplet: Triplet to assess
            **metrics: Quality metrics

        Returns:
            dict: Quality assessment
        """
        return {
            "confidence": triplet.confidence,
            "completeness": 1.0
            if triplet.subject and triplet.predicate and triplet.object
            else 0.0,
            "quality_score": triplet.confidence,
        }

    def calculate_quality_scores(
        self, triplets: List[Triplet], **options
    ) -> Dict[str, Any]:
        """
        Calculate quality scores for triplets.

        Args:
            triplets: List of triplets
            **options: Quality options

        Returns:
            dict: Quality scores
        """
        if not triplets:
            return {}

        scores = [self.assess_triplet_quality(t)["quality_score"] for t in triplets]

        return {
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "high_quality": len([s for s in scores if s >= 0.8]),
            "medium_quality": len([s for s in scores if 0.5 <= s < 0.8]),
            "low_quality": len([s for s in scores if s < 0.5]),
        }
