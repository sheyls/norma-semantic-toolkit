"""
Layer 4 — SWRL exporter tests.

Verifies that the exporter produces syntactically correct OWL/XML,
uses the correct IRI namespaces, and emits the right structural
markers for Protégé / OWL-reasoner consumption.

"""

import pytest
import tempfile
import os
import xml.etree.ElementTree as ET

from norma_engine.parsing.bpmn_parser import parse_bpmn_to_reduced_graph
from norma_engine.rules.extractor import enumerate_paths_and_build_ir
from norma_engine.exporters.swrl import export_rules_to_owl

RULES_IRI = "http://test.org/norma/rules"
ABOX_IRI  = "http://test.org/norma"
TBOX_NS   = "https://w3id.org/def/norma-o#"


def _rules(sample_bpmn_xml):
    nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(sample_bpmn_xml)
    _, rules, superiority = enumerate_paths_and_build_ir(
        nodes=nodes,
        edges=edges,
        gateway_outgoing_index=gw_index,
        task_props=task_props,
    )
    return rules, superiority


def _export(sample_bpmn_xml):
    rules, _ = _rules(sample_bpmn_xml)
    with tempfile.NamedTemporaryFile(
        suffix=".owl", delete=False, mode="w", encoding="utf-8"
    ) as f:
        tmp = f.name
    try:
        export_rules_to_owl(
            rules,
            out_file=tmp,
            rules_iri=RULES_IRI,
            abox_iri=ABOX_IRI,
        )
        with open(tmp, encoding="utf-8") as f:
            content = f.read()
    finally:
        os.unlink(tmp)
    return content


class TestSWRLExporter:
    def test_output_is_valid_xml(self, sample_bpmn_xml):
        ET.fromstring(_export(sample_bpmn_xml))

    def test_two_swrl_rules_present(self, sample_bpmn_xml):
        assert _export(sample_bpmn_xml).count("<swrl:Imp ") == 2

    def test_imports_abox(self, sample_bpmn_xml):
        content = _export(sample_bpmn_xml)
        assert f'rdf:resource="{ABOX_IRI}"' in content

    def test_ontology_iri_is_rules_iri(self, sample_bpmn_xml):
        content = _export(sample_bpmn_xml)
        assert f'rdf:about="{RULES_IRI}"' in content

    def test_tbox_properties_in_head(self, sample_bpmn_xml):
        # SWRL head is compact: only ClassAtoms (deontic type assertions).
        # RelationAtoms and DataAtoms are omitted — they are declared in the ABox
        # which the SWRL file imports, so asserting them in the rule head is redundant.
        content = _export(sample_bpmn_xml)
        assert f"{TBOX_NS}Obligation" in content
        assert f"{TBOX_NS}Recommendation" in content
        assert f"{TBOX_NS}hasLegalAgent" not in content
        assert f"{TBOX_NS}hasLegalSource" not in content

    def test_abox_individuals_in_head(self, sample_bpmn_xml):
        # Compact head: norm individuals appear as ClassAtom subjects; agent individuals do not.
        content = _export(sample_bpmn_xml)
        assert f"{ABOX_IRI}#OBL_1" in content
        assert f"{ABOX_IRI}#REC_1" in content
        assert f"{ABOX_IRI}#Agent_AI_owner" not in content

    def test_body_uses_boolean_condition(self, sample_bpmn_xml):
        content = _export(sample_bpmn_xml)
        assert 'rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean"' in content
        assert ">true<"  in content
        assert ">false<" in content

    def test_variable_declared(self, sample_bpmn_xml):
        content = _export(sample_bpmn_xml)
        assert "swrl:Variable" in content
        assert f"{RULES_IRI}#var_x" in content

    def test_binding_force_tbox_individual_in_head(self, sample_bpmn_xml):
        # Compact head omits RelationAtoms — binding-force individuals stay in the ABox only.
        content = _export(sample_bpmn_xml)
        assert f"{TBOX_NS}HardLaw" not in content
        assert f"{TBOX_NS}SoftLaw" not in content

    def test_deontic_id_data_atom_in_head(self, sample_bpmn_xml):
        # Compact head omits DataAtoms — deonticId literals stay in the ABox only.
        content = _export(sample_bpmn_xml)
        assert f"{TBOX_NS}deonticId" not in content
        assert ">OBL_1<" not in content
        assert ">REC_1<" not in content

    def test_semantic_template_data_is_exported(self, sample_bpmn_xml):
        # Compact head omits DataAtoms and RelationAtoms — annotation metadata stays in the ABox only.
        content = _export(sample_bpmn_xml)
        assert f"{TBOX_NS}fromRegulation" not in content
        assert f"{TBOX_NS}fromArticle" not in content
        assert f"{TBOX_NS}annotationDate" not in content
        assert f"{TBOX_NS}confidenceScore" not in content
        assert f"{TBOX_NS}wasGeneratedByAnnotationActivity" not in content
