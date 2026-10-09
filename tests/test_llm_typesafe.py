"""Tests for the decision-only TypeSafe Jev provider wrappers."""

import json
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import toml

import semantica.llms.typesafe as typesafe_module
from semantica.context import Decision
from semantica.context.decision_models import deserialize_decision, serialize_decision
from semantica.llms import AsyncJev, Jev, JevDecisionResult
from semantica.utils.exceptions import ProcessingError


def _answer(kind, **fields):
    return SimpleNamespace(type=kind, **fields)


def _response(answer, request_id="req_123"):
    return SimpleNamespace(
        answers={"decision": answer},
        model="jev-2026-09-15",
        request_id=request_id,
        usage=SimpleNamespace(input_tokens=120, output_tokens=4),
    )


def _question_payload(question):
    """Return comparable data for real SDK models and dependency-free stubs."""

    if isinstance(question, dict):
        return question
    return question.model_dump(exclude_none=True)


def _choice_response():
    return _response(
        _answer(
            "choice",
            choice="approve",
            confidence=0.91,
            probabilities={"approve": 0.91, "escalate": 0.09},
        )
    )


def test_exports_decision_only_public_surface():
    client = MagicMock()

    assert JevDecisionResult is typesafe_module.JevDecisionResult
    assert not hasattr(Jev(client=client), "generate")
    assert not hasattr(Jev(client=client), "generate_structured")
    assert not hasattr(AsyncJev(client=client), "generate")


def test_is_available_false_without_sdk_or_injected_client(monkeypatch):
    monkeypatch.setattr(typesafe_module, "TYPESAFE_AVAILABLE", False)
    jev = Jev()

    assert jev.is_available() is False
    with pytest.raises(ProcessingError, match=r"semantica\[llm-typesafe\]"):
        jev.decide("state", "question", "noul")


def test_is_available_requires_local_credentials(monkeypatch):
    monkeypatch.setattr(typesafe_module, "TYPESAFE_AVAILABLE", True)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    assert Jev().is_available() is False
    assert Jev(api_key="test-key").is_available() is True

    monkeypatch.setenv("TYPESAFE_API_KEY", "environment-key")
    assert Jev().is_available() is True


def test_whitespace_only_credentials_are_rejected(monkeypatch):
    monkeypatch.setattr(typesafe_module, "TYPESAFE_AVAILABLE", True)
    monkeypatch.setenv("TYPESAFE_API_KEY", "   ")

    assert Jev().is_available() is False
    assert Jev(api_key="\t").is_available() is False

    with pytest.raises(ProcessingError, match="TYPESAFE_API_KEY"):
        Jev().decide("state", "question", "noul")


def test_missing_credentials_raise_clear_error(monkeypatch):
    monkeypatch.setattr(typesafe_module, "TYPESAFE_AVAILABLE", True)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(ProcessingError, match="TYPESAFE_API_KEY"):
        Jev().decide("state", "question", "noul")


def test_injected_client_is_available_without_optional_sdk(monkeypatch):
    monkeypatch.setattr(typesafe_module, "TYPESAFE_AVAILABLE", False)
    client = MagicMock()
    client.system_one.return_value = _choice_response()

    result = Jev(client=client).decide(
        "state", "Choose a route", "choice", choices=["approve", "escalate"]
    )

    assert result.value == "approve"
    question = client.system_one.call_args.kwargs["questions"]["decision"]
    assert question == {
        "type": "choice",
        "instructions": "Choose a route",
        "criteria": {"approve": None, "escalate": None},
    }


def test_choice_uses_criteria_and_preserves_response_metadata():
    client = MagicMock()
    client.system_one.return_value = _choice_response()
    jev = Jev(client=client)

    result = jev.decide(
        state={"amount": 12500},
        question="Should this transaction be approved?",
        kind="choice",
        choices={
            "approve": "Policy permits automatic approval",
            "escalate": "Human review is required",
        },
        timeout=2.5,
    )

    call = client.system_one.call_args
    assert call.kwargs["state"] == {"amount": 12500}
    assert call.kwargs["timeout"] == 2.5
    payload = _question_payload(call.kwargs["questions"]["decision"])
    assert payload == {
        "type": "choice",
        "instructions": "Should this transaction be approved?",
        "criteria": {
            "approve": "Policy permits automatic approval",
            "escalate": "Human review is required",
        },
    }

    assert result == JevDecisionResult(
        kind="choice",
        value="approve",
        probability=0.91,
        confidence=0.91,
        probabilities={"approve": 0.91, "escalate": 0.09},
        model="jev-2026-09-15",
        request_id="req_123",
        usage={"input_tokens": 120, "output_tokens": 4},
        legend={},
    )
    assert result.to_dict()["request_id"] == "req_123"


