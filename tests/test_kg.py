"""
Layer 2 — Knowledge graph builder tests.

Verifies that to_json() and to_turtle() produce correct intermediate
records and Turtle ABox, with particular focus on:
  - LegalSource deduplication (same regulation label → one individual)
  - Controlled vocabulary values → NORMA IRIs, not literals
  - ABox correctly imports the TBox
"""

import pytest
from norma.kg.builder import parse_bpmn, to_json, to_turtle
import xml.etree.ElementTree as ET
import io


BASE_IRI = "https://w3id.org/norma-abox/test"
NORMA_IRI = "https://w3id.org/norma-ontology#"
NORMA_ONT = "https://w3id.org/norma-ontology"


def _records(sample_bpmn_xml):
    """Parse sample BPMN XML via a temp file to feed kg_builder."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".bpmn", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(sample_bpmn_xml)
        tmp = f.name
    try:
        elements = parse_bpmn(tmp)
    finally:
        os.unlink(tmp)
    return to_json(elements)


class TestToJson:
    def test_two_task_records(self, sample_bpmn_xml):
        recs = _records(sample_bpmn_xml)
        tasks = [r for r in recs if r["element_type"] == "task"]
        assert len(tasks) == 2

    def test_one_gateway_record(self, sample_bpmn_xml):
        recs = _records(sample_bpmn_xml)
        gws = [r for r in recs if r["element_type"] == "exclusiveGateway"]
        assert len(gws) == 1

    def test_obligation_fields(self, sample_bpmn_xml):
        recs = _records(sample_bpmn_xml)
        obl = next(r for r in recs if r.get("deontic_id") == "OBL_1")
        assert obl["deontic_type"]  == "obligation"
        assert obl["agent"]         == "AI owner"
        assert obl["binding_force"] == "hard_law"
        assert obl["article"]       == "50"

    def test_recommendation_fields(self, sample_bpmn_xml):
        recs = _records(sample_bpmn_xml)
        rec = next(r for r in recs if r.get("deontic_id") == "REC_1")
        assert rec["deontic_type"]  == "recommendation"
        assert rec["binding_force"] == "soft_law"
        assert rec["article"]       == "95"


class TestToTurtle:
    def _turtle(self, sample_bpmn_xml):
        recs = _records(sample_bpmn_xml)
        return to_turtle(recs, "test_source", BASE_IRI)

    def test_imports_tbox(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert f"owl:imports <{NORMA_ONT}>" in ttl

    def test_legal_source_declared_once(self, sample_bpmn_xml):
        """
        Both tasks and the gateway share regulation "EU AI Act".
        The ABox must declare exactly one :Regulation_EU_AI_Act individual.
        """
        ttl = self._turtle(sample_bpmn_xml)
        # Count declarations of the LegalSource individual
        occurrences = ttl.count("a owl:NamedIndividual, norma:LegalSource")
        assert occurrences == 1

    def test_obligation_iri_not_literal(self, sample_bpmn_xml):
        """norma:HardLaw must appear as an IRI, not as a string literal."""
        ttl = self._turtle(sample_bpmn_xml)
        assert f"<{NORMA_IRI}HardLaw>"      in ttl
        assert '"hard_law"'                  not in ttl

    def test_norm_status_iri_not_literal(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert f"<{NORMA_IRI}Active>"        in ttl
        assert '"active"'                    not in ttl

    def test_review_status_iri_not_literal(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert f"<{NORMA_IRI}Approved>"      in ttl
        assert '"approved"'                  not in ttl

    def test_risk_level_iri_not_literal(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert f"<{NORMA_IRI}High>"          in ttl
        assert '"high"'                      not in ttl

    def test_obligation_class_iri(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert f"<{NORMA_IRI}Obligation>"    in ttl

    def test_recommendation_class_iri(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert f"<{NORMA_IRI}Recommendation>" in ttl

    def test_agent_individual_declared(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert "norma:LegalAgent" in ttl
        assert 'rdfs:label "AI owner"@en' in ttl

    def test_articles_aggregated_under_one_source(self, sample_bpmn_xml):
        """Art. 50 and Art. 95 must both appear under the single LegalSource."""
        ttl = self._turtle(sample_bpmn_xml)
        assert '"50"^^xsd:string' in ttl
        assert '"95"^^xsd:string' in ttl
