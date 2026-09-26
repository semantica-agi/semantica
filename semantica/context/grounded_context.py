"""Assemble grounded context from one consistent read view.

The assembler is the read-side consumer of the grounded context stack: it
captures exactly one provider view and one registry snapshot, validates every
retrieved candidate against them before ranking, and renders the surviving
blocks plus their citations into a frozen :class:`GroundedContext`. Nothing
is returned unless the view and the registry revision are still current when
assembly finishes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from semantica.utils.exceptions import ProcessingError, ValidationError

from ._context_dependencies import evaluate_artifact, evaluate_candidate
from .context_artifact_index import ContextArtifactIndex
from .context_retriever import ContextRetriever, RetrievedContext
from .grounded_context_types import (
    ArtifactRegistrySnapshot,
    ContextBlock,
    ContextCitation,
    ContextReadView,
    Exclusion,
    GroundedArtifact,
    GroundedContext,
)
from .truth_snapshot_provider import TruthSnapshotProvider

__all__ = ["GroundedContextAssembler"]


class GroundedContextAssembler:
    """Build a grounded context from one capture of provider and registry."""

    def __init__(self, retriever, *, provider, artifacts):
        if not isinstance(retriever, ContextRetriever):
            raise ValidationError(
                "retriever must be a ContextRetriever instance",
                validation_context={"retriever_type": type(retriever).__name__},
            )
        if not isinstance(provider, TruthSnapshotProvider):
            raise ValidationError(
                "provider must be a TruthSnapshotProvider instance",
                validation_context={"provider_type": type(provider).__name__},
            )
        if not isinstance(artifacts, ContextArtifactIndex):
            raise ValidationError(
                "artifacts must be a ContextArtifactIndex instance",
                validation_context={"artifacts_type": type(artifacts).__name__},
            )
        self.retriever = retriever
        self.provider = provider
        self.artifacts = artifacts

    def assemble(
        self,
        query: str,
        *,
        max_results: int = 5,
        max_context_chars: int = 8000,
        valid_at: Any = None,
        known_at: Any = None,
    ) -> GroundedContext:
        """
        Assemble one grounded context for ``query`` from a single read view.

        Args:
            query: Search query
            max_results: Maximum number of body blocks
            max_context_chars: Budget for the rendered text; oversized
                blocks are skipped, never truncated
            valid_at: Optional temporal coordinate forwarded to the provider
            known_at: Optional temporal coordinate forwarded to the provider

        Returns:
            Frozen GroundedContext describing this one read view

        Raises:
            ValidationError: Invalid arguments
            ProcessingError: The view or registry went stale mid-assembly
        """
        if not isinstance(query, str) or not query.strip():
            raise ValidationError(
                "query must be a non-empty string",
                validation_context={"method": "GroundedContextAssembler.assemble"},
            )
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or max_results < 1
        ):
            raise ValidationError(
                "max_results must be a positive integer",
                validation_context={"method": "GroundedContextAssembler.assemble"},
            )
        if (
            isinstance(max_context_chars, bool)
            or not isinstance(max_context_chars, int)
            or max_context_chars < 0
        ):
            raise ValidationError(
                "max_context_chars must be a non-negative integer",
                validation_context={"method": "GroundedContextAssembler.assemble"},
            )

        view = self.provider.capture(valid_at=valid_at, known_at=known_at)
        registry = self.artifacts.snapshot()
        if registry.namespace != view.stamp.namespace:
            raise ValidationError(
                "artifact registry namespace must match provider namespace"
            )
        exclusions: list[Exclusion] = []
        candidate_ids: dict[int, str] = {}

        def candidate_filter(candidates):
            kept = []
            for position, candidate in enumerate(candidates, start=1):
                object_id, reason = self._candidate_reason(
                    candidate, registry=registry, view=view, position=position
                )
                if reason is None:
                    # Rank and merge mutate scores and metadata in place;
                    # never let those writes reach the external stores.
                    owned = deepcopy(candidate)
                    candidate_ids[id(owned)] = object_id
                    kept.append(owned)
                else:
                    exclusions.append(Exclusion(object_id=object_id, reason=reason))
            return kept

        ranked = self.retriever._retrieve_local(
            query,
            max_results=max_results,
            candidate_filter=candidate_filter,
            merge_duplicates=False,
            limit_results=False,
        )

        admitted: list[GroundedArtifact | RetrievedContext] = []
        for candidate in ranked:
            if len(admitted) >= max_results:
                break
            artifact_id = candidate.metadata.get("grounded_artifact_id")
            item = registry.get(artifact_id) if artifact_id is not None else candidate
            admitted.append(item)
            blocks, citations, text = self._render(admitted, registry)
            if len(text) <= max_context_chars:
                continue
            admitted.pop()
            exclusions.append(
                Exclusion(
                    object_id=candidate_ids[id(candidate)], reason="budget_exceeded"
                )
            )
        blocks, citations, text = self._render(admitted, registry)

        # Freshness: even an empty or over-budget result must confirm that
        # the read view it describes is still the current one.
        self.provider.assert_current(view)
        if self.artifacts.revision != registry.revision:
            raise ProcessingError(
                "artifact registry changed during assembly: revision "
                f"{registry.revision} no longer matches "
                f"{self.artifacts.revision}"
            )

        return GroundedContext(
            text=text,
            blocks=blocks,
            citations=citations,
            stamp=view.stamp,
            artifact_revision=registry.revision,
            exclusions=tuple(exclusions),
        )

    @staticmethod
    def _candidate_reason(
        candidate: Any,
        *,
        registry: ArtifactRegistrySnapshot,
        view: ContextReadView,
        position: int,
    ) -> tuple[str, str | None]:
        """
        Return ``(object_id, reason)`` for one retrieved candidate.

        ``reason`` is ``None`` when the candidate is grounded on the view.
        The exclusion id is the effective ``grounded_artifact_id`` when the
        row carries one, otherwise the candidate's position in the merged
        candidate stream (``candidate:1``, ``candidate:2``, ...).
        """

        fallback = f"candidate:{position}"
        metadata = getattr(candidate, "metadata", None)
        if not isinstance(metadata, dict):
            return fallback, "missing_annotation"
        if "grounded_artifact_id" not in metadata:
            return fallback, evaluate_candidate(candidate, view=view)
        artifact_id = metadata["grounded_artifact_id"]
        if (
            not isinstance(artifact_id, str)
            or not artifact_id
            or artifact_id.strip() != artifact_id
        ):
            return fallback, "invalid_annotation"
        artifact = registry.get(artifact_id)
        if artifact is None:
            return artifact_id, "unknown_artifact"
        if artifact.kind == "citation":
            # Citations are footnotes; they never become body blocks.
            return artifact_id, "invalid_annotation"
        reason = evaluate_candidate(candidate, view=view)
        if reason is not None:
            return artifact_id, reason
        if not isinstance(candidate, RetrievedContext):
            return fallback, "invalid_annotation"
        if candidate.content != artifact.content:
            return artifact_id, "content_mismatch"
        reason = evaluate_artifact(artifact_id, registry=registry, view=view)
        if reason is not None:
            return artifact_id, reason
        return artifact_id, None

    @staticmethod
    def _render(
        admitted: list[GroundedArtifact | RetrievedContext],
        registry: ArtifactRegistrySnapshot,
    ) -> tuple[tuple[ContextBlock, ...], tuple[ContextCitation, ...], str]:
        """
        Render structured blocks/citations first, then the final text.

        Both the trial budget checks and the returned context call this one
        pure function, so a block is admitted only if its fully rendered
        form (citation suffixes and Sources footnotes included) fits the
        budget.
        """

        labels: dict[str, str] = {}
        ordered_citation_ids: list[str] = []
        blocks: list[ContextBlock] = []
        for index, artifact in enumerate(admitted, start=1):
            block_citation_ids: list[str] = []
            is_artifact = isinstance(artifact, GroundedArtifact)
            citation_ids = artifact.citation_ids if is_artifact else ()
            for cited_id in citation_ids:
                if cited_id not in labels:
                    labels[cited_id] = f"c{len(labels) + 1}"
                    ordered_citation_ids.append(cited_id)
                block_citation_ids.append(cited_id)
            blocks.append(
                ContextBlock(
                    block_id=f"b{index}",
                    content=artifact.content,
                    source=artifact.artifact_id if is_artifact else artifact.source,
                    citation_ids=tuple(block_citation_ids),
                )
            )

        citations: list[ContextCitation] = []
        for cited_id in ordered_citation_ids:
            cited = registry.get(cited_id)
            citations.append(
                ContextCitation(
                    label=labels[cited_id],
                    artifact_id=cited_id,
                    content=cited.content,
                    support_ids=tuple(sorted(cited.dependencies.required_support_ids)),
                )
            )

        parts = []
        for block in blocks:
            suffix = ""
            if block.citation_ids:
                suffix = (
                    " (sources: "
                    + ", ".join(
                        "[" + labels[artifact_id] + "]"
                        for artifact_id in block.citation_ids
                    )
                    + ")"
                )
            parts.append("[" + block.block_id + "] " + block.content + suffix)
        text = "\n\n".join(parts)
        if citations:
            text += "\n\nSources:\n" + "\n".join(
                "[" + citation.label + "] " + citation.content for citation in citations
            )
        return tuple(blocks), tuple(citations), text
