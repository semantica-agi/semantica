"""TypeSafe Jev decision provider.

This module wraps TypeSafe's System One API as a decision-only provider.  Jev
does not generate free text, so :class:`Jev` and :class:`AsyncJev` deliberately
do not expose the ``generate`` methods implemented by chat-LLM providers.

The optional ``typesafe-sdk`` dependency is guarded so that
``import semantica.llms`` keeps working when the SDK is not installed; a clear
error is raised only when a caller attempts a Jev request without the optional
dependency.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Union

from ..utils.exceptions import ProcessingError
from ..utils.helpers import safe_import

_typesafe_sdk, TYPESAFE_AVAILABLE = safe_import("typesafe_sdk")

if TYPESAFE_AVAILABLE:
    AsyncTypeSafeClient = _typesafe_sdk.AsyncTypeSafeClient
    Choice = _typesafe_sdk.Choice
    Noul = _typesafe_sdk.Noul
    Score = _typesafe_sdk.Score
    TypeSafeClient = _typesafe_sdk.TypeSafeClient
else:  # pragma: no cover - assignments are exercised through availability tests
    AsyncTypeSafeClient = None
    Choice = None
    Noul = None
    Score = None
    TypeSafeClient = None


JevDecisionKind = Literal["choice", "noul", "score"]
JevDecisionValue = Union[str, bool, float]
JevProbabilityKey = Union[str, int]

_DEPENDENCY_ERROR = (
    "TypeSafe Jev provider is unavailable because typesafe-sdk is not installed. "
    'Install it with: pip install "semantica[llm-typesafe]"'
)
_CREDENTIAL_ERROR = (
    "TypeSafe Jev provider is unavailable because no API key is configured. "
    "Set TYPESAFE_API_KEY or pass api_key."
)


@dataclass(frozen=True)
class JevDecisionResult:
    """Normalized result from a Jev decision.

    Attributes:
        kind: Decision primitive used: ``choice``, ``noul``, or ``score``.
        value: Selected label, derived boolean, or expected numeric score.
        probability: Selected-label probability for Choice, raw yes-probability
            for Noul, and ``None`` for Score (an expected score has no single
            corresponding probability).
        confidence: Routing certainty in the range 0..1.  Choice and Score use
            the SDK-provided confidence.  Noul derives certainty as
            ``abs(2 * probability - 1)`` while preserving its raw probability.
        probabilities: Full probability distribution returned for Choice or
            Score.  Noul returns a single yes-probability, so this is empty.
        model: Concrete model reported by TypeSafe, which may differ from the
            requested alias.
        request_id: TypeSafe request identifier when supplied by the response.
        usage: Token usage reported by TypeSafe.
        legend: Score rubric keyed by numeric level; empty for other kinds.
    """

    kind: JevDecisionKind
    value: JevDecisionValue
    probability: Optional[float]
    confidence: float
    probabilities: Dict[JevProbabilityKey, float]
    model: str
    request_id: Optional[str]
    usage: Dict[str, Any]
    legend: Dict[int, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible copy suitable for decision provenance."""

        return {
            "kind": self.kind,
            "value": self.value,
            "probability": self.probability,
            "confidence": self.confidence,
            "probabilities": dict(self.probabilities),
            "model": self.model,
            "request_id": self.request_id,
            "usage": dict(self.usage),
            "legend": dict(self.legend),
        }