@pytest.mark.parametrize(
    "probability, expected_value, expected_confidence",
    [
        (0.0, False, 1.0),
        (0.25, False, 0.5),
        (0.5, True, 0.0),
        (0.9, True, 0.8),
        (1.0, True, 1.0),
    ],
)
def test_noul_preserves_yes_probability_and_derives_routing_certainty(
    probability, expected_value, expected_confidence
):
    client = MagicMock()
    client.system_one.return_value = _response(_answer("noul", noul=probability))

    result = Jev(client=client).decide(
        state="Transaction details",
        question="Does this transaction violate policy?",
        kind="noul",
        criteria={"true": "A violation exists", "false": "No violation exists"},
    )

    payload = _question_payload(
        client.system_one.call_args.kwargs["questions"]["decision"]
    )
    assert payload["type"] == "noul"
    assert payload["criteria"] == {
        "true": "A violation exists",
        "false": "No violation exists",
    }
    assert result.value is expected_value
    assert result.probability == probability
    assert result.confidence == pytest.approx(expected_confidence)
    assert result.probabilities == {}


def test_score_preserves_distribution_and_legend():
    client = MagicMock()
    client.system_one.return_value = _response(
        _answer(
            "score",
            score=1.7,
            confidence=0.84,
            probabilities={0: 0.05, 1: 0.20, 2: 0.75},
            legend={0: "low", 1: "medium", 2: "high"},
        )
    )

    result = Jev(client=client).decide(
        "Alert details",
        "How urgent is this alert?",
        "score",
        criteria=["low", "medium", "high"],
    )

    payload = _question_payload(
        client.system_one.call_args.kwargs["questions"]["decision"]
    )
    assert payload == {
        "type": "score",
        "instructions": "How urgent is this alert?",
        "criteria": ["low", "medium", "high"],
    }
    assert result.value == 1.7
    assert result.probability is None
    assert result.confidence == 0.84
    assert result.probabilities == {0: 0.05, 1: 0.20, 2: 0.75}
    assert result.legend == {0: "low", 1: "medium", 2: "high"}


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"kind": "unknown"}, "kind must be one of"),
        ({"kind": "choice"}, "require choices or criteria"),
        (
            {"kind": "choice", "choices": ["same", "same"]},
            "labels must be unique",
        ),
        ({"kind": "choice", "choices": ["valid", 3]}, "non-empty strings"),
        ({"kind": "noul", "choices": ["yes", "no"]}, "only valid for Choice"),
        ({"kind": "noul", "criteria": {"maybe": None}}, "only supports"),
        ({"kind": "score"}, "require ordered criteria"),
        ({"kind": "score", "criteria": "low, high"}, "ordered sequence"),
    ],
)
def test_invalid_question_inputs_fail_before_client_call(kwargs, message):
    client = MagicMock()
    jev = Jev(client=client)

    with pytest.raises(ValueError, match=message):
        jev.decide("state", "question", **kwargs)

    client.system_one.assert_not_called()


def test_sdk_errors_are_not_hidden_by_the_wrapper():
    class AuthenticationFailure(Exception):
        pass

    client = MagicMock()
    client.system_one.side_effect = AuthenticationFailure("bad key")

    with pytest.raises(AuthenticationFailure, match="bad key"):
        Jev(client=client).decide("state", "question", "noul")


def test_missing_request_id_is_normalized_to_none():
    class ResponseWithoutRequestId:
        answers = {"decision": _answer("noul", noul=0.8)}
        model = "jev-latest"
        usage = {"input_tokens": 5, "output_tokens": 1}

        @property
        def request_id(self):
            raise RuntimeError("header absent")

    client = MagicMock()
    client.system_one.return_value = ResponseWithoutRequestId()

    result = Jev(client=client).decide("state", "question", "noul")

    assert result.request_id is None


