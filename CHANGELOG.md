# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

- **Benchmark real-dataset migration — replace synthetic tests, fix oracle leakage, expand fixtures and docs** (PR #418 follow-up by @KaifAhmad1 and @ZohaibHassan16):
  - **Causal chain tests** (`test_causal_chains.py`) fully rewritten: 9 tests driven by ATOMIC (500 cause-effect pairs, CC BY 4.0) and e-CARE (200 causal QA records); multi-hop chain test chains sequential ATOMIC pairs via `LEADS_TO` bridge edges; counterfactual withheld-pair test verifies edge absence prevents retrieval; full-scale 500-node recall test (50-pair sample, seed 42).
  - **Temporal validity tests** (`test_temporal_validity.py`) fully rewritten: 7 TimeQA-driven tests (150 temporal Q&A records) covering stale injection rate, future injection rate, before/after-intent precision and recall, entity version disambiguation (expired vs current), rewriter accuracy across all 150 questions; 3 synthetic API-shape tests retained for windowless-node and future-node edge cases.
  - **Oracle leakage removed** from `test_decision_intelligence.py`: `_structured_predict_decision` no longer reads `has_conflicting_policies`, `boundary_case`, `has_overturned_precedent`, or `ground_truth_reasoning` at inference time; replaced with graph-derived conflict signal (`distinct_precedent_outcomes > 1 and top_similarity < 0.70`) and ambiguous-compliance check — lift measurement is now valid.
  - **MetaQA KB tests** added to `test_extended_multihop.py`: `TestMetaQAKnowledgeGraph` with 1-hop (recall ≥ 0.65), 2-hop (recall ≥ 0.75), 3-hop (recall ≥ 0.65), and KB node coverage (≥ 0.95) over a 100-movie graph with director, actor, and genre nodes.
  - **SES formula corrected** in `test_ses_score.py`: weighted `0.7 × ContextGraphScore + 0.3 × SemanticLayerScore` replaces the previous unweighted mean; `ses_composite` threshold raised from 0.70 → 0.72 in `thresholds.py`.
  - **`test_governance_impact.py`**: hardcoded `sample_size == 8` assertion relaxed to `>= 8` to accommodate fixture expansion.
  - **`conftest.py`**: 4 new session-scoped fixtures — `atomic_causal_dataset`, `ecare_causal_dataset`, `metaqa_dataset` (1/2/3-hop sub-dicts), `webqsp_dataset`.
  - **`decision_intelligence_dataset.json`** expanded 60 → 120 records (24 per domain) across lending (UCI German Credit: DTI, credit score), healthcare (TREC CT 2022: HbA1c, BMI, comorbidities), legal (CUAD + LEDGAR: IP, GDPR, ADEA, export control), HR (IBM Attrition: tenure, KPIs, PIP, FMLA), and ecommerce (fraud, returns, seller verification); hard slices include 20 boundary cases, 12 conflicting-policy cases, 13 overturned-precedent cases.
  - **`metric_change_pairs.json`** expanded 8 → 30 records covering all 8 change types (`expression_restatement`, `expression_and_filter`, `filter_added`, `window_tightened`, `filter_broadened`, `threshold_raised`, `filter_exclusion_added`, `time_window_added`) across 16 metrics with a 37-entry policy decision registry.
  - **`jaffle_shop_metrics.json`** expanded 8 → 16 metrics (added `gross_margin`, `repeat_purchase_rate`, `net_promoter_score`, `support_ticket_volume`, `avg_resolution_time`, `inventory_turnover`, `customer_acquisition_cost`, `active_customers`) and 15 → 35 NL queries.
  - **`benchmarks/benchmarks.md`** and **`benchmarks/benchmark_results.md`** fully rewritten: dataset inventory tables for both pillars, real-data coverage per all 25 tracks, SES_v2 formula section, threshold reference table with evidence basis, per-track results with measurement notes, and updated measurement policy noting oracle-flag reads as invalid evidence.

- **Benchmark suite follow-up — reporting, offline results, and description update** (PR #418 follow-up by @KaifAhmad1 and @ZohaibHassan16):
  - Added `benchmarks/context_graph_effectiveness/reporting.py` — structured benchmark output helpers that write per-track results and aggregate SES_v2 score to `benchmarks/results/effectiveness_offline.json`.
  - Added `benchmarks/context_graph_effectiveness/test_reporting_helpers.py` — coverage for reporting module (fixture loading, JSON serialisation, threshold formatting).
  - Committed `benchmarks/results/effectiveness_offline.json` — offline run record (`142 passed, 12 skipped, 0 failed`, exit code 0, no API key required).
  - Deepened `test_decision_intelligence.py`, `test_ses_score.py`, and `test_skill_injection.py` with additional measurement-based assertions and slice breakdowns.
  - Refined `thresholds.py` values based on measured offline results.
  - Updated `benchmarks_runner.py`, `benchmarks.md`, and `benchmark_results.md` to reflect current suite state.
  - Updated `pyproject.toml` description to reflect the project's focus on Context Graphs and Decision Intelligence Layers for AI.

- **Benchmark documentation correction**:
  - The Context Graph Effectiveness suite is a manual benchmark suite and is not part of CI merge gating.
  - Benchmark reporting has been tightened so only tracks rerun with measurement-based assertions should be presented as `measured`.
  - Real-LLM tracks such as decision quality and skill injection are auxiliary manual benchmarks and should not be summarized as deterministic offline results.
  - Remaining semantic-layer and aggregate benchmark tracks are under audit until all placeholder-style assertions are removed.

- **Context Graph Effectiveness Benchmark Suite — 20 Tracks** (PR #418 by @ZohaibHassan16, extended by @KaifAhmad1):
  - **Infrastructure**: `benchmarks/context_graph_effectiveness/` with `conftest.py` (session-scoped dataset fixtures for 28 real-world corpora), `thresholds.py` (54 evidence-based pass/fail thresholds with `check_thresholds()` CI helper), `benchmarks_runner.py` extended with `--effectiveness` flag running the full suite as plain pytest.
  - **28 real-world fixture datasets** committed under `benchmarks/context_graph_effectiveness/fixtures/` — zero network access at test time:
    - Decision intelligence: German Credit (200), IBM HR Attrition (300), CUAD legal (100), TREC Clinical Trials 2022 (50), LEDGAR (100), Credit Risk (200), HR Promotion (300), `decision_intelligence_dataset.json` (60 cross-domain records with boundary/conflicting/overturned-precedent/no-policy record types).
    - Retrieval: MetaQA 1/2/3-hop (450 total), WebQSP (200), `retrieval_eval_dataset.json` (70 labelled queries with `relevant_node_ids` / `irrelevant_node_ids`).
    - Causal: ATOMIC 500 cause-effect pairs (CC BY 4.0), e-CARE 200 causal QA records.
    - Temporal: TimeQA 150 temporal Q&A pairs.
    - Provenance: FEVER 200 claim+evidence pairs (CC BY 4.0).
    - Deduplication: DBLP-ACM 2,224 gold pairs, Amazon-Google 1,300 pairs, Abt-Buy 1,076 pairs (all Magellan/Leipzig, research open).
    - NLP extraction: CoNLL-2003 NER 50 sentences, ACE 2005 RE+Event 60 sentences.
    - Multi-hop QA: HotpotQA 30 records (CC BY SA 4.0), 2WikiMultihopQA 15 records (Apache 2.0).
    - Commonsense reasoning: COPA 30 pairs (BSD), WIQA 20 what-if process chains.
    - Knowledge graph triples: WN18RR ~100 triples (WordNet), FB15k-237 ~85 triples (Freebase, CC BY 4.0).
  - **20 test tracks — all metrics computed from live API calls, no hardcoded values**:
    - Track 1 — Core Graph Retrieval: `ContextRetriever` on MetaQA/WebQSP; Hit@1, 2/3-hop recall, MRR, citation groundedness; hybrid alpha sweep ($\alpha=0.5$ best); thresholds anchored to published KG-RAG baselines.
    - Track 2 — Decision Quality *(real LLM, gated)*: `AgentContext` on 60-record cross-domain dataset; `decision_accuracy_delta` and `hallucination_rate_delta` both must be > 0; lightweight regex NER cross-referenced against injected context for hallucination detection; `claude-haiku-4-5` via `SEMANTICA_REAL_LLM=1`.
    - Track 3 — Causal Chain Quality: `CausalChainAnalyzer` on ATOMIC+e-CARE; recall ≥ 0.80, precision ≥ 0.85; four topology tests (linear, diamond, branching, cycle).
    - Track 4 — Decision Intelligence: `PolicyEngine` compliance evaluation; `policy_compliance_hit_rate` ≥ 0.90; causal influence score ordering verified.
    - Track 5 — Temporal Validity: `TemporalGraphRetriever`+`TemporalQueryRewriter` on TimeQA; stale/future injection rates < 0.05; temporal precision ≥ 0.90; rewriter accuracy ≥ 0.85 (16/19 intent types).
    - Track 6 — KG Algorithm Quality: community NMI ≥ 0.80 (Louvain), link predictor AUC ≥ 0.70, semantic coherence delta > 0, hash-fallback stability == 1.0; embedding cosine normalised to [0,1] — tests updated accordingly.
    - Track 7 — Reasoning Quality: Rete precision ≥ 0.95, all 13 Allen interval relations correctly classified, explanation completeness ≥ 0.90.
    - Track 8 — Provenance Integrity: `ProvenanceTracker` on FEVER; 4-hop lineage completeness == 1.0 (manual `parent_entity_id` chain walk); checksum integrity == 1.0.
    - Track 9 — Conflict Resolution: `ConflictDetector`+`ConflictResolver` on value/type/temporal/logical conflicts; recall ≥ 0.85, precision ≥ 0.90; VOTING/HIGHEST_CONFIDENCE/MOST_RECENT strategies verified.
    - Track 10 — Deduplication Quality: `SimilarityCalculator.calculate_similarity()` pair-wise on DBLP-ACM/Amazon-Google/Abt-Buy gold pairs; F1 ≥ 0.85; threshold anchored to DeepMatcher published score of 0.98.
    - Track 11 — Embedding Quality: `NodeEmbedder`, `GraphEmbeddingManager`; semantic coherence delta > 0, hash-fallback stable, batch/single consistency < 0.01.
    - Track 12 — Change Management: `VersionManager`; snapshot fidelity == 1.0, version diff correctness == 1.0, 50-snapshot overhead < 5 s.
    - Track 13 — Skill Injection *(real LLM, gated)*: 6 skill types (temporal, causal, policy, precedent, uncertainty, escalation); activation rate ≥ 0.70 detected via regex patterns in LLM output.
    - Track 14 — Semantic Extraction: `NERExtractor(method="pattern")` on CoNLL-2003; entity-span F1 (overlap matching) ≥ 0.60; `RelationExtractor` entity-pair detection ≥ 0.60; event detection recall ≥ 0.65; KG triplet node-addition accuracy ≥ 0.70.
    - Track 15 — Context Quality Metrics: CRS ≥ 0.70, CNR < 0.30, SCR ≥ 2.0 (signal-to-context ratio), redundancy score ≥ 0.80; monotonicity invariant verified structurally.
    - Track 16 — Graph Structural Integrity: WN18RR/FB15k-237 triple retrieval ≥ 0.95, relation type coverage ≥ 0.90; integrity invariants: no dangling edges, temporal consistency, cycle detection, contradiction detection.
    - Track 17 — Extended Multi-hop: HotpotQA bridge recall ≥ 0.65, comparison recall ≥ 0.70; 2WikiMultihop 4-hop chain recall ≥ 0.60; all tests use direct BFS via `get_neighbor_ids()` (not `ContextRetriever`).
    - Track 18 — Abductive & Deductive Reasoning: COPA `find_explanations()` coverage ≥ 0.60/0.55 (cause/effect); WIQA Rete deductive chain recall ≥ 0.65.
    - Track 19 — Entity Linking & Graph Validation: `EntityResolver` fuzzy precision ≥ 0.80, recall ≥ 0.75; `GraphValidator` false-positive rate < 0.05.
    - Track 20 — Composite SES Score: Semantica Effectiveness Score = mean of 8 live components (retrieval hit rate, causal recall, temporal precision, policy compliance, dedup F1, provenance completeness, context relevance, NER F1 proxy); SES ≥ 0.70 overall, ≥ 0.60 per domain (lending, healthcare, legal, HR); regression floor ≥ 0.50.
  - **Semantic Layer Pillar — Tracks 21–25** (Jaffle Shop governed metric fixtures; all tests use `ContextGraph` direct API; Track 22 is real-LLM gated):
    - Track 21 — Semantic Metric Exactness: `ContextGraph` stores 8 Jaffle Shop governed metrics; NL query → canonical metric name resolution; alias resolution; dimension conformance (grain-aware); 6 tests, all passing.
    - Track 22 — NL-to-Governed-Decision (real LLM, `SEMANTICA_REAL_LLM=1`): governed_decision_delta > 0.35 (semantic layer lifts LLM metric accuracy ≥ 35pp over baseline); semantic_hallucination_rate ≤ 0.05; skipped in normal CI.
    - Track 23 — Metric-Graph Hybrid Reasoning: metric node + causal chain + policy nodes stored and traversed via BFS; `hybrid_recall ≥ 0.75`; `causal_root_accuracy ≥ 0.70`; `metric_policy_linkage_rate ≥ 0.90`; 6 tests, all passing.
    - Track 24 — Governance Impact & Change Propagation: 8 before/after metric change records; 21-entry policy decision registry; `metric_change_impact_score ≥ 0.95` (GDPR/SOX auditability SLA); `decision_drift_rate ≤ 0.02` (production SLA); 4 tests passing, 1 skipped (VersionManager optional).
    - Track 25 — Agentic Semantic Consistency: 5 multi-turn traces; detects silent metric definition drift across turns; `cross_turn_metric_consistency ≥ 0.90`; `threshold_stability_rate ≥ 0.95`; `trace_buildability_rate == 1.0`; 5 tests, all passing.
  - **New fixtures** (`fixtures/semantic_layer/`): `jaffle_shop_metrics.json` (8 governed metrics, 15 NL queries, 8 conformance tests), `metric_change_pairs.json` (8 change records, 21-decision registry), `hybrid_metric_graph.json` (8 hybrid records with causal chains), `agentic_conversation_traces.json` (5 multi-turn traces).
  - **Updated SES formula**: `SES_v2 = 0.7 × ContextGraphScore (Tracks 1–20) + 0.3 × SemanticLayerScore (Tracks 21–25)`; new composite baseline ≥ 0.72.
  - **Final result: 163 passed, 33 skipped, 0 failed** across all 25 tracks.
  - **Bug fixes applied during implementation** (all found via review by @KaifAhmad1):
    - Removed `if False else 0.0` guard in stale injection test — rate now uses computed value.
    - `future_count` no longer discarded; feeds `future_injection_rate` directly.
    - Causal recall/precision computed from `retrieved_ancestors ∩ true_ancestors` sets, not hardcoded 1.0.
    - `multi_source_boost` reads actual scores from `_rank_and_merge` return value.
    - Silent `if embedder: assert ...` vacuous passes replaced with `pytest.skip()`.
    - `hybrid_similarity.py`: scipy imports wrapped in `try/except` with numpy fallbacks — fixes Windows 11 import cascade that caused `ContextGraph` to fail everywhere.
  - **Documentation**:
    - `benchmarks/benchmarks.md` — complete rewrite with LaTeX metric formulas, theoretical background per track, dataset provenance with conference citations, research paper reporting guidance, comparison table against published baselines (DeepMatcher, KG-RAG, MetaQA, DPR, TimeQA, Louvain), and ablation study design for decision intelligence.
    - `benchmarks/benchmark_results.md` — updated with genuine measured results for all 20 tracks; per-track metric tables, threshold rationale, and key implementation notes.
- **Named Graph Support: Review Follow-up Fixes** (PR #432 by @Sameer6305, follow-up patch by @KaifAhmad1):
  - Fixed `enable_named_graphs` handling so `TripletStore.execute_query()` now forwards `supports_named_graphs=False` when named-graph support is disabled in config.
  - Fixed duplicate dataset clause behavior in `QueryEngine.prepare_query()` so the same URI is not emitted as both `FROM <...>` and `FROM NAMED <...>`.
  - Added backward-compatible config alias support for `default_graph_uri` alongside existing `default_graph`.
  - Hardened graph URI handling in version-pruning `DROP SILENT GRAPH` updates by percent-encoding unsafe characters before SPARQL interpolation.
  - Added focused regression tests covering config-flag enforcement, duplicate clause prevention, `default_graph_uri` alias behavior, and pruning-path URI sanitization.
  - Verified with targeted feature tests: `tests/triplet_store/test_triplet_store.py` and `tests/change_management/test_managers.py` (54 passed).

### Added

- **XML File Ingestion Support** (#560) by @Luffy2208
  - Added `XMLIngestor` class with `lxml` backend for parsing local XML files
  - Nested element hierarchy and flat element list extraction
  - Namespace and prefix extraction with collision handling
  - Attribute and element metadata extraction
  - Optional XSD schema validation with detailed error reporting
  - Optional DTD validation (internal and external)
  - Secure-by-default parser (`resolve_entities=False`, `no_network=True`) blocking XXE attacks
  - `ingest_xml()` convenience function and `ingest_file(..., method="xml")` support
  - Unified `.xml` auto-detection via `ingest("file.xml")`
  - Directory ingestion with recursive scanning and `fail_fast` support
  - `ingest_string()` for in-memory XML bytes/str ingestion
  - Comprehensive test coverage (8/8 tests passing)

### Fixed

- **NERExtractor LLM method returning pattern-based output on custom gateways** (#554, PR #556) by @KaifAhmad1

  `NERExtractor(method="llm")` silently fell back to regex/pattern extraction when used with OpenAI-compatible enterprise or self-hosted gateways (Qwen, LLaMA proxies, internal routing layers). Returned entities carried `extraction_method='pattern'` even though the LLM itself was producing correct tool-call output. Three root causes fixed:

  - **Silent exception swallowing** — `exc_info=True` was missing from the method-failure `WARNING` in `NERExtractor.extract_entities`. The full gateway-rejection traceback was invisible in logs even with `DEBUG` level enabled, making the failure impossible to diagnose without reading source code.

  - **`response_format=json_object` sent to incompatible gateways** — `OpenAIProvider.generate_structured` unconditionally included `response_format={"type": "json_object"}` in every API call. Custom/enterprise gateways frequently reject this parameter, causing both the `instructor` path and the manual repair loop to fail with the same error on every retry, eventually triggering `_extract_fallback` (pattern extraction).

  - **No fallback in the `generate_typed` manual repair loop** — when `generate_structured` itself raised (due to gateway rejection), the repair loop retried the identical failing call up to `max_retries` times before giving up. There was no path to recover via plain `generate()` + JSON parsing.

  **Additional fixes applied during PR review:**

  - Mode.JSON retry in `generate_typed` now strips `response_format` from `create_kwargs` before forwarding to the retry client, preventing incompatible kwargs from being sent to a client configured for a different instructor mode.
  - `exc_info=True` added to the `generate_structured` fallback warning in the manual repair loop for consistent observability across all failure paths.
  - Removed dead duplicate `is_available` definition in `GroqProvider` — Python silently kept only the second definition; the first was unreachable.
  - `OpenAIProvider._init_client` now validates `base_url` scheme at construction time. Non-HTTP(S) schemes (`file://`, `ftp://`, `javascript:`, etc.) raise `ValueError` immediately, preventing SSRF if `base_url` originates from configuration rather than hardcoded values.

  **17 regression tests** added in `tests/test_issue_554_fixes.py` covering all bug paths, including harshalizode's exact gateway configuration.

---

## [0.5.0] - 2026-05-11

### Added

- **Distance Intelligence Embedding Cache Optimization** by @KaifAhmad1
  - Implemented per-session graph revision-based embedding cache to avoid re-scanning all nodes on every request
  - Added `get_cached_embeddings()` method to GraphSession with thread-safe caching and automatic invalidation
  - Updated distance matrix and semantic neighborhood endpoints to use cached embeddings for significant performance improvement
  - Added graph revision tracking using hash-based identifiers for cache invalidation
  - Implemented force refresh capability and automatic cache invalidation on graph modifications (add_nodes/add_edges)
  - Resolved TODO in `graph.py` for embedding caching optimization
- **Parquet File Ingestion Support** (#548) by @Luffy2208
  - Added ParquetIngestor class with PyArrow backend
  - Single file and partitioned directory ingestion
  - Schema and metadata extraction capabilities
  - Selective column reading with memory efficiency
  - Hive-style partition discovery support
  - Unified dispatch integration
  - Optional dependency management (ingest-parquet extra)
  - Comprehensive test coverage (32/32 tests passing)

**Ontology Hub** (part of #517)

- **Alignments tab** (PR #524, @KaifAhmad1 @ZohaibHassan16) — cross-ontology alignment authoring UI:
  - Create/edit/delete alignments with source URI, target URI, relation selector (owl:equivalentClass, all five skos:*Match variants), confidence slider, provenance, and reviewer fields.
  - Pairwise alignment matrix: scrollable table for all loaded ontology pairs; clicking a badge pre-fills the form.
  - Alignment suggestions via `POST /api/ontology/suggest-alignments` — blended score (0.4×label + 0.6×TF-IDF char-ngram cosine); one-click accept.
  - Ephemeral-storage banner; all handlers wrapped in `useCallback`.
- **Health Dashboard** (PR #524) — per-ontology quality scoring across 5 dimensions:
  - Completeness, Consistency, SHACL (stub), Alignment, Documentation.
  - Total score computed as mean of scoreable dimensions only (SHACL excluded when unavailable).
  - Issue list with severity badges (error/warning/info), entity URI chip, "Fix in Editor" deep-link.
  - Downloadable JSON health report; `GET /api/ontology/health` with `_MAX_ANALYSIS_NODES = 5 000` OOM cap.
- **SHACL Studio** (PR #524) — interactive SHACL shape authoring:
  - Shape generation via `POST /api/ontology/shacl/generate` (permissive/standard/strict tiers).
  - Shape library panel with per-shape Turtle extraction; "View all" restores full document.
  - Monaco editor with custom Monarch tokenizer for Turtle syntax.
  - Validation stub via `POST /api/ontology/shacl/validate`; rejects empty/invalid Turtle with HTTP 422.
- **Visual Ontology Editor** (PR #519, @KaifAhmad1) — @xyflow/react canvas for authoring classes/properties/individuals without hand-writing OWL/Turtle:
  - Context menus on nodes (rename, add super/subclass, restrictions, SKOS metadata, deprecation, delete with impact count) and edges (toggle functional/symmetric/transitive/inverse-functional, add inverse).
  - All edits debounced and staged as pending diffs via `PATCH /api/ontology/draft`; nothing commits until proposal publish.
- **Versions & Proposals tab** (PR #519) — version timeline, proposal review (approve/reject/publish), SHACL pre-validation, side-by-side diff via `VersionManager.diff_ontologies()`.
- **Ontology Registry** (PR #518, @KaifAhmad1) — full CRUD with status/format badges, per-ontology stats, live search, filter pills (All/OWL/SKOS/Internal/External), action feedback auto-hide.
- **Ontology Loader** (PR #518) — three-mode modal: URL import (fetch preview + load), file upload (.ttl/.rdf/.owl/.nt/.jsonld/.n3), create new (scratch/from-data/from-text).
- **Entity Search panel** (PR #518) — debounced 320 ms search across all loaded ontologies; type filter pills; result detail panel with super/subclasses, domain/range, instance count.
- **SKOS Vocabulary Manager** (PR #518) — hierarchical concept browser with recursive `ConceptTreeNode`, client-side `filterConcepts()`, full SKOS annotation detail (definition, scopeNote, broader/narrower/related/exactMatch).
- **16 backend endpoints** under `/api/ontology` — registry, preview, load, create, search, entity, skos/schemes, skos/concept, draft, proposals CRUD, versions, alignments, health, shacl/generate, shacl/shapes, shacl/validate (PRs #518, #519, #524).
- **Explorer landing page redesign** (PR #516, @ZohaibHassan16) — hero section, animated SVG graph preview, live `/api/graph/stats` metrics, workspace launcher; `Space Grotesk` / `IBM Plex Sans` fonts; `prefers-reduced-motion` support.
- **Distance Intelligence** (PR #502, @KaifAhmad1):
  - `ContextGraph.get_neighbors(include_distance_metadata)` — adds `distance_band`, `confidence_decay`, `path_to_anchor` per result.
  - `AgentContext.retrieve()` / `find_precedents()` blend graph proximity with semantic score (`combined_score = (1−w)×semantic + w×proximity`).
  - 5 new API endpoints: `POST /api/graph/distance-matrix` (N×N, upper-triangle mirrored), `GET /api/graph/node/{id}/semantic-neighborhood`, `GET /api/decisions/causal-distance`, `GET /api/temporal/distance-history`, `POST /api/export/distance-enriched` (CSV/JSONL, capped at 200 nodes).
  - Explorer UI: Ego Mode (BFS depth-of-field fading, depth slider 1–8), Structural overlay, Semantic overlay, Heatmap (green→red by hop); Path inspector with distance band chip, metric cards, bottleneck node highlight.
  - 57 new tests in `tests/context/test_distance_intelligence.py`.
- **Graph Explorer visual refresh** (PR #503, @ZohaibHassan16) — structured `ui.*` design-token namespace; per-shape biomolecule/condition/compound config; decomposed toolbar memos; typed sub-components (`SearchCommandBar`, `ToolbarCluster`, etc.); deterministic LOD edge classification via `GraphFullEdgeClass`.
- **Graph Workspace declutter** (PR #483, @ZohaibHassan16) — calmer default presentation for dense graphs, display-edge aggregation with raw-edge bundle retention, grouped community view, neighborhood collapse/expand.
- **Bidirectional path finding** (closes #469, @KaifAhmad1) — `directed=false` query param on BFS and Dijkstra; undirected view built via `graph.to_undirected()` for traversal only; empty-path 404 guard; `PathResponse.directed` field.
- **Node distance semantics in path responses** (closes #472) — `PathResponse` gains `hop_count` and `distance_band` ("direct"/"near"/"mid-range"/"distant"); `classify_path_distance()` in `semantica/utils/helpers.py`; `KGVisualizer.visualize_network(highlight_path)` with band-scaled edge rendering.
- **Native `KnowledgeGraph` type support in `KGVisualizer`** (closes #471) — formal `KnowledgeGraph` dataclass (`entities`, `relationships`, `metadata`); `_normalize_graph()` duck-types input; raises clear `ProcessingError` on unknown types. 21 tests added.
- **Indexed search for large graphs** (PR #481, @ZohaibHassan16) — purpose-built inverted index with exact/token/prefix lookup tiers; LRU cache (128 slots); O(log n) mutation sync via `bisect.insort`; warm-query time 24 ms → 0.004 ms on 118 k-node graph.
- **Provenance traversal multi-hop fix** (PR #480, @Sameer6305) — undirected ego-graph expansion so upstream ancestors at depth ≥ 2 are no longer silently excluded; `ProvenanceEdge.direction` field (upstream/downstream/lateral); grouped markdown report under `## Upstream/Downstream/Lateral` sections.
- **TripletStore ontology namespace** (PR #447, @KaifAhmad1) — `_resolve_iri()` applies `base_uri` before `urn:` fallback; W3C prefix expansion table (owl/xsd/rdf/rdfs/skos) expands to canonical IRIs regardless of `base_uri`.
- **Blazegraph literal serialization** (PR #448, @KaifAhmad1) — `_format_object_for_sparql()` selects IRI/typed-literal/language-tagged-literal/plain-literal token; `_resolve_datatype_iri()` with prefix expansion; RFC 5646 language-tag validation; `_escape_literal()` for string escaping.
- **DeepSeek provider via OpenAI SDK** (PR #482, @liling) — `_init_client` rewritten using `openai.OpenAI(base_url=self.base_url)` instead of defunct `deepseek` package; `verbose_mode` assignment fix; `pyproject.toml` updated to `openai>=1.0.0`.

- **`DuplicateDetector` result limiting and ranking** (issue #534, by @KaifAhmad1):
  - `max_results` — hard global cap on returned candidates; applied after sorting. `None` means no limit.
  - `top_k_per_entity` — keep at most *k* candidates per entity (by the sort field) so no single entity floods the output. `None` means no per-entity limit.
  - `min_similarity` — extra similarity floor on top of `similarity_threshold`; candidates below it are dropped before ranking. `None` means no extra floor.
  - `sort_by` — ranking field before limits are applied; accepts `"confidence"` (default) or `"similarity_score"`. Invalid values raise `ValueError` at construction time.
  - All four options are applied by the new `_apply_result_limits` helper and are respected by both `detect_duplicates()` and `incremental_detect()`.
  - 15 new tests in `TestResultLimiting` covering each option in isolation and in combination.
  - **Follow-up Qodo review fixes** (by @KaifAhmad1):
    - `top_k_per_entity` now uses OR semantics — a candidate is kept if *either* entity is still under quota, preventing high-quality pairs from being silently dropped when a popular counterpart saturates its limit.
    - `max_results` and `top_k_per_entity` now validated at construction time; negative or non-integer values raise `ValueError`.
    - `min_similarity` now validated in `[0.0, 1.0]` at construction; out-of-range values raise `ValueError`.
    - Added `_normalize_entity_id` helper (always returns `str`) used consistently in both `_apply_result_limits` and `_build_duplicate_groups`, eliminating `int` vs `str` ID key mismatches.
    - Updated `detect_duplicates` and `incremental_detect` docstrings to reflect the configurable `sort_by` field.

### Fixed

- **Fix: `ConflictDetector.detect_conflicts()` raises `AttributeError` when called with `method=` or `property_name=` kwargs** (issue #533, PR conflicts, by @KaifAhmad1):
  - `detect_conflicts` was defined twice in `conflict_detector.py`; Python silently overwrote the first (dispatcher) definition with the second (comprehensive), which accepted no `method` or `property_name` parameters — causing `AttributeError` or `TypeError` for any caller using those kwargs.
  - Removed the first (dead) definition and merged its dispatcher logic into the surviving method. New signature: `detect_conflicts(entities, method="all", property_name=None, entity_type=None, **kwargs)`.
  - Supported `method` values: `"all"` (default, comprehensive), `"value"`, `"property"`, `"type"`, `"relationship"`, `"temporal"`, `"logical"`, `"entity"`. Unknown values raise `ValueError`.
  - Fixed `method="relationship"` silently defaulting `relationships` to the entities list, which caused entity dicts to be iterated as relationship dicts producing silent wrong results (`None_None_None` keys). Now defaults to `[]` with dict normalization.
  - Removed unreachable dead code (`for field_name in fields_to_check` loop after `try/except raise`) in `detect_entity_conflicts`.
  - **Follow-up Qodo review fix** — hardened `method="relationship"` normalization: when `relationships` kwarg is a dict whose `"relationships"` value is itself a non-list (or the key is absent), the value is now always wrapped in a list before being passed to `detect_relationship_conflicts`, guaranteeing `List[Dict]` input in all cases.

- **Fix: `semantica[all]` installation fails on Windows due to `faiss-gpu` dependency** (issue #532, PR #utlis, by @KaifAhmad1):
  - `[all]` bundled the `[gpu]` extra (`faiss-gpu>=1.7.0`, `cupy>=10.0.0`), which has no Windows builds, causing `pip install "semantica[all]"` to fail with `No matching distribution found for faiss-gpu>=1.7.0`.
  - Removed `gpu` from both `[all]` lines in `pyproject.toml` — `[all]` now installs only cross-platform dependencies. Users on Linux who need GPU acceleration can install `semantica[gpu]` explicitly.

- **Fix: Progress tracker crashes with `UnicodeEncodeError` on Windows cp1252 consoles** (issue #531, PR #utlis, by @KaifAhmad1):
  - `ConsoleProgressDisplay.update()` had 5 direct `sys.stdout.write()` calls that bypassed the existing `_safe_write()` guard, causing `UnicodeEncodeError` when emoji characters (`🧠`, `📊`) were written to cp1252-encoded consoles during any progress-tracked operation.
  - All 5 calls replaced with `self._safe_write()`, which catches `UnicodeEncodeError` and re-encodes output with `errors="replace"` so progress output never crashes the process.
  - Added `TestProgressTrackerEncoding` regression class (3 tests) covering `_safe_write` safety, pipeline header write, and auto emoji-disable on cp1252 stdout.

- **Fix: Break circular import in `semantic_extract`; address Qodo review bug** (issue #528, PR #536, by @ZohaibHassan16, review fixes by @KaifAhmad1):
  - **Root cause** — `ner_extractor.py` imported `get_entity_method` from `methods.py`, while `methods.py` imported `Entity` from `ner_extractor.py`, creating a circular import that raised `ImportError: cannot import name 'Entity' from partially initialized module` on any import of `semantica.semantic_extract`.
  - `semantica/semantic_extract/types.py` (new) — shared `Entity`, `Relation`, and `Triplet` dataclasses extracted into a dedicated module that neither side of the old cycle imports, so both `ner_extractor`, `relation_extractor`, `triplet_extractor`, and `methods` can import from it freely.
  - `semantica/semantic_extract/__init__.py` — lazy-loads package-level exports so core extractor imports do not pull in optional modules (e.g. the YAML-backed semantic network extractor); added `TripleExtractor` as a compatibility alias for `TripletExtractor`; legacy re-exports from the individual extractor modules preserved for backward compatibility.
  - `semantica/semantic_extract/methods.py` — updated to import shared types from `types.py`; extractor-specific imports moved to function scope where needed to prevent re-introducing the cycle.
  - Added regression tests (`tests/semantic_extract/test_imports.py`) covering import order independence (methods-before-extractors and extractors-before-methods), legacy type import compatibility, `TripleExtractor` alias, and that core imports do not require `yaml`.
  - **Review fix (Qodo — Py3.8 test import crash)**: `test_imports.py` annotated `_run_python` as `-> subprocess.CompletedProcess[str]`, which is not subscriptable at runtime on Python 3.8 (generic subscript on built-in types requires 3.9+). Added `from __future__ import annotations` (PEP 563) so all annotations are lazy strings never evaluated at import time, restoring compatibility with the declared `requires-python = ">=3.8"` without any behaviour change on 3.9+.
- **Fix: Lazy-load optional ingest backends; address Qodo review bugs** (issue #527, PR #535, by @ZohaibHassan16, review fixes by @KaifAhmad1):
  - `semantica/ingest/__init__.py` — core exports (`FileIngestor`, `ingest_file`, config, registry) remain eagerly imported; all optional backends (`WebIngestor`, `FeedIngestor`, `RepoIngestor`, `EmailIngestor`, `StreamIngestor`, `DBIngestor`, `MCPIngestor`, `OntologyIngestor`, `SnowflakeIngestor`) are now deferred behind a module-level `__getattr__`, so `from semantica.ingest import FileIngestor` no longer fails when GitPython or BeautifulSoup4 are absent.
  - `semantica/ingest/methods.py` — backend imports relocated into their respective ingestion functions (`ingest_web`, `ingest_feed`, `ingest_repository`, `ingest_email`) with helper `_missing_optional_dependency()` / `_is_missing_dependency()` for consistent, actionable error messages.
  - **Review fix (Bug 1 — overbroad missing-dep detection)**: replaced `except ImportError` with `except ModuleNotFoundError` in all four function-level import guards and in `__getattr__`. `ImportError` catches failures thrown by code *inside* a successfully found module, masking real bugs with a misleading "package not installed" message; `ModuleNotFoundError` (its subclass) is specific to absent modules. Simplified `_is_missing_dependency` to rely solely on `exc.name` now that `ModuleNotFoundError` always sets it.
  - **Review fix (Bug 2 — expected errors logged as failures)**: added `except ConfigurationError: raise` before the blanket `except Exception` handlers in `ingest_web`, `ingest_feed`, `ingest_repository`, and `ingest_email`. Missing optional dependencies are expected user-configuration issues and must not produce error-level log entries.
  - **Review fix (Bug 3 — test blocker not setting `exc.name`)**: `OptionalDependencyBlocker.find_spec` now sets `err.name = root_name` on the manually constructed `ModuleNotFoundError`, matching what Python's import machinery does, so `_is_missing_dependency` correctly identifies the missing package in tests.
  - Added regression tests (`tests/ingest/test_optional_imports.py`) that block the `git` and `bs4` modules via a custom meta path finder and assert core imports succeed and backends raise `ConfigurationError` with an actionable message.
- **Fix: Ontology Hub post-review bug fixes and security hardening** (follow-up to #518, closes security advisory #23, by @KaifAhmad1):
  - **Broken registry filters** — `fetchRegistry` was sending toolbar filter values (`owl`, `skos`, `internal`, `external`) to the backend as the `status` query param, which only accepts `published|draft|external`, causing those filters to return empty lists. Removed the spurious `status` param; all format/kind filtering is now applied client-side via `filteredEntries`, which already had the correct logic.
  - **Toggle/refresh URI corruption** — `toggle_ontology` and `refresh_ontology` applied `.removesuffix("/toggle")` / `.removesuffix("/refresh")` to the captured path parameter, which would silently corrupt any ontology URI that legitimately ends with those strings. Starlette's route regex (`/{uri:path}/toggle`) already strips the literal suffix via backtracking, so the `removesuffix` calls were removed and the raw `ontology_uri` parameter is used directly.
  - **SSRF in URL fetch** — `_fetch_url_sync()` accepted arbitrary user-supplied URLs and called `requests.get()` with no validation, enabling server-side request forgery against internal services. Added `_validate_fetch_url()` which rejects non-`http`/`https` schemes and resolves the hostname via `socket.getaddrinfo`, blocking loopback, private, link-local, reserved, and multicast addresses.
  - **File upload format misdetected** — the file picker accepted `.xml` and `.json` but `fmtMap` had no entries for those extensions, causing them to default to `turtle`. Added `xml: "xml"` and `json: "json-ld"` mappings. Changed the unknown-extension fallback from `|| "turtle"` to `?? ""` (empty string), and omit the `format` key from the request body when empty so the backend `_detect_format()` runs instead of receiving a forced incorrect value. Also added `.n3` to the accepted extension list and dropzone hint.
  - **Inconsistent XML hardening** — `_parse_rdf_sync()` called `rdflib.Graph().parse()` directly, bypassing the `defusedxml`-based XXE protection already present in `semantica/explorer/utils/rdf_parser.py`. Now routes through `_safe_parse_rdf()` from that module, applying consistent protection for all RDF/XML parse paths.
  - **Search scans whole graph** (`GET /api/ontology/search`) — the endpoint fetched up to 999 999 nodes and performed a linear Python substring scan on every request. Replaced with `session.search(q, limit * 6)` which uses the `GraphSearchIndex`; results are then post-filtered by `_SEARCHABLE_TYPES` and `entity_type` before being returned up to the requested limit.
  - **ReDoS in format detector** (security advisory #23, CodeQL `py/polynomial-redos`, CWE-1333/730/400) — `_detect_format()` used `re.match(r"_:\w+|<[^>]+>\s+<[^>]+>", ...)` to detect N-Triples content. The `<[^>]+>\s+<[^>]+>` alternative was flagged as a polynomial regular expression on uncontrolled data. The URI-subject branch was already unreachable (strings starting with `<` return `"xml"` two lines above), so the entire regex was replaced with two O(1) string operations: `stripped.startswith("_:")` and `" <" in stripped`. `import re` removed as now unused.
- **OWLExporter Turtle syntax** (closes #478) — invalid multi-block output fixed via `_ttl_block()`; data properties no longer silently dropped; `_escape_ttl_str()` applied to all label/comment/version sites. 43 tests added.
- **OWLGenerator schema compatibility** (Issue #446) — label-first IRI fallback, list-typed datatype ranges, per-call namespace consistency, `subClassOf`/`subclassOf` parity.
- **TripletStore IRI regressions** (PR #447 follow-up) — non-string IDs coerced to `str()`; W3C prefix expansion now correct regardless of `base_uri`.
- **`KGVisualizer` accepts `KnowledgeGraph` objects** (closes #458) — `_normalize_graph()` duck-types input; raises clear `ProcessingError` on unknown types. 21 tests added.
- **Semantic Distance UI slash-safe routes** (PR #515, @ZohaibHassan16) — query-param routes `/api/graph/semantic-neighborhood?node_id=` and `/api/graph/path?source=&target=` bypass FastAPI's `%2F` pre-decode; legacy path-segment routes kept as deprecated aliases.
- **Explorer Distance Intelligence rendering** (PR #513, @ZohaibHassan16) — distance state flows through Sigma reducer/theme pipeline instead of mutating raw graph attributes; `restoreNodeColors()` race eliminated by merging ego/heatmap `useEffect` hooks.
- **Distance Intelligence code review regressions** (PR #502 follow-up, @KaifAhmad1) — `top_k` param name fix; `include_distance_metadata` gated behind `False` default; `weakest_link` key standardized; temporal sampling uses `timedelta` not `timetuple`; O(E×L) decay replaced with O(E) index; `AgentContext._apply_proximity_metadata` stores `graph_node_id` separately; sweep animation `sweepGeneration` counter fix; HTTP 413 for >200 node subsets; upper-triangle distance matrix.
- **Knowledge Explorer blockers** (PR #420, @ZohaibHassan16):
  - `Dockerfile`: renamed `DockerFile` → `Dockerfile`; fixed `CMD` module path; added `app = create_app()` at module level.
  - CORS: default origins narrowed from `"*"` to `localhost:5173` only.
  - `get_ws_manager()` now raises HTTP 503 instead of unhandled `AttributeError`.
  - SPARQL: read-only enforcement — `INSERT`/`DELETE`/`UPDATE`/`LOAD`/`DROP` rejected.
  - Vocabulary: 10 MB upload cap; JSON-LD format auto-detection for `.jsonld`/`.json-ld`/`.json`.
  - Annotation `O(1)` lookup via `GraphSession.get_annotation(id)`.
  - Self-loop guard in `batchMergeEdges` prevents Graphology crash.
  - Static build artifacts removed from git; `semantica/static/` added to `.gitignore`.
- **Ontology Hub post-review hardening** (PR #518 follow-up, @KaifAhmad1):
  - Registry filter: `status` param removed from `fetchRegistry`; filtering applied client-side.
  - Toggle/refresh URI: removed `.removesuffix()` calls that corrupted URIs ending with those strings.
  - Format detector: `_detect_format()` ReDoS eliminated — `re.match` replaced with two O(1) string ops.
  - Broken `fmtMap` entries: added `xml`/`json` mappings; unknown-extension fallback changed from `|| "turtle"` to `?? ""`.
  - XML hardening: `_parse_rdf_sync()` now routes through `_safe_parse_rdf()` for consistent defusedxml XXE protection.
  - Search: replaced O(999 999) linear scan with `GraphSearchIndex`-backed `session.search()`.

### Security

- **12 vulnerability fixes** (PR security-enhancement, @KaifAhmad1):
  - **[CRITICAL — CWE-95]** Eval injection in `media_parser.py`: replaced `eval(ffprobe_output)` with `fractions.Fraction`.
  - **[CRITICAL — CWE-502]** Pickle deserialization in `agent_memory.py`: replaced with JSON; legacy `.pkl` files detected and refused with migration message.
  - **[HIGH — CWE-89]** SQL injection in `snowflake_ingestor.py`: `LIMIT`/`OFFSET` parameterized; `ORDER BY` regex-validated; `WHERE` clauses containing semicolons rejected.
  - **[HIGH — CWE-611]** XXE in `rdf_parser.py`: `defusedxml.defuse_stdlib()` before all RDF/XML parsing.
  - **[HIGH — CWE-346/200]** Missing security headers in `server.py`: `CORSMiddleware`, `X-Content-Type-Options`, `X-Frame-Options`, HSTS, generic 500 handler.
  - **[HIGH — CWE-346/400]** Overpermissive CORS in `explorer/app.py`: methods/headers narrowed; 64 KB WebSocket frame cap.
  - **[MEDIUM — CWE-20]** Algorithm param unconstrained in `graph.py`: enum-validated `bfs|dijkstra` only.
  - **[MEDIUM — CWE-434]** RDF upload without extension check in `vocabulary.py`: `.ttl/.rdf/.owl/.xml/.jsonld` allowlist enforced.
  - **[MEDIUM — CWE-1336]** Prompt injection in `llm_extraction.py`: user-supplied content wrapped in `json.dumps()`.
  - **[MEDIUM — CWE-95]** Dynamic `__import__()` in `pipeline_validator.py`: replaced with proper module-level import.
  - **[MEDIUM — CWE-1333]** ReDoS in `enrich.py`: whitespace-normalize then split on literal `" AND "`.
  - **[LOW — CWE-22]** Path traversal in `server.py` SPA route: `Path.resolve().relative_to()` guard; 400 on escape.
  - **[LOW — CWE-400]** Unbounded SPARQL in `sparql.py`: 5 000-row cap, 30 s `asyncio.wait_for` timeout, `Semaphore(4)` concurrency cap; `SparqlResponse.truncated` field added.
  - **[LOW — CWE-434]** Import upload in `export_import.py`: 50 MB cap; `{.json,.csv}` allowlist.
  - CodeQL `paths-ignore` for `cookbook/**/*.html` to suppress false-positive JS alerts #15–18.
- **SSRF in Ontology Hub** (PR #518 follow-up): `_validate_fetch_url()` rejects non-http/https schemes and resolves hostname via `socket.getaddrinfo`, blocking loopback/private/link-local/multicast addresses.

---

## [0.4.0] - 2026-04-08

### Added

**Temporal Intelligence** (@KaifAhmad1, PRs #396–#402)

- **Core Temporal Data Model** (PR #396) — `semantica.kg.temporal_model` with shared parsing/normalization/serialization helpers; `TemporalBound` and `BiTemporalFact` exported from `semantica.kg`; valid-time and transaction-time filtering; `TemporalValidationError` on invalid inputs; history-preserving revisions in `TemporalVersionManager.apply_revision()` with supersession semantics.
- **Point-in-Time Query Engine** (PR #397) — `TemporalGraphQuery.reconstruct_at_time(graph, at_time)` builds consistent point-in-time subgraphs without mutating source; `TemporalConsistencyReport` detects inverted intervals, relationships outside entity lifetimes, overlapping same-type relationships, and temporal gaps; sequence/cycle pattern detection; calendar-aligned evolution bucketing via `temporal_granularity`; causal ordering controls on `find_temporal_paths()` (strict/overlap/loose).
- **Deterministic Temporal Reasoning Engine** (PR #398) — `semantica.kg.temporal_reasoning`; full Allen interval algebra via `IntervalRelation` (all 13 relations); `TemporalReasoningEngine` with interval merging, gap analysis, coverage calculation, timelines, retroactive coverage; zero LLM calls; circular import risk between `semantica.reasoning` and `semantica.kg` eliminated.
- **Temporal Awareness in ContextGraph** (PR #399) — `Decision` dataclass gains `valid_from`/`valid_until`; superseded decisions remain in graph (immutable history); `find_precedents_by_scenario(include_superseded, as_of)`; `ContextGraph.state_at(timestamp)` serializable snapshot; `CausalChainAnalyzer.trace_at_time(event_id, at_time)`; `AgentContext.checkpoint(label)`, `diff_checkpoints()`, `flush_checkpoint()`.
- **Temporal Metadata Extraction from Text** (PR #400):
  - `extract_relations_llm(extract_temporal_bounds=True)` — each `Relation` gains `valid_from`, `valid_until`, `temporal_confidence` (0.0–1.0), `temporal_source_text`; default `False` is 100% backward-compatible.
  - Calibrated confidence anchors: 1.00 = full ISO date → 0.00 = no temporal signal.
  - `TemporalNormalizer` (zero LLM calls, pure regex + dateutil): `normalize(value)` → UTC datetime tuple or `None`; `normalize_phrase(phrase)` → metadata dict or `None`; 13-domain default phrase map; `TemporalAmbiguityWarning` for ambiguous DD/MM/YYYY inputs (never silently guesses locale).
- **Temporal Provenance & OWL-Time Export** (PR #401):
  - `ProvenanceTracker.track_entity()` auto-stamps `recorded_at` on every new record.
  - `query_recorded_between(start, end)`, `revision_history(fact_id)`, `export_audit_log(fact_ids, format)` (JSON/CSV).
  - `RDFExporter.export_to_rdf(include_temporal=True, time_axis="valid|transaction|both")` — emits OWL-Time triples for all temporally-annotated relationships.
  - `create_snapshot()` stamps `"format_version": "1.0"`; `validate_snapshot()` and `migrate_snapshot()` for stable snapshot lifecycle.
- **Temporal GraphRAG Integration** (PR #402) — `TemporalGraphRetriever` filters retrieved context to a point in time; `ContextRetriever.query_with_reasoning(at_time, header_template)` prepends structured temporal header; `TemporalQueryRewriter` extracts temporal intent (before/after/at/during/between) from natural language; regex-only by default, optional LLM-assisted mode.

**Ontology** (@KaifAhmad1 @ZohaibHassan16)

- **SHACL Shape Generation & Validation** (PR #318) — `SHACLGenerator` derives SHACL node/property shapes from any ontology dict; three quality tiers (basic/standard/strict); Turtle/JSON-LD/N-Triples output; iterative multi-level inheritance propagation, cycle-safe; `OntologyEngine.to_shacl()`, `export_shacl()`, `validate_graph(explain=True)`; `SHACLValidationReport` with plain-English explanations for all 7 constraint types. `pip install semantica[shacl]`.
- **SKOS Vocabulary Module** (PR #319) — `TripletStore.add_skos_concept()` / `get_skos_concepts(scheme_uri)`; `OntologyEngine.list_vocabularies()`, `list_concepts()`, `search_concepts()`; `NamespaceManager.get_skos_uri()` / `build_concept_scheme_uri()`; SPARQL injection hardened.
- **Ontology Alignment API** (PR #361) — `OntologyEngine.create_alignment()`, `get_alignments()`, `list_alignments()`; OWL/SKOS standard predicates (`owl:equivalentClass`, all five `skos:*Match`); `ReuseManager.suggest_alignments()`; `QueryEngine.expand_entity_uri(use_alignments=True)` with SPARQL `VALUES` clause injection; SPARQL injection hardened.
- **Ontology Diff & Migration** (PR #367) — `VersionManager.diff_ontologies()` covering classes/properties/individuals/axioms; `ChangeLogAnalyzer.analyze()` classifying CRITICAL/HIGH/MEDIUM/INFO impact; `ImpactReport`, `generate_change_report()`; `OntologyEngine.compare_versions()` end-to-end orchestrator with optional validation and graph-instance checks.

**Knowledge Explorer API** (@ZohaibHassan16 @KaifAhmad1)

- **Full FastAPI backend** (PR #384) — `semantica.explorer` package with graph, analytics, decisions, temporal, enrichment, export/import, annotations routes; 12 export formats; WebSocket progress for import; 99 integration tests. `pip install semantica[explorer]`; CLI: `semantica-explorer --graph my_graph.json`.
- **Thread safety** (PR #385) — `ContextGraph` and `GraphSession` protected with `threading.RLock`; 8 analytics components lazily initialized under lock.
- **In-memory fallbacks** (PR #386) — All 7 `DecisionQuery` and 4 `DecisionRecorder` methods have `ContextGraph` fallback paths for in-memory usage without a graph DB.
- **Snapshot schema compatibility** (PR #393) — accepts both `nodes`/`edges` and `entities`/`relationships` snapshot schemas transparently; metadata counts always accurate.
- **Audit trail & rollback protection** (PR #394) — mutation-level audit tracking, named version tags, `restore_snapshot()` requires explicit confirmation, `get_node_history()`, `diff()` Git-like alias.
- **SKOS Vocabulary REST API** (PR #426) — `GET /api/vocabulary/schemes`, `GET /api/vocabulary/hierarchy?scheme=<uri>` with cycle detection, `POST /api/vocabulary/import` (.ttl/.rdf/.owl; HTTP 422 on invalid).
- **O(N) → O(limit) Pagination** (PR #431) — `find_nodes`/`find_edges` use `itertools.islice` on generators; ghost-node fix (accepts `source_id`/`target_id` and `source`/`target` key names); deterministic page boundaries via `sorted()`; `stats()` applies same validity filters as pagination.
- **Named graph support** (PR #432, @Sameer6305) — `enable_named_graphs` flag forwarded correctly through `TripletStore.execute_query()`; duplicate `FROM`/`FROM NAMED` clauses prevented; graph URIs percent-encoded in DROP statements.

**Integrations**

- **Agno Agentic Framework** (Issue #249, @KaifAhmad1) — 5 components, all degrading gracefully when `agno` is not installed:
  - `AgnoContextStore` — graph-backed agent memory implementing `agno.memory.db.base.MemoryDb`.
  - `AgnoKnowledgeGraph` — multi-hop GraphRAG knowledge base implementing `agno.knowledge.base.AgentKnowledge`.
  - `AgnoDecisionKit` — 6 decision-intelligence tools (record_decision, find_precedents, trace_causal_chain, analyze_impact, check_policy, get_decision_summary).
  - `AgnoKGToolkit` — 7 KG pipeline tools (extract_entities, extract_relations, add_to_graph, query_graph, find_related, infer_facts, export_subgraph).
  - `AgnoSharedContext` — team coordinator with single shared `ContextGraph`; `bind_agent(role)` returns role-scoped view; thread-safe via `RLock`.
  - 110 integration tests; 3 cookbook notebooks. `pip install semantica[agno]`.
- **Novita AI Provider** (PR #374, @Alex-wuhu) — OpenAI-compatible; default model `deepseek/deepseek-v3.2`; `NOVITA_API_KEY`; `create_provider("novita")`.

**Reasoning**

- **Native Datalog Reasoning Engine** (PR #371, @ZohaibHassan16) — pure-Python bottom-up semi-naive fixpoint with guaranteed termination; recursive Horn clause rules (e.g. `ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y).`); O(1) delta-index lookup; `load_from_graph(ContextGraph)`; `query("pred(?X, ?Y)")` with optional `bindings=`; `DatalogReasoner`, `DatalogFact`, `DatalogRule` exported from `semantica.reasoning`.

### Fixed

- **Pattern Matcher restored** (PR #387, @ZohaibHassan16) — dead code silently overwrote `_match_pattern` regex (pre-bound variable embedding, repeated-variable backreferences) with `re.escape`, breaking transitivity/symmetry/self-join rules; removed. `re.error` now surfaced instead of swallowed.
- **OllamaProvider base_url ignored** (PR #408, @AlexeyMyslin) — `ollama.Client(host=self.base_url)` instead of raw module assignment; remote Ollama servers now reachable.
- **spaCy runtime fallback** — `NERExtractor` now catches runtime initialization failures, not just missing-model errors.
- **CentralityCalculator crash** — `_build_adjacency()` handles both ContextGraph dataclass edges (`source_id`/`target_id`) and plain dicts.
- **`find_path` always used BFS** (PR #384) — algorithm query param now correctly dispatched to `dijkstra_shortest_path` or `bfs_shortest_path`.
- **Event loop blocked in `/api/enrich/links`** (PR #385) — `score_link` scoring loop wrapped in `asyncio.to_thread`.
- **Temp file leak in `export_graph`** (PR #384) — `try/finally` cleanup for all error paths.
- **`ChangeCategory` enum typo** (PR #367) — `"potenitally_breaking"` → `"potentially_breaking"`.
- **DecisionQuery/DecisionRecorder fallbacks** (PR #386) — `type()` guard instead of `isinstance()` for Mock safety; flat property storage in `_store_decision_node`; spurious `properties={}` kwarg removed; tz-aware/naive datetime mismatch resolved; `find_edges()` hoisted out of BFS loop (O(nodes×edges) → O(1) per call).
- **Snapshot schema** (PR #393) — silent restore failures when `nodes`/`edges` schema didn't match legacy `entities`/`relationships` expectations.
- **Context explainability** (@KaifAhmad1) — decision nodes now store full `scenario`/`reasoning` text; causal/precedent reconstruction returns enriched `Decision` objects; `PolicyEngine.get_affected_decisions()` consistent across Cypher and fallback branches.

### Security

- **CWE-312/359/532** — Removed `api_key` debug `print` blocks from `relation_extractor.py` and `triplet_extractor.py`.
- **CWE-20** — URL sanitization: `"url" in urls` replaced with `any(url == "url" for url in urls)`, eliminating substring match.
- **CI overpermissions** — `permissions: contents: read` added to `benchmark.yml` and `security.yml`.
- **SHACL path traversal** (PR #318) — replaced `len < 500 and "\n" not in s` heuristic with `os.path.exists()`.
- **SHACL inheritance mutation** (PR #318) — `_propagate_inheritance` uses `dataclasses.replace()` instead of appending parent `PropertyShape` objects by reference.
- **SPARQL injection** (PR #361) — `search_concepts`, `list_alignments`, `build_values_clause` fully hardened.

---

## [0.3.0] - 2026-03-10

### Added

- **Context Graph Feature Completeness** (@KaifAhmad1):
  - `ContextNode` / `ContextEdge` gain `valid_from` / `valid_until` with `is_active(at_time) -> bool`.
  - `ContextGraph.find_active_nodes(node_type, at_time)` — temporal node filtering.
  - `get_neighbors(min_weight)` — confidence-filtered BFS (default 0.0 passes all edges).
  - `link_graph()` / `navigate_to()` / `resolve_links(registry)` — cross-graph navigation with full save/load round-trip.
  - `graph_id` UUID field persisted to JSON.

### Fixed

- `is_active()` tz-aware/naive datetime normalization.
- `valid_from`/`valid_until` serialization in `add_nodes()`, `add_edges()`, `to_dict()`, `from_dict()`.
- Cross-graph link phantom-node prevention in `link_graph()`.
- `pipeline_builder.add_step()` return type annotation.
- `test_hybrid_search_performance` timing computation; threshold raised to < 5.0 s.
- **ProvenanceTracker** added to `semantica/kg/__init__.py` exports.
- Duplicate relation creation in `_parse_relation_result` — orphaned legacy block removed.
- `extraction_method` parameter added; typed path now correctly sets `"llm_typed"`.
- Cross-test cache pollution in `test_retry_logic.py` — `_result_cache.clear()` added to `setUp()`.
- 14 tests in `tests/context/test_cross_graph_navigation.py`; 85 real-world tests in `tests/test_030_realworld_comprehensive.py`.

---

## [0.3.0-beta] - 2026-03-07

### Added

- **Multi-Founder LLM Extraction** (PR #354, @KaifAhmad1):
  - `_parse_relation_result`: unmatched subjects/objects produce a synthetic `UNKNOWN` entity instead of being silently dropped.
  - `_match_pattern` rewritten: splits on `?var` placeholders, pre-bound variable resolution, repeated-variable backreferences.
- **TTL Export Aliases** (PR #355, @KaifAhmad1) — `format="ttl"/"nt"/"xml"/"rdf"/"json-ld"` resolve correctly before format validation; 8 tests in `tests/export/test_rdf_exporter.py`.
- **Incremental/Delta Processing** (PR #349, @ZohaibHassan16) — native delta computation between graph snapshots via SPARQL, delta-aware pipeline execution (`delta_mode`), snapshot retention with `prune_versions()`, significant performance improvements for near real-time pipelines.
- **Deduplication v2**:
  - **Candidate Generation v2** (PR #338, @ZohaibHassan16) — multi-key blocking, phonetic (Soundex) blocking, deterministic candidate budgeting; 63.6% faster (0.259 s → 0.094 s for 100 entities).
  - **Two-Stage Scoring Prefilter** (PR #339, @ZohaibHassan16) — type mismatch, length ratio, token overlap gates; 18–25% faster batch processing.
  - **Semantic Relationship Deduplication v2** (PR #340, @ZohaibHassan16) — predicate synonym mapping (`works_for` → `employed_by`), O(1) hash matching, weighted scoring (60% predicate + 40% object); 6.98x speedup (~83 ms vs ~579 ms).
  - **Migration Guide** (PR #344, @ZohaibHassan16) — comprehensive MIGRATION_V2.md; critical infinite recursion bug in `dedup_triplets()` fixed.
- **ArangoDB AQL Export** (PR #342, @tibisabau) — AQL INSERT generation, configurable collections, batch processing (default 1 000), `.aql` auto-detection, 17 tests.
- **Apache Parquet Export** (PR #343, @tibisabau) — columnar storage, configurable compression (snappy/gzip/brotli/zstd/lz4/none), explicit Arrow schemas, `.parquet` auto-detection, 25 tests.

### Fixed

- **Test Suite Fixes** (@KaifAhmad1):
  - Context: entity extraction gated on `use_hybrid_search=True`; `_extract_entities_from_query` uses `word[0].isupper()`; added `expand_context` BFS method; `hybrid_retrieval` and `multi_hop_context_assembly` corrected; vector result fallback to `metadata["content"]`.
  - KG: `calculate_pagerank` aliases; `community_detector._to_networkx` no longer silently loses edges; `_build_adjacency` handles both `"edges"` and `"relationships"` keys; 9 tracking methods added to `AlgorithmTrackerWithProvenance`.
  - Pipeline: retry loop honours `max_retries`; `FailureHandler.handle_failure()` added; `add_step` return type fixed; `validate` alias added; error message standardized.
  - Tests: emoji replaced with ASCII for Windows cp1252 compatibility.
- `NameError`: missing `Type` import in `utils/helpers.py`.

---

## [0.3.0-alpha] - 2026-02-19

### Added

- **Decision Tracking System** — complete lifecycle management (record → analyze → query → precedent → influence) with audit trails and provenance tracking.
- **Advanced KG Algorithms** — Node2Vec embeddings, centrality analysis, community detection for decision insights.
- **Enhanced Context Module** — unified `AgentContext` with granular feature flags for decision tracking, KG algorithms, and vector store features.
- **Vector Store Features** — hybrid search combining semantic, structural, and category similarity.
- **Policy Management** — versioning, compliance checking, and exception handling.
- **Context Engineering Enhancement** (PR #307, @KaifAhmad1) — full decision tracking, hybrid search, `PolicyException` model, `GraphStore` validation, explainable AI features, 9 critical bug fixes, 100% test coverage (9/9).
- **PgVector Store Support** (PR #303, @Sameer6305 @KaifAhmad1) — HNSW/IVFFlat indexing, JSONB metadata filtering, psycopg3/psycopg2 fallback, SQL injection protection via `psycopg_sql.SQL()`, 36+ tests.
- **Apache AGE Backend** (PR #311, @Sameer6305) — `AgeStore` with `GraphStore` API compatibility, SQL injection protection.
- **Improved Vector Store for Decision Tracking** (PR #293, @KaifAhmad1) — `DecisionEmbeddingPipeline`, `HybridSimilarityCalculator` (0.7 semantic + 0.3 structural), `DecisionContext`, `ContextRetriever` with multi-hop reasoning; 34+ tests.
- **Improved Graph Algorithms** (PR #292, @KaifAhmad1) — 30+ algorithms across 7 categories (Node2Vec, Dijkstra, A*, PageRank, Louvain, Leiden, etc.), unified provenance tracking with `GraphBuilderWithProvenance` / `AlgorithmTrackerWithProvenance`.
- **ResourceScheduler Deadlock Fix** (PRs #299 #301, @d4ndr4d3 @KaifAhmad1) — `threading.Lock` → `threading.RLock`; allocation validation; leak prevention on failure; 6 regression tests.
- **Dependabot & Security Automation** — bi-weekly security updates, automated Bandit/Safety/Semgrep scans, security-critical package grouping.

### Fixed

- Context Graphs decision tracking bugs (PR #315, @KaifAhmad1): empty/`None` decision ID, `None` metadata, causal chain depth logic, nonexistent node handling, `to_dict`/`from_dict` round-trip.
- `PolicyEngine` latest version selection; `AgentContext` fallback robustness and secure logging.
- Import issues in test suite (ProvenanceTracker location); causal analyzer `max_depth` bounds.

---

## [0.2.7] - 2026-02-09

### Added

- **Snowflake Connector** (PR #276, @Sameer6305) — multi-auth (password/OAuth/key-pair/SSO), table and query ingestion, SQL injection prevention, progress tracking, 24 tests. `pip install semantica[db-snowflake]`.
- **Apache Arrow Export** (PR #273, @Sameer6305) — explicit Arrow schemas, entity/relationship export, Pandas/DuckDB compatible, 20 tests.
- **Benchmark Suite** (PR #289, @ZohaibHassan16 @KaifAhmad1) — 137+ benchmarks across all 10 modules, Z-score statistical regression detection, GitHub Actions workflow. CLI: `python benchmarks/benchmark_runner.py`.

---

## [0.2.6] - 2026-02-03

### Added

- **W3C PROV-O Provenance Tracking** (Issues #254 #246, @KaifAhmad1):
  - Comprehensive provenance across all 17 Semantica modules; InMemory/SQLite backends; SHA-256 integrity.
  - FDA 21 CFR Part 11, SOX, HIPAA, TNFD compliance infrastructure.
  - 237 tests; opt-in (`provenance=False` by default).
- **Enhanced Change Management** (Issues #248 #243, @KaifAhmad1):
  - `TemporalVersionManager` and `OntologyVersionManager` with SQLite/in-memory backends; SHA-256 checksums; detailed diffs.
  - 104 tests; 17.6 ms for 10 k entities; 510+ ops/sec concurrent.
- **CSV Ingestion Enhancements** (PR #244, @saloni0318) — auto-detect encoding (chardet) and delimiter (csv.Sniffer); tolerant decoding; optional chunked reading.
- **Ingest Unit Tests** (Issues #239 #232, @Mohammed2372) — file, web, and feed ingestors; 998 lines of tests; 80–86% coverage.
- TextNormalizer comprehensive unit tests (PR #242, @ZohaibHassan16).

### Fixed

- **Temperature Compatibility** (Issues #256 #252, @F0rt1s @IGES-Institut) — `temperature=None` now omits parameter so APIs use model defaults; `_add_if_set` helper applied to all 5 providers; 10 tests.
- **JenaStore Empty Graph** (Issues #257 #258, @ZohaibHassan16) — `if self.graph is None:` replaces implicit falsy check in 5 methods.

---

## [0.2.5] - 2026-01-27

### Added

- **Pinecone Vector Store** (closes #219 #220) — serverless and pod-based indexes, namespace support, metadata filtering, unified `VectorStore` integration.
- **Configurable LLM Retry Logic** — `max_retries` parameter (default 3) in `NERExtractor`, `RelationExtractor`, `TripletExtractor`, and all `extract_*_llm` methods.
- **Bring Your Own Model (BYOM)** — custom HuggingFace models in all extractors; custom tokenizer support; runtime `model=` overrides config defaults.
- **Enhanced NER** — configurable aggregation strategies (simple/first/average/max); IOB/BILOU parsing for raw model outputs; confidence scoring.
- **Relation Extraction** — entity marker technique (`<subj>`/`<obj>` tags) for sequence classification models; structured output parsing.
- **Triplet Extraction** — Seq2Seq model support (REBEL) for direct structured triplet generation from text.

### Fixed

- LLM extraction: strict `max_retries` enforcement prevents infinite retry loops.
- Model parameter precedence: runtime arguments now correctly override config defaults in HuggingFace extractors.
- Circular imports in test suites.

---

## [0.2.4] - 2026-01-22

### Added

- **Ontology Ingestion Module** — `OntologyIngestor` for Turtle/RDF-XML/JSON-LD/N3 files; `ingest_ontology()` convenience function; recursive directory scanning; `OntologyData` dataclass; integrated into `ingest(source_type="ontology")`.

---

## [0.2.3] - 2026-01-20

### Added

- Amazon Neptune dev environment — CloudFormation template; `cfn-lint` in pre-commit.
- Vector Store high-performance ingestion — `VectorStore.add_documents()` with batching and parallel processing (`max_workers=6`); `VectorStore.embed_batch()` helper.
- LLM relation extraction tests (mocked and Groq integration).

### Changed

- Simplified relation extraction parameter interface; improved error handling and verbose logging.
- Standardized `VectorStore` concurrency defaults; implicit `max_workers=6` in examples.

### Fixed

- **LLM Relation Extraction Parsing** — normalized typed responses to consistent dict format before parsing; structured JSON fallback; extra kwargs removed from internals.
- **Pipeline Circular Import** (Issues #192 #193) — lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__`; `TYPE_CHECKING` guard.
- **JupyterLab Progress** (Issue #181) — `SEMANTICA_DISABLE_JUPYTER_PROGRESS` env var suppresses rich progress tables.

---

## [0.2.2] - 2026-01-15

### Added

- **Parallel Extraction Engine** — `concurrent.futures.ThreadPoolExecutor` across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`); `max_workers` parameter; thread-safe `ProgressTracker`.
- Semantic extract regression suite; real-use-case benchmark script.

### Changed

- **Gemini SDK Migration** — `google-genai` SDK with `google.generativeai` fallback.
- Pinned `opentelemetry-api`/`-sdk` to 1.37.0; updated `protobuf`/`grpcio` constraints.
- Entity filtering applied only to LLM prompt construction, not non-LLM flows.
- Raised global `optimization.max_workers` default to 8.

### Security

- **Credential sanitization** — hardcoded API keys removed from 8 notebooks; `ExtractionCache` excludes `api_key`/`token`/`password` from cache keys; cache key hashing upgraded MD5 → SHA-256.

### Performance

- ~1.89× speedup via parallel extraction (Groq `llama-3.3-70b-versatile`, standard datasets).
- Optimized entity matching: exact/substring/word-boundary fast paths before embedding similarity.

---

## [0.2.1] - 2026-01-12

### Fixed

- **LLM Output Stability** (Bug #176) — correct `max_tokens` propagation; automatic chunk-halving and retry on context/output limit errors.
- Removed hardcoded `max_length` constraints from `Entity`, `Relation`, `Triplet`.
- Orchestrator lazy property initialization and configuration normalization.
- `AssertionError` in orchestrator tests (mock alignment).
- Pinned `protobuf>=5.29.1,<7.0`, `grpcio>=1.71.2`; added `GitPython` and `chardet` to `pyproject.toml`.

### Changed

- Increased default `max_text_length` to 64 000 characters for all major providers.
- Standardized Groq defaults: `llama-3.3-70b-versatile`, 64 k context, native `max_tokens`/`max_completion_tokens`.

---

## [0.2.0] - 2026-01-10

### Added

- **Amazon Neptune Support** — `AmazonNeptuneStore` via Bolt/OpenCypher; `NeptuneAuthTokenManager` with AWS IAM SigV4 signing; retry/backoff. `pip install semantica[graph-amazon-neptune]`.
- **Docling Integration** — `DoclingParser` for PDF/DOCX/PPTX/XLSX/HTML/image parsing; OCR support; Markdown/HTML/JSON export.
- **Robust Extraction Fallbacks** — ML/LLM → Pattern → Last Resort chains across all extractors.
- **Provenance & Tracking** — `batch_index` and `document_id` metadata on all extracted items.
- **Semantic Extract** — auto-chunking for long text; `silent_fail` parameter; JSON parsing with 3-attempt exponential backoff.
- End-to-end KG pipeline integration tests; `TextEmbedder` model switching tests.

### Changed

- Removed internal dedup logic from extractors (deferred to `semantica/conflicts`).
- Standardized batch processing across all extractors using unified `extract`/`analyze`/`resolve` pattern.
- Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity).

### Fixed

- `NameError` in `extraction_validator.py` (missing `Union` import).
- Extractors returning empty lists for valid input when primary methods fail.
- Model switching bug in `TextEmbedder` (state not cleared on model switch). (Issue #160)
- `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer`. (Issue #159)
- Pinned `protobuf==4.25.3`, `grpcio==1.67.1`.
- `TripletExtractor.validate_triplets` shadowed by internal attribute.
- Incorrect `TextSplitter` import path.

---

## [0.1.1] - 2026-01-05

### Added

- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse`.
- Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed

- `DoclingParser` import/export across platforms (Windows, Linux, Google Colab).
- Error messaging when optional `docling` dependency is missing.
- Versioning inconsistencies across the framework.

---

## [0.1.0] - 2025-12-31

### Added

- Command-line interface (`semantica` CLI) with knowledge base building and info commands.
- FastAPI-based REST API server for remote access.
- Background worker component for scalable task processing.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed

- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core components.

---

## [0.0.5] - 2025-11-26

### Changed

- Configured Trusted Publishing for secure automated PyPI deployments.

---

## [0.0.4] - 2025-11-26

### Changed

- Fixed PyPI deployment issues from v0.0.3.

---

## [0.0.3] - 2025-11-25

### Added

- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership).
- Updated pull request template with clear guidelines.
- Community support documentation (`SUPPORT.md`).
- Funding and sponsorship configuration (`FUNDING.yml`).
- 10+ domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.).

### Changed

- Simplified CI/CD workflows — removed failing tests and strict linting.
- Combined release and PyPI publishing into single workflow.
- Simplified security scanning to weekly pip-audit only.

### Removed

- Redundant scripts folder (8 shell/PowerShell scripts).
- Unnecessary automation workflows (label-issues, mark-answered).
- Excessive issue templates.

---

## [0.0.2] - 2025-11-25

### Changed

- Updated README with streamlined content and better examples.
- Added more notebooks to cookbook.
- Improved documentation structure.

---

## [0.0.1] - 2024-01-XX

### Added

- Core framework architecture.
- Universal data ingestion (multiple file formats).
- Semantic intelligence engine (NER, relation extraction, event detection).
- Knowledge graph construction with entity resolution.
- 6-stage ontology generation pipeline.
- GraphRAG engine for hybrid retrieval.
- Multi-agent system infrastructure.
- Production-ready quality assurance modules.
- Comprehensive documentation with MkDocs.
- Cookbook with interactive tutorials.
- Multiple vector store backends (Weaviate, Qdrant, FAISS).
- Multiple graph database backends (Neo4j, NetworkX, RDFLib).
- Temporal knowledge graph support.
- Conflict detection and resolution; deduplication and entity merging.
- Schema template enforcement; seed data management.
- Multi-format export (RDF, JSON-LD, CSV, GraphML).
- Visualization tools; pipeline orchestration.
- Streaming support (Kafka, RabbitMQ, Kinesis).
- Context engineering for AI agents; reasoning and inference engine.

---

## Types of Changes

| Label | Meaning |
|-------|---------|
| **Added** | New features |
| **Changed** | Changes in existing functionality |
| **Deprecated** | Soon-to-be removed features |
| **Removed** | Removed features |
| **Fixed** | Bug fixes |
| **Security** | Vulnerability fixes |
| **Performance** | Performance improvements |

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).