class _JevBase:
    """Configuration and response normalization shared by sync and async Jev."""

    def __init__(
        self,
        model: str = "jev-latest",
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        **client_options: Any,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")

        self.model = model
        self.api_key = api_key
        self._client = client
        self._client_options = dict(client_options)
        self._owns_client = False

    def is_available(self) -> bool:
        """Return whether an injected client or configured SDK is available.

        This is a local check for the SDK and API key.  It does not validate the
        credential or perform a network request.
        """

        return self._client is not None or (
            TYPESAFE_AVAILABLE and self._has_configured_api_key()
        )

    def _has_configured_api_key(self) -> bool:
        """Return whether the effective API key contains non-whitespace text."""

        api_key = (
            self.api_key
            if self.api_key is not None
            else os.environ.get("TYPESAFE_API_KEY")
        )
        return isinstance(api_key, str) and bool(api_key.strip())

    @staticmethod
    def _normalize_choice_criteria(
        choices: Union[Sequence[str], Mapping[str, Any]],
    ) -> Dict[str, Any]:
        if isinstance(choices, Mapping):
            criteria = dict(choices)
        elif isinstance(choices, Sequence) and not isinstance(
            choices, (str, bytes, bytearray)
        ):
            labels = list(choices)
            if any(not isinstance(label, str) or not label.strip() for label in labels):
                raise ValueError("choice labels must be non-empty strings")
            if len(set(labels)) != len(labels):
                raise ValueError("choice labels must be unique")
            criteria = {label: None for label in labels}
        else:
            raise ValueError("choices must be a mapping or a sequence of strings")

        if not criteria:
            raise ValueError("choice decisions require at least one choice")
        if any(not isinstance(label, str) or not label.strip() for label in criteria):
            raise ValueError("choice labels must be non-empty strings")
        return criteria

    @classmethod
    def _build_question(
        cls,
        question: Any,
        kind: str,
        choices: Optional[Union[Sequence[str], Mapping[str, Any]]],
        criteria: Optional[Any],
    ) -> Any:
        normalized_kind = kind.lower() if isinstance(kind, str) else kind
        if normalized_kind not in {"choice", "noul", "score"}:
            raise ValueError("kind must be one of: choice, noul, score")

        if normalized_kind == "choice":
            if choices is not None and criteria is not None:
                raise ValueError("pass either choices or criteria for Choice, not both")
            choice_input = choices if choices is not None else criteria
            if choice_input is None:
                raise ValueError("choice decisions require choices or criteria")
            choice_criteria = cls._normalize_choice_criteria(choice_input)
            if TYPESAFE_AVAILABLE:
                return Choice(instructions=question, criteria=choice_criteria)
            return {
                "type": "choice",
                "instructions": question,
                "criteria": choice_criteria,
            }

        if choices is not None:
            raise ValueError("choices is only valid for Choice decisions")

        if normalized_kind == "noul":
            if criteria is not None:
                if not isinstance(criteria, Mapping):
                    raise ValueError("Noul criteria must be a mapping")
                unknown = set(criteria) - {"true", "false"}
                if unknown:
                    names = ", ".join(sorted(str(name) for name in unknown))
                    raise ValueError(
                        "Noul criteria only supports 'true' and 'false'; "
                        f"received: {names}"
                    )
                criteria = dict(criteria)
            if TYPESAFE_AVAILABLE:
                return Noul(instructions=question, criteria=criteria)
            payload = {"type": "noul", "instructions": question}
            if criteria is not None:
                payload["criteria"] = criteria
            return payload

        if criteria is None:
            raise ValueError("score decisions require ordered criteria")
        if not isinstance(criteria, Sequence) or isinstance(
            criteria, (str, bytes, bytearray)
        ):
            raise ValueError("Score criteria must be an ordered sequence")
        score_criteria = list(criteria)
        if not score_criteria:
            raise ValueError("score decisions require at least one criterion")
        if TYPESAFE_AVAILABLE:
            return Score(instructions=question, criteria=score_criteria)
        return {
            "type": "score",
            "instructions": question,
            "criteria": score_criteria,
        }

    @staticmethod
    def _read_field(value: Any, field: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(field, default)
        return getattr(value, field, default)

    @classmethod
    def _normalize_usage(cls, usage: Any) -> Dict[str, Any]:
        if usage is None:
            return {}
        if isinstance(usage, Mapping):
            return dict(usage)
        model_dump = getattr(usage, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, Mapping):
                return dict(dumped)
        return {
            field: getattr(usage, field)
            for field in ("input_tokens", "output_tokens")
            if hasattr(usage, field)
        }

    @staticmethod
    def _validate_probability(value: Any, field: str) -> float:
        try:
            probability = float(value)
        except (TypeError, ValueError) as exc:
            raise ProcessingError(
                f"TypeSafe returned a non-numeric {field}: {value!r}"
            ) from exc
        if not 0.0 <= probability <= 1.0:
            raise ProcessingError(
                f"TypeSafe returned {field} outside the range 0..1: {probability}"
            )
        return probability

    @classmethod
    def _normalize_response(cls, response: Any) -> JevDecisionResult:
        answers = cls._read_field(response, "answers")
        if not isinstance(answers, Mapping) or "decision" not in answers:
            raise ProcessingError(
                "TypeSafe response did not contain the expected 'decision' answer"
            )

        answer = answers["decision"]
        kind = cls._read_field(answer, "type")
        probabilities: Dict[JevProbabilityKey, float] = {}
        legend: Dict[int, Any] = {}

        if kind == "choice":
            value = cls._read_field(answer, "choice")
            if not isinstance(value, str) or not value:
                raise ProcessingError("TypeSafe returned an invalid Choice value")
            confidence = cls._validate_probability(
                cls._read_field(answer, "confidence"), "Choice confidence"
            )
            raw_probabilities = cls._read_field(answer, "probabilities")
            if not isinstance(raw_probabilities, Mapping):
                raise ProcessingError(
                    "TypeSafe returned invalid Choice probabilities; "
                    "expected a mapping"
                )
            probabilities = {
                str(label): cls._validate_probability(
                    raw_probability, f"Choice probability for {label!r}"
                )
                for label, raw_probability in raw_probabilities.items()
            }
            probability = probabilities.get(value, confidence)

        elif kind == "noul":
            probability = cls._validate_probability(
                cls._read_field(answer, "noul"), "Noul probability"
            )
            value = probability >= 0.5
            confidence = abs(2.0 * probability - 1.0)

        elif kind == "score":
            raw_value = cls._read_field(answer, "score")
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    f"TypeSafe returned a non-numeric Score value: {raw_value!r}"
                ) from exc
            confidence = cls._validate_probability(
                cls._read_field(answer, "confidence"), "Score confidence"
            )
            probability = None
            raw_probabilities = cls._read_field(answer, "probabilities")
            if not isinstance(raw_probabilities, Mapping):
                raise ProcessingError(
                    "TypeSafe returned invalid Score probabilities; "
                    "expected a mapping"
                )
            try:
                probabilities = {
                    int(level): cls._validate_probability(
                        raw_probability, f"Score probability for level {level!r}"
                    )
                    for level, raw_probability in raw_probabilities.items()
                }
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "TypeSafe returned a non-integer Score probability level"
                ) from exc
            raw_legend = cls._read_field(answer, "legend")
            if not isinstance(raw_legend, Mapping):
                raise ProcessingError(
                    "TypeSafe returned an invalid Score legend; expected a mapping"
                )
            try:
                legend = {
                    int(level): description for level, description in raw_legend.items()
                }
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "TypeSafe returned a non-integer Score legend level"
                ) from exc

        else:
            raise ProcessingError(
                f"TypeSafe returned an unsupported decision answer type: {kind!r}"
            )

        request_id: Optional[str]
        try:
            raw_request_id = cls._read_field(response, "request_id")
        except Exception:  # SDK property raises when the header was not returned.
            raw_request_id = None
        request_id = str(raw_request_id) if raw_request_id else None

        raw_model = cls._read_field(response, "model")
        if not isinstance(raw_model, str) or not raw_model:
            raise ProcessingError("TypeSafe response did not include a model name")

        return JevDecisionResult(
            kind=kind,
            value=value,
            probability=probability,
            confidence=confidence,
            probabilities=probabilities,
            model=raw_model,
            request_id=request_id,
            usage=cls._normalize_usage(cls._read_field(response, "usage")),
            legend=legend,
        )

    @classmethod
    def _validate_response_contract(
        cls, result: JevDecisionResult, question: Any
    ) -> None:
        """Ensure a provider response stays inside the submitted decision domain."""

        requested_kind = cls._read_field(question, "type")
        if result.kind != requested_kind:
            raise ProcessingError(
                "TypeSafe returned a "
                f"{result.kind!r} answer for a {requested_kind!r} request"
            )

        criteria = cls._read_field(question, "criteria")
        if requested_kind == "choice":
            if not isinstance(criteria, Mapping):
                raise ProcessingError(
                    "TypeSafe Choice request did not contain valid criteria"
                )
            allowed_labels = set(criteria)
            if result.value not in allowed_labels:
                raise ProcessingError(
                    "TypeSafe returned a Choice value outside the requested criteria: "
                    f"{result.value!r}"
                )
            unexpected_labels = set(result.probabilities) - allowed_labels
            if unexpected_labels:
                labels = ", ".join(repr(label) for label in sorted(unexpected_labels))
                raise ProcessingError(
                    "TypeSafe returned Choice probabilities outside the requested "
                    f"criteria: {labels}"
                )
            missing_labels = allowed_labels - set(result.probabilities)
            if missing_labels:
                labels = ", ".join(repr(label) for label in sorted(missing_labels))
                raise ProcessingError(
                    "TypeSafe omitted Choice probabilities for requested criteria: "
                    f"{labels}"
                )

        elif requested_kind == "score":
            if not isinstance(criteria, Sequence) or isinstance(
                criteria, (str, bytes, bytearray)
            ):
                raise ProcessingError(
                    "TypeSafe Score request did not contain valid criteria"
                )
            allowed_levels = set(range(len(criteria)))
            score_value = float(result.value)
            if not allowed_levels or not 0.0 <= score_value <= max(allowed_levels):
                raise ProcessingError(
                    "TypeSafe returned a Score value outside the requested criteria: "
                    f"{result.value!r}"
                )
            unexpected_levels = (
                set(result.probabilities) | set(result.legend)
            ) - allowed_levels
            if unexpected_levels:
                levels = ", ".join(str(level) for level in sorted(unexpected_levels))
                raise ProcessingError(
                    "TypeSafe returned Score levels outside the requested criteria: "
                    f"{levels}"
                )
            missing_probability_levels = allowed_levels - set(result.probabilities)
            if missing_probability_levels:
                levels = ", ".join(
                    str(level) for level in sorted(missing_probability_levels)
                )
                raise ProcessingError(
                    "TypeSafe omitted Score probabilities for requested levels: "
                    f"{levels}"
                )
            missing_legend_levels = allowed_levels - set(result.legend)
            if missing_legend_levels:
                levels = ", ".join(
                    str(level) for level in sorted(missing_legend_levels)
                )
                raise ProcessingError(
                    "TypeSafe omitted Score legend entries for requested levels: "
                    f"{levels}"
                )
            mismatched_legend_levels = [
                level
                for level, expected_description in enumerate(criteria)
                if result.legend[level] != expected_description
            ]
            if mismatched_legend_levels:
                levels = ", ".join(str(level) for level in mismatched_legend_levels)
                raise ProcessingError(
                    "TypeSafe returned Score legend entries that did not match "
                    f"the requested criteria at levels: {levels}"
                )

    def _require_available(self) -> None:
        if self._client is not None:
            return
        if not TYPESAFE_AVAILABLE:
            raise ProcessingError(_DEPENDENCY_ERROR)
        if not self._has_configured_api_key():
            raise ProcessingError(_CREDENTIAL_ERROR)


