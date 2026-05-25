"""
Explorer-local in-memory node search index.
"""

from __future__ import annotations

import bisect
import heapq
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WHITESPACE_RE = re.compile(r"\s+")
_CURATED_ALIAS_KEYS = (
    "label",
    "name",
    "title",
    "pref_label",
    "preferred_label",
    "prefLabel",
    "aliases",
    "alias",
    "synonyms",
    "synonym",
    "symbol",
    "display_name",
    "displayName",
    "text",
    "content",
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    return _WHITESPACE_RE.sub(" ", text)


def _tokenize(text: str) -> Tuple[str, ...]:
    if not text:
        return ()
    return tuple(dict.fromkeys(_TOKEN_RE.findall(text)))


def _collect_text_fragments(value: Any, fragments: List[str], *, limit: int = 64) -> None:
    if value is None or len(fragments) >= limit:
        return
    if isinstance(value, dict):
        for nested in value.values():
            _collect_text_fragments(nested, fragments, limit=limit)
            if len(fragments) >= limit:
                return
        return
    if isinstance(value, (list, tuple, set)):
        for nested in value:
            _collect_text_fragments(nested, fragments, limit=limit)
            if len(fragments) >= limit:
                return
        return

    normalized = _normalize_text(value)
    if normalized:
        fragments.append(normalized)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class IndexedNodeDocument:
    node_id: str
    normalized_id: str
    node_type: str
    exact_terms: frozenset[str]
    tokens: frozenset[str]
    primary_text: str
    secondary_text: str
    confidence: Optional[float]
    tags: Tuple[str, ...]


class GraphSearchIndex:
    def __init__(
        self,
        *,
        cache_size: int = 128,
        prefix_min_length: int = 2,
        prefix_max_length: int = 12,
        secondary_scan_limit: int = 12000,
    ) -> None:
        self.cache_size = cache_size
        self.prefix_min_length = prefix_min_length
        self.prefix_max_length = prefix_max_length
        self.secondary_scan_limit = secondary_scan_limit
        self._documents: Dict[str, IndexedNodeDocument] = {}
        self._exact_index: DefaultDict[str, set[str]] = defaultdict(set)
        self._token_index: DefaultDict[str, set[str]] = defaultdict(set)
        self._prefix_index: DefaultDict[str, set[str]] = defaultdict(set)
        self._ordered_node_ids: List[str] = []
        self._cache: OrderedDict[Tuple[Any, ...], List[Tuple[str, float]]] = OrderedDict()

    def rebuild(self, nodes: Iterable[Dict[str, Any]]) -> None:
        self._documents.clear()
        self._exact_index.clear()
        self._token_index.clear()
        self._prefix_index.clear()
        self._ordered_node_ids = []
        self.clear_cache()

        for node in nodes:
            self.upsert(node, clear_cache=False)

        self._ordered_node_ids.sort()

    def clear_cache(self) -> None:
        self._cache.clear()

    def remove(self, node_id: str, *, clear_cache: bool = True) -> None:
        existing = self._documents.pop(node_id, None)
        if existing is None:
            return

        for term in existing.exact_terms:
            bucket = self._exact_index.get(term)
            if bucket is None:
                continue
            bucket.discard(node_id)
            if not bucket:
                self._exact_index.pop(term, None)

        for token in existing.tokens:
            bucket = self._token_index.get(token)
            if bucket is None:
                continue
            bucket.discard(node_id)
            if not bucket:
                self._token_index.pop(token, None)

            for length in range(self.prefix_min_length, min(len(token), self.prefix_max_length) + 1):
                prefix = token[:length]
                prefix_bucket = self._prefix_index.get(prefix)
                if prefix_bucket is None:
                    continue
                prefix_bucket.discard(node_id)
                if not prefix_bucket:
                    self._prefix_index.pop(prefix, None)

        pos = bisect.bisect_left(self._ordered_node_ids, node_id)
        if pos < len(self._ordered_node_ids) and self._ordered_node_ids[pos] == node_id:
            self._ordered_node_ids.pop(pos)

        if clear_cache:
            self.clear_cache()

    def upsert(self, node: Dict[str, Any], *, clear_cache: bool = True) -> None:
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            return

        self.remove(node_id, clear_cache=False)
        document = self._build_document(node)
        self._documents[node_id] = document

        for term in document.exact_terms:
            self._exact_index[term].add(node_id)

        for token in document.tokens:
            self._token_index[token].add(node_id)
            for length in range(self.prefix_min_length, min(len(token), self.prefix_max_length) + 1):
                self._prefix_index[token[:length]].add(node_id)

        bisect.insort(self._ordered_node_ids, node_id)

        if clear_cache:
            self.clear_cache()

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[Tuple[str, float]], Dict[str, Any]]:
        normalized_query = _normalize_text(query)
        filters = filters or {}
        diagnostics: Dict[str, Any] = {
            "cache_hit": False,
            "path": "empty",
            "candidates": 0,
        }
        if not normalized_query:
            return [], diagnostics

        cache_key = self._cache_key(normalized_query, limit, filters)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            diagnostics.update({"cache_hit": True, "path": "cache", "candidates": len(cached)})
            return list(cached), diagnostics

        query_tokens = _tokenize(normalized_query)
        exact_ids = set(self._exact_index.get(normalized_query, set()))
        token_sets: List[set[str]] = []
        prefix_sets: List[set[str]] = []
        for token in query_tokens:
            exact_token_ids = set(self._token_index.get(token, set()))
            prefix_ids = set(self._prefix_index.get(token, set())) if len(token) >= self.prefix_min_length else set()
            if exact_token_ids:
                token_sets.append(exact_token_ids)
            if prefix_ids:
                prefix_sets.append(prefix_ids)

        candidate_ids: set[str] = set(exact_ids)
        if token_sets:
            intersected = set.intersection(*token_sets)
            candidate_ids.update(intersected if intersected else set().union(*token_sets))
        if prefix_sets:
            candidate_ids.update(set().union(*prefix_sets))

        diagnostics["path"] = "index"

        if not candidate_ids:
            diagnostics["path"] = "secondary_scan"
            candidate_ids = self._secondary_scan(normalized_query, limit)

        diagnostics["candidates"] = len(candidate_ids)

        scored: List[Tuple[float, int, int, str]] = []
        for node_id in candidate_ids:
            document = self._documents.get(node_id)
            if document is None or not self._passes_filters(document, filters):
                continue
            score = self._score_document(document, normalized_query, query_tokens)
            if score <= 0:
                continue
            token_hits = sum(1 for token in query_tokens if token in document.tokens)
            exactness = 1 if normalized_query == document.normalized_id or normalized_query in document.exact_terms else 0
            scored.append((score, exactness, token_hits, node_id))

        top_matches = heapq.nlargest(limit, scored, key=lambda item: (item[0], item[1], item[2], item[3]))
        results = [(node_id, round(score, 4)) for score, _, _, node_id in top_matches]
        self._store_cache(cache_key, results)
        return results, diagnostics

    def _secondary_scan(self, normalized_query: str, limit: int) -> set[str]:
        matches: set[str] = set()
        max_hits = max(limit * 20, 200)
        scanned = 0
        for node_id in self._ordered_node_ids:
            if scanned >= self.secondary_scan_limit or len(matches) >= max_hits:
                break
            scanned += 1
            document = self._documents.get(node_id)
            if document is None:
                continue
            if normalized_query in document.primary_text or normalized_query in document.secondary_text:
                matches.add(node_id)
        return matches

    def _score_document(
        self,
        document: IndexedNodeDocument,
        normalized_query: str,
        query_tokens: Tuple[str, ...],
    ) -> float:
        score = 0.0
        if normalized_query == document.normalized_id:
            score = max(score, 140.0)
        elif normalized_query in document.exact_terms:
            score = max(score, 120.0)

        if normalized_query and normalized_query in document.primary_text:
            score = max(score, 78.0 + min(len(normalized_query), 24) / 10.0)
        elif normalized_query and normalized_query in document.secondary_text:
            score = max(score, 26.0 + min(len(normalized_query), 24) / 20.0)

        token_hits = 0
        prefix_hits = 0
        for token in query_tokens:
            if token in document.tokens:
                token_hits += 1
            elif len(token) >= self.prefix_min_length and any(candidate.startswith(token) for candidate in document.tokens):
                prefix_hits += 1

        score += token_hits * 18.0
        score += prefix_hits * 10.0

        if len(query_tokens) > 1 and token_hits:
            score += token_hits * 4.0

        return score

    def _passes_filters(self, document: IndexedNodeDocument, filters: Dict[str, Any]) -> bool:
        filter_type = filters.get("type") or filters.get("node_type")
        if filter_type and document.node_type != str(filter_type):
            return False

        min_confidence = _coerce_float(filters.get("min_confidence"))
        if min_confidence is not None:
            if document.confidence is None or document.confidence < min_confidence:
                return False

        tags_filter = filters.get("tags")
        if tags_filter:
            if isinstance(tags_filter, str):
                required_tags = {_normalize_text(tags_filter)}
            else:
                required_tags = {
                    normalized
                    for normalized in (_normalize_text(tag) for tag in tags_filter)
                    if normalized
                }
            if required_tags and not required_tags.issubset(set(document.tags)):
                return False

        return True

    def _cache_key(
        self,
        normalized_query: str,
        limit: int,
        filters: Dict[str, Any],
    ) -> Tuple[Any, ...]:
        serialized_filters: List[Tuple[str, Any]] = []
        for key in sorted(filters.keys()):
            value = filters[key]
            if isinstance(value, (list, tuple, set)):
                serialized_filters.append((key, tuple(sorted(str(item) for item in value))))
            else:
                serialized_filters.append((key, str(value)))
        return normalized_query, limit, tuple(serialized_filters)

    def _store_cache(self, cache_key: Tuple[Any, ...], results: List[Tuple[str, float]]) -> None:
        self._cache[cache_key] = list(results)
        self._cache.move_to_end(cache_key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def _build_document(self, node: Dict[str, Any]) -> IndexedNodeDocument:
        node_id = str(node.get("id", "")).strip()
        node_type = str(node.get("type", "entity"))
        properties = dict(node.get("properties", {}) or {})

        primary_terms: List[str] = []
        for candidate in (node_id, node.get("content", "")):
            normalized = _normalize_text(candidate)
            if normalized:
                primary_terms.append(normalized)

        for alias_key in _CURATED_ALIAS_KEYS:
            _collect_text_fragments(properties.get(alias_key), primary_terms, limit=32)

        deduped_primary_terms = tuple(dict.fromkeys(term for term in primary_terms if term))
        primary_text = " ".join(deduped_primary_terms)
        tokens = frozenset(_tokenize(primary_text))

        secondary_fragments: List[str] = []
        for key, value in properties.items():
            if key in _CURATED_ALIAS_KEYS or key in {"content", "valid_from", "valid_until"}:
                continue
            _collect_text_fragments(value, secondary_fragments, limit=48)
            if len(secondary_fragments) >= 48:
                break

        secondary_text = " ".join(dict.fromkeys(fragment for fragment in secondary_fragments if fragment))
        confidence = _coerce_float(properties.get("confidence"))

        raw_tags = properties.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        tags = tuple(
            dict.fromkeys(
                normalized for normalized in (_normalize_text(tag) for tag in raw_tags) if normalized
            )
        )

        return IndexedNodeDocument(
            node_id=node_id,
            normalized_id=_normalize_text(node_id),
            node_type=node_type,
            exact_terms=frozenset(deduped_primary_terms),
            tokens=tokens,
            primary_text=primary_text,
            secondary_text=secondary_text,
            confidence=confidence,
            tags=tags,
        )