def test_response_kind_must_match_requested_kind():
    client = MagicMock()
    client.system_one.return_value = _response(_answer("noul", noul=0.99))

    with pytest.raises(ProcessingError, match="answer for a 'choice' request"):
        Jev(client=client).decide(
            "state", "Choose a route", "choice", choices=["approve", "escalate"]
        )


def test_choice_response_must_stay_inside_requested_labels():
    client = MagicMock()
    client.system_one.return_value = _response(
        _answer(
            "choice",
            choice="admin_override",
            confidence=0.99,
            probabilities={"admin_override": 0.99, "approve": 0.01},
        )
    )

    with pytest.raises(ProcessingError, match="outside the requested criteria"):
        Jev(client=client).decide(
            "state", "Choose a route", "choice", choices=["approve", "escalate"]
        )


@pytest.mark.parametrize("probabilities", [None, [], "approve=1"])
def test_choice_response_requires_probability_mapping(probabilities):
    client = MagicMock()
    client.system_one.return_value = _response(
        _answer(
            "choice",
            choice="approve",
            confidence=1.0,
            probabilities=probabilities,
        )
    )

    with pytest.raises(ProcessingError, match="invalid Choice probabilities"):
        Jev(client=client).decide(
            "state", "Choose a route", "choice", choices=["approve", "escalate"]
        )


def test_choice_response_requires_every_requested_probability():
    client = MagicMock()
    client.system_one.return_value = _response(
        _answer(
            "choice",
            choice="approve",
            confidence=1.0,
            probabilities={"approve": 1.0},
        )
    )

    with pytest.raises(ProcessingError, match="omitted Choice probabilities.*escalate"):
        Jev(client=client).decide(
            "state", "Choose a route", "choice", choices=["approve", "escalate"]
        )


@pytest.mark.parametrize(
    "answer, message",
    [
        (
            _answer(
                "score",
                score=3.0,
                confidence=0.9,
                probabilities={0: 0.0, 1: 0.0, 2: 0.1, 3: 0.9},
                legend={0: "low", 1: "medium", 2: "high", 3: "critical"},
            ),
            "Score value outside",
        ),
        (
            _answer(
                "score",
                score=1.5,
                confidence=0.9,
                probabilities={0: 0.1, 1: 0.3, 2: 0.5, 7: 0.1},
                legend={0: "low", 1: "medium", 2: "high"},
            ),
            "Score levels outside",
        ),
    ],
)
def test_score_response_must_stay_inside_requested_levels(answer, message):
    client = MagicMock()
    client.system_one.return_value = _response(answer)

    with pytest.raises(ProcessingError, match=message):
        Jev(client=client).decide(
            "state",
            "How urgent is this?",
            "score",
            criteria=["low", "medium", "high"],
        )


@pytest.mark.parametrize(
    "answer, message",
    [
        (
            _answer(
                "score",
                score=1.5,
                confidence=0.9,
                probabilities=None,
                legend={0: "low", 1: "medium", 2: "high"},
            ),
            "invalid Score probabilities",
        ),
        (
            _answer(
                "score",
                score=1.5,
                confidence=0.9,
                probabilities={0: 0.1, 1: 0.3, 2: 0.6},
                legend=None,
            ),
            "invalid Score legend",
        ),
        (
            _answer(
                "score",
                score=1.5,
                confidence=0.9,
                probabilities={0: 0.1, 1: 0.9},
                legend={0: "low", 1: "medium", 2: "high"},
            ),
            "omitted Score probabilities.*2",
        ),
        (
            _answer(
                "score",
                score=1.5,
                confidence=0.9,
                probabilities={0: 0.1, 1: 0.3, 2: 0.6},
                legend={0: "low", 1: "medium"},
            ),
            "omitted Score legend entries.*2",
        ),
        (
            _answer(
                "score",
                score=1.5,
                confidence=0.9,
                probabilities={0: 0.1, 1: 0.3, 2: 0.6},
                legend={0: "low", 1: "moderate", 2: "high"},
            ),
            "did not match.*1",
        ),
    ],
)
def test_score_response_requires_complete_matching_metadata(answer, message):
    client = MagicMock()
    client.system_one.return_value = _response(answer)

    with pytest.raises(ProcessingError, match=message):
        Jev(client=client).decide(
            "state",
            "How urgent is this?",
            "score",
            criteria=["low", "medium", "high"],
        )


