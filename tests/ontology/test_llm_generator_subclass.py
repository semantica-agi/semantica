"""Regression: LLMOntologyGenerator must emit ``subClassOf`` so OWLGenerator
keeps the class hierarchy (previously only ``parent`` was emitted and every
subclass axiom was silently dropped from the OWL output)."""

import pytest
import rdflib
from rdflib import RDFS, URIRef

from semantica.ontology.llm_generator import LLMOntologyGenerator
from semantica.ontology.owl_generator import OWLGenerator

BASE = "https://example.org/t/"


class _StubProvider:
    def __init__(self, payload):
        self.payload = payload

    def generate_structured(self, prompt, **kwargs):
        return self.payload


def _generate(classes):
    gen = LLMOntologyGenerator(provider=None)
    gen.provider = _StubProvider({"classes": classes, "properties": []})
    return gen.generate_ontology_from_text("text", name="T", base_uri=BASE)


@pytest.mark.parametrize("key", ["parent", "Parent", "subClassOf", "subclassOf"])
def test_parent_aliases_normalised_to_subclassof(key):
    onto = _generate([{"name": "Rig"}, {"name": "JackUpRig", key: "Rig"}])
    by_name = {c["name"]: c for c in onto["classes"]}
    assert by_name["JackUpRig"]["subClassOf"] == "Rig"
    assert by_name["JackUpRig"]["parent"] == "Rig"  # backward compatible
    assert by_name["Rig"]["subClassOf"] is None


def test_hierarchy_survives_owl_export():
    onto = _generate([{"name": "Rig"}, {"name": "JackUpRig", "parent": "Rig"}])
    ttl = OWLGenerator().generate_owl(onto, format="turtle")
    g = rdflib.Graph().parse(data=ttl, format="turtle")
    assert (URIRef(BASE + "JackUpRig"), RDFS.subClassOf, URIRef(BASE + "Rig")) in g
