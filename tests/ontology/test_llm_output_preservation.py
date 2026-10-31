"""Provider diagnostics and executable constraints survive public generation."""

from copy import deepcopy

import pytest

from semantica.ontology.llm_generator import LLMOntologyGenerator


def generate_saved(response):
    class SavedProvider:
        def generate_structured(self, prompt, **options):
            return response

    generator = LLMOntologyGenerator(provider=None)
    generator.provider = SavedProvider()
    return generator.generate_ontology_from_text(
        "Synthetic order specification", base_uri="https://example.org/orders/"
    )


def test_public_generation_keeps_actionable_input_diagnostics():
    response = {
        "classes": [],
        "properties": [],
        "status": "needs_input",
        "clarification_questions": ["Can an order have multiple customers?"],
        "assumptions": [{"statement": "Customer identity is unresolved"}],
    }
    original = deepcopy(response)
    output = generate_saved(response)

    assert output["status"] == "needs_input"
    assert output["clarification_questions"] == response["clarification_questions"]
    assert output["assumptions"] == response["assumptions"]
    output["clarification_questions"].append("Which statuses are allowed?")
    output["assumptions"][0]["statement"] = "Changed by caller"
    assert response == original


@pytest.mark.parametrize(
    "required,cardinality,values",
    [(True, {"min": 1, "max": 1}, ["Draft", "Submitted"]),
     (False, {"min": 0, "max": 0}, [])],
)
def test_public_generation_keeps_explicit_constraints(required, cardinality, values):
    response = {
        "classes": [{"name": "Order"}],
        "properties": [{
            "name": "status", "type": "data", "domain": "Order",
            "range": "xsd:string", "required": required,
            "cardinality": cardinality, "enum": values,
        }],
    }
    original = deepcopy(response)
    prop = generate_saved(response)["properties"][0]

    assert prop["required"] is required
    assert prop["cardinality"] == cardinality
    assert prop["enum"] == values
    prop["cardinality"]["max"] = 8
    prop["enum"].append("Cancelled")
    assert response == original


def test_missing_optional_fields_do_not_acquire_defaults():
    output = generate_saved({"classes": [{"name": "Order"}],
                             "properties": [{"name": "status"}]})
    assert not {"status", "clarification_questions", "assumptions"} & output.keys()
    assert not {"required", "cardinality", "enum"} & output["properties"][0].keys()


def test_empty_diagnostic_values_are_not_discarded():
    output = generate_saved({"status": "needs_input", "clarification_questions": [],
                             "assumptions": []})
    assert output["clarification_questions"] == []
    assert output["assumptions"] == []


def test_existing_aliases_and_iri_defaults_remain_compatible():
    output = generate_saved({
        "Classes": [{"Name": "Order", "Label": "Order"}],
        "Properties": [{"Name": "status", "Type": "data", "Domain": "Order",
                        "Range": "xsd:string", "Description": "Current status"}],
    })
    assert output["classes"][0]["uri"] == "https://example.org/orders/Order"
    prop = output["properties"][0]
    assert prop["uri"] == "https://example.org/orders/status"
    assert prop["domain"] == ["Order"]
    assert prop["range"] == ["xsd:string"]
    assert prop["comment"] == "Current status"
    assert output["version"] == "1.0"
    assert output["metadata"]["source"] == "llm"