def test_owned_sync_client_uses_sdk_model_default_and_request_override(monkeypatch):
    client = MagicMock()
    client.system_one.return_value = _response(_answer("noul", noul=0.9))
    client_type = MagicMock(return_value=client)
    monkeypatch.setattr(typesafe_module, "TYPESAFE_AVAILABLE", True)
    monkeypatch.setattr(typesafe_module, "TypeSafeClient", client_type)
    monkeypatch.setattr(
        typesafe_module,
        "Noul",
        lambda instructions, criteria: {
            "type": "noul",
            "instructions": instructions,
            "criteria": criteria,
        },
    )

    Jev(
        model="jev-default",
        api_key="test-key",
        base_url="https://example.test",
    ).decide("state", "question", "noul", model="jev-request")

    client_type.assert_called_once_with(
        api_key="test-key",
        model="jev-default",
        base_url="https://example.test",
    )
    assert client.system_one.call_args.kwargs["model"] == "jev-request"


@pytest.mark.asyncio
async def test_async_jev_has_sync_result_parity_and_forwards_options():
    client = SimpleNamespace(system_one=AsyncMock(return_value=_choice_response()))

    result = await AsyncJev(client=client).decide(
        state="state",
        question="Choose a route",
        kind="choice",
        choices=["approve", "escalate"],
        model="jev-preview",
    )

    assert result == Jev(client=MagicMock())._normalize_response(_choice_response())
    call = client.system_one.call_args
    assert call.kwargs["model"] == "jev-preview"
    payload = _question_payload(call.kwargs["questions"]["decision"])
    assert payload["criteria"] == {"approve": None, "escalate": None}


@pytest.mark.asyncio
async def test_owned_async_client_uses_sdk_model_default_and_request_override(
    monkeypatch,
):
    client = SimpleNamespace(
        system_one=AsyncMock(return_value=_response(_answer("noul", noul=0.9)))
    )
    client_type = MagicMock(return_value=client)
    monkeypatch.setattr(typesafe_module, "TYPESAFE_AVAILABLE", True)
    monkeypatch.setattr(typesafe_module, "AsyncTypeSafeClient", client_type)
    monkeypatch.setattr(
        typesafe_module,
        "Noul",
        lambda instructions, criteria: {
            "type": "noul",
            "instructions": instructions,
            "criteria": criteria,
        },
    )

    await AsyncJev(
        model="jev-default",
        api_key="test-key",
        base_url="https://example.test",
    ).decide("state", "question", "noul", model="jev-request")

    client_type.assert_called_once_with(
        api_key="test-key",
        model="jev-default",
        base_url="https://example.test",
    )
    assert client.system_one.call_args.kwargs["model"] == "jev-request"


def test_result_round_trips_as_decision_provenance():
    client = MagicMock()
    client.system_one.return_value = _choice_response()
    result = Jev(client=client).decide(
        "transaction", "Approve?", "choice", choices=["approve", "escalate"]
    )
    decision = Decision(
        decision_id="decision-1",
        category="transaction_review",
        scenario="wire_transfer_approval",
        reasoning="Policy and evidence were evaluated by Semantica",
        outcome=str(result.value),
        confidence=result.confidence,
        timestamp=datetime(2026, 9, 21, 12, 0, 0),
        decision_maker=f"jev:{result.model}",
        metadata={"typesafe_jev": result.to_dict()},
    )

    restored = deserialize_decision(serialize_decision(decision))

    assert restored.outcome == "approve"
    assert restored.confidence == 0.91
    assert restored.decision_maker == "jev:jev-2026-09-15"
    assert restored.metadata["typesafe_jev"]["request_id"] == "req_123"
    assert restored.metadata["typesafe_jev"]["probabilities"]["approve"] == 0.91


def test_pyproject_guards_sdk_on_python_310_and_includes_aggregate_extra():
    pyproject = toml.load(Path(__file__).resolve().parents[1] / "pyproject.toml")
    extras = pyproject["project"]["optional-dependencies"]

    assert extras["llm-typesafe"] == [
        "typesafe-sdk>=0.7.0,<0.8.0; python_version >= '3.10'"
    ]
    assert "llm-typesafe" in extras["llm-all"][0]