class Jev(_JevBase):
    """Synchronous TypeSafe Jev decision provider.

    Args:
        model: TypeSafe model or alias. Defaults to ``jev-latest``.
        api_key: TypeSafe API key. The SDK reads ``TYPESAFE_API_KEY`` when
            omitted.
        client: Optional compatible synchronous client, primarily for testing
            or custom transports. The caller retains ownership of injected
            clients.
        **client_options: Options forwarded to ``TypeSafeClient``.

    Example:
        >>> from semantica.llms import Jev
        >>> jev = Jev(api_key="...")
        >>> result = jev.decide(
        ...     state={"amount": 12500, "country": "US"},
        ...     question="Should this transaction be approved?",
        ...     kind="choice",
        ...     choices=["approve", "escalate"],
        ... )
        >>> result.value in {"approve", "escalate"}
        True
    """

    def _get_client(self) -> Any:
        self._require_available()
        if self._client is None:
            self._client = TypeSafeClient(
                api_key=self.api_key,
                model=self.model,
                **self._client_options,
            )
            self._owns_client = True
        return self._client

    def decide(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        question: Any,
        kind: JevDecisionKind,
        *,
        choices: Optional[Union[Sequence[str], Mapping[str, Any]]] = None,
        criteria: Optional[Any] = None,
        **request_options: Any,
    ) -> JevDecisionResult:
        """Make one typed decision about application state.

        ``choices`` is a Choice convenience parameter.  A sequence is mapped
        to ``{label: None}``; a mapping preserves per-label descriptions.
        Noul accepts optional ``criteria={"true": ..., "false": ...}``, and
        Score requires an ordered ``criteria`` sequence.
        """

        client = self._get_client()
        decision_question = self._build_question(question, kind, choices, criteria)
        response = client.system_one(
            state=state,
            questions={"decision": decision_question},
            **request_options,
        )
        result = self._normalize_response(response)
        self._validate_response_contract(result, decision_question)
        return result

    def close(self) -> None:
        """Close a client created by this wrapper."""

        if self._owns_client and self._client is not None:
            close = getattr(self._client, "close", None)
            if callable(close):
                close()
            self._client = None
            self._owns_client = False

    def __enter__(self) -> "Jev":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


