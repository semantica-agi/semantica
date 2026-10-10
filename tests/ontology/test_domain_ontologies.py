"""Regression tests for the DomainOntologies template registry (#1819).

The module docstring advertises healthcare, finance, legal, research and
cybersecurity templates. Before this fix only healthcare and finance existed,
so ``get_domain_template`` returned a bare ``None`` for the other three.
"""

import logging

import pytest

from semantica.ontology.domain_ontologies import DomainOntologies

ADVERTISED_DOMAINS = ["healthcare", "finance", "legal", "research", "cybersecurity"]


@pytest.fixture
def domains():
    return DomainOntologies()


@pytest.mark.parametrize("domain", ADVERTISED_DOMAINS)
def test_advertised_domain_has_a_template(domains, domain):
    template = domains.get_domain_template(domain)
    assert template is not None
    assert template["classes"]
    assert template["properties"]


@pytest.mark.parametrize("domain", ADVERTISED_DOMAINS)
def test_create_domain_ontology_for_advertised_domain(domains, domain):
    ontology = domains.create_domain_ontology(domain)
    assert ontology["classes"] == domains.get_domain_template(domain)["classes"]
    assert ontology["properties"] == domains.get_domain_template(domain)["properties"]


def test_list_domains_covers_every_advertised_domain(domains):
    assert set(ADVERTISED_DOMAINS) <= set(domains.list_domains())


def test_unknown_domain_logs_the_available_domains(domains, caplog):
    with caplog.at_level(logging.WARNING, logger="semantica.domain_ontologies"):
        assert domains.get_domain_template("nonexistent") is None
    assert "nonexistent" in caplog.text
    assert "healthcare" in caplog.text