@pytest.fixture
def real_sdk_transport():
    """Exercise the published SDK without making network requests."""
    pytest.importorskip("typesafe_sdk")
    httpx = pytest.importorskip("httpx2")
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        question = payload["questions"]["decision"]
        kind = question["type"]
        if kind == "choice":
            answer = {
                "type": kind,
                "choice": "approve",
                "confidence": 0.91,
                "probabilities": {"approve": 0.91, "escalate": 0.09},
            }
        elif kind == "score":
            answer = {
                "type": kind,
                "score": 0.8,
                "confidence": 0.8,
                "probabilities": {"0": 0.2, "1": 0.8},
                "legend": {"0": "low", "1": "high"},
            }
        else:
            answer = {"type": "noul", "noul": 0.9}
        return httpx.Response(
            200,
            headers={"x-typesafe-request-id": "req_transport"},
            json={
                "answers": {"decision": answer},
                "model": "jev-concrete",
                "usage": {"input_tokens": 12, "output_tokens": 2},
            },
        )

    return httpx.MockTransport(respond), requests


def _assert_real_sdk_result(result, kind):
    assert result.kind == kind
    assert result.model == "jev-concrete"
    assert result.request_id == "req_transport"
    assert result.usage == {"input_tokens": 12, "output_tokens": 2}
    if kind == "choice":
        assert result.probabilities == {"approve": 0.91, "escalate": 0.09}
    elif kind == "score":
        assert result.probabilities == {0: 0.2, 1: 0.8}
        assert result.legend == {0: "low", 1: "high"}
    else:
        assert result.value is True
        assert result.probability == 0.9


@pytest.mark.parametrize(
    "kind, options",
    [
        ("choice", {"choices": ["approve", "escalate"]}),
        ("noul", {}),
        ("score", {"criteria": ["low", "high"]}),
    ],
)
def test_real_owned_sdk_sync_dispatch_and_model_precedence(
    real_sdk_transport, kind, options
):
    transport, requests = real_sdk_transport
    with Jev(api_key="test-key", model="jev-default", transport=transport) as provider:
        for request_options in ({}, {"model": "jev-override"}, {}):
            result = provider.decide(
                "state", "question", kind, **options, **request_options
            )
            _assert_real_sdk_result(result, kind)
    assert [request["model"] for request in requests] == [
        "jev-default",
        "jev-override",
        "jev-default",
    ]
    assert all(request["state"] == "state" for request in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind, options",
    [
        ("choice", {"choices": ["approve", "escalate"]}),
        ("noul", {}),
        ("score", {"criteria": ["low", "high"]}),
    ],
)
async def test_real_owned_sdk_async_dispatch_and_model_precedence(
    real_sdk_transport, kind, options
):
    transport, requests = real_sdk_transport
    async with AsyncJev(
        api_key="test-key", model="jev-default", transport=transport
    ) as provider:
        for request_options in ({}, {"model": "jev-override"}, {}):
            result = await provider.decide(
                "state", "question", kind, **options, **request_options
            )
            _assert_real_sdk_result(result, kind)
    assert [request["model"] for request in requests] == [
        "jev-default",
        "jev-override",
        "jev-default",
    ]
    assert all(request["state"] == "state" for request in requests)


def test_typesafe_ci_pin_and_hashes_match_uv_lock():
    root = Path(__file__).resolve().parents[1]
    lock = toml.load(root / "uv.lock")
    package = next(p for p in lock["package"] if p["name"] == "typesafe-sdk")
    requirements = (root / "requirements-ci.txt").read_text()
    entry = re.search(
        r"(?m)^typesafe-sdk==([^\n]+)\n((?:    --hash=[^\n]+\n)+)", requirements
    )
    assert entry is not None
    assert entry.group(1).split()[0] == package["version"]
    expected_hashes = {package["sdist"]["hash"]} | {
        wheel["hash"] for wheel in package["wheels"]
    }
    assert set(re.findall(r"sha256:[a-f0-9]+", entry.group(2))) == expected_hashes