class AsyncJev(_JevBase):
    """Asynchronous TypeSafe Jev decision provider.

    Constructor arguments and result semantics match :class:`Jev`.  Use
    ``await decide(...)`` and ``async with`` when the wrapper owns the client.
    """

    def _get_client(self) -> Any:
        self._require_available()
        if self._client is None:
            self._client = AsyncTypeSafeClient(
                api_key=self.api_key,
                model=self.model,
                **self._client_options,
            )
            self._owns_client = True
        return self._client

    async def decide(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        question: Any,
        kind: JevDecisionKind,
        *,
        choices: Optional[Union[Sequence[str], Mapping[str, Any]]] = None,
        criteria: Optional[Any] = None,
        **request_options: Any,
    ) -> JevDecisionResult:
        """Asynchronously make one typed decision about application state."""

        client = self._get_client()
        decision_question = self._build_question(question, kind, choices, criteria)
        response = await client.system_one(
            state=state,
            questions={"decision": decision_question},
            **request_options,
        )
        result = self._normalize_response(response)
        self._validate_response_contract(result, decision_question)
        return result

    async def aclose(self) -> None:
        """Close a client created by this wrapper."""

        if self._owns_client and self._client is not None:
            close = getattr(self._client, "aclose", None)
            if callable(close):
                await close()
            self._client = None
            self._owns_client = False

    async def __aenter__(self) -> "AsyncJev":
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await self.aclose()


__all__ = [
    "AsyncJev",
    "Jev",
    "JevDecisionResult",
]
