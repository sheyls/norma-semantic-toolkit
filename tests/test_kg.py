"""
Layer 2 — Knowledge graph builder tests.

Verifies that to_json() and to_turtle() produce correct intermediate
records and Turtle ABox, with particular focus on:
  - LegalSource deduplication (same regulation label → one individual)
  - Controlled vocabulary values → NORMA IRIs, not literals
  - ABox correctly imports the TBox
"""

import pytest
from norma_engine.kg.builder import parse_bpmn, to_json, to_turtle
from norma_engine.kg.normalizer import normalize
from norma_engine.parsing.bpmn_parser import parse_bpmn_to_reduced_graph
from norma_engine.rules.extractor import enumerate_paths_and_build_ir
import xml.etree.ElementTree as ET
import io


BASE_IRI = "https://w3id.org/norma-abox/test"
NORMA_IRI = "https://w3id.org/def/norma-o#"
NORMA_ONT = "https://w3id.org/def/norma-o"


MULTI_GATEWAY_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions
    xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:zeebe="http://camunda.org/schema/zeebe/1.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    id="Definitions_multi" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_multi" isExecutable="true">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_start_gw1</bpmn:outgoing>
    </bpmn:startEvent>

    <bpmn:exclusiveGateway id="GW_1" name="Is the system high risk?">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType" value="exclusiveGateway" />
          <zeebe:property name="gw_conditionStatement" value="Is the system high risk?" />
          <zeebe:property name="gw_trueBranch" value="Yes" />
          <zeebe:property name="gw_falseBranch" value="No" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_start_gw1</bpmn:incoming>
      <bpmn:outgoing>Flow_gw1_gw2</bpmn:outgoing>
      <bpmn:outgoing>Flow_gw1_end</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <bpmn:exclusiveGateway id="GW_2" name="Is the system real-life tested?">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType" value="exclusiveGateway" />
          <zeebe:property name="gw_conditionStatement" value="Is the system real-life tested?" />
          <zeebe:property name="gw_trueBranch" value="Yes" />
          <zeebe:property name="gw_falseBranch" value="No" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_gw1_gw2</bpmn:incoming>
      <bpmn:outgoing>Flow_gw2_end</bpmn:outgoing>
      <bpmn:outgoing>Flow_gw2_task</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <bpmn:sequenceFlow id="Flow_start_gw1" sourceRef="Start_1" targetRef="GW_1" />
    <bpmn:sequenceFlow id="Flow_gw1_gw2" name="Yes" sourceRef="GW_1" targetRef="GW_2" />
    <bpmn:sequenceFlow id="Flow_gw1_end" name="No" sourceRef="GW_1" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_gw2_end" name="Yes" sourceRef="GW_2" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_gw2_task" name="No" sourceRef="GW_2" targetRef="Task_OBL" />

    <bpmn:task id="Task_OBL" name="Apply high-risk safeguards">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType" value="task" />
          <zeebe:property name="compliance_deonticType" value="obligation" />
          <zeebe:property name="compliance_deonticId" value="OBL_MULTI" />
          <zeebe:property name="compliance_agent" value="AI provider" />
          <zeebe:property name="compliance_action" value="apply safeguards" />
          <zeebe:property name="compliance_object" value="AI system" />
          <zeebe:property name="compliance_bindingForce" value="hard_law" />
          <zeebe:property name="compliance_status" value="active" />
          <zeebe:property name="compliance_regulation" value="EU AI Act" />
          <zeebe:property name="compliance_article" value="8" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_gw2_task</bpmn:incoming>
      <bpmn:outgoing>Flow_task_end</bpmn:outgoing>
    </bpmn:task>

    <bpmn:sequenceFlow id="Flow_task_end" sourceRef="Task_OBL" targetRef="End_1" />

    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_gw1_end</bpmn:incoming>
      <bpmn:incoming>Flow_gw2_end</bpmn:incoming>
      <bpmn:incoming>Flow_task_end</bpmn:incoming>
    </bpmn:endEvent>
  </bpmn:process>
</bpmn:definitions>
"""


REPEATED_CONDITION_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions
    xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:zeebe="http://camunda.org/schema/zeebe/1.0"
    id="Definitions_repeat" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_repeat" isExecutable="true">
    <bpmn:startEvent id="Start_1">
      <bpmn:outgoing>Flow_start_gw1</bpmn:outgoing>
    </bpmn:startEvent>

    <bpmn:exclusiveGateway id="GW_1" name="Is the system used in public spaces?">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType" value="exclusiveGateway" />
          <zeebe:property name="gw_conditionStatement" value="Is the system used in public spaces?" />
          <zeebe:property name="gw_trueBranch" value="Yes" />
          <zeebe:property name="gw_falseBranch" value="No" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_start_gw1</bpmn:incoming>
      <bpmn:outgoing>Flow_gw1_gw2</bpmn:outgoing>
      <bpmn:outgoing>Flow_gw1_end</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <bpmn:exclusiveGateway id="GW_2" name="Is the system used in public spaces?">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType" value="exclusiveGateway" />
          <zeebe:property name="gw_conditionStatement" value="Is the system used in public spaces?" />
          <zeebe:property name="gw_trueBranch" value="Yes" />
          <zeebe:property name="gw_falseBranch" value="No" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_gw1_gw2</bpmn:incoming>
      <bpmn:outgoing>Flow_gw2_task</bpmn:outgoing>
      <bpmn:outgoing>Flow_gw2_end</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <bpmn:task id="Task_OBL" name="Apply public-space safeguards">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType" value="task" />
          <zeebe:property name="compliance_deonticType" value="obligation" />
          <zeebe:property name="compliance_deonticId" value="OBL_REPEAT" />
          <zeebe:property name="compliance_agent" value="AI provider" />
          <zeebe:property name="compliance_action" value="apply safeguards" />
          <zeebe:property name="compliance_object" value="AI system" />
          <zeebe:property name="compliance_bindingForce" value="hard_law" />
          <zeebe:property name="compliance_status" value="active" />
          <zeebe:property name="compliance_regulation" value="EU AI Act" />
          <zeebe:property name="compliance_article" value="5" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_gw2_task</bpmn:incoming>
      <bpmn:outgoing>Flow_task_end</bpmn:outgoing>
    </bpmn:task>

    <bpmn:sequenceFlow id="Flow_start_gw1" sourceRef="Start_1" targetRef="GW_1" />
    <bpmn:sequenceFlow id="Flow_gw1_gw2" name="Yes" sourceRef="GW_1" targetRef="GW_2" />
    <bpmn:sequenceFlow id="Flow_gw1_end" name="No" sourceRef="GW_1" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_gw2_task" name="Yes" sourceRef="GW_2" targetRef="Task_OBL" />
    <bpmn:sequenceFlow id="Flow_gw2_end" name="No" sourceRef="GW_2" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_task_end" sourceRef="Task_OBL" targetRef="End_1" />

    <bpmn:endEvent id="End_1">
      <bpmn:incoming>Flow_gw1_end</bpmn:incoming>
      <bpmn:incoming>Flow_gw2_end</bpmn:incoming>
      <bpmn:incoming>Flow_task_end</bpmn:incoming>
    </bpmn:endEvent>
  </bpmn:process>
</bpmn:definitions>
"""


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

    def test_action_individual_declared(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert "norma:LegalAction" in ttl
        assert 'rdfs:label "mark synthetic content"@en' in ttl

    def test_uses_ontology_legal_object_property(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert "norma:hasLegalObject" in ttl
        assert "norma:hasObject" not in ttl

    def test_provenance_uses_annotation_activity_model(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert "norma:AnnotationActivity" in ttl
        assert "norma:AnnotatorAgent" in ttl
        assert "norma:wasGeneratedByAnnotationActivity" in ttl
        assert "norma:wasAttributedToAnnotator" in ttl
        assert "norma:wasAssociatedWithAnnotator" in ttl
        assert "norma:annotator" not in ttl

    def test_norms_link_to_legal_source_derivation(self, sample_bpmn_xml):
        ttl = self._turtle(sample_bpmn_xml)
        assert "norma:hasLegalSource" in ttl
        assert "norma:wasDerivedFromSource" in ttl

    def test_articles_aggregated_under_one_source(self, sample_bpmn_xml):
        """Art. 50 and Art. 95 must both appear under the single LegalSource."""
        ttl = self._turtle(sample_bpmn_xml)
        assert '"50"^^xsd:string' in ttl
        assert '"95"^^xsd:string' in ttl

    def test_trigger_events_do_not_preassert_activates_norm(self, sample_bpmn_xml):
        recs = _records(sample_bpmn_xml)

        nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(sample_bpmn_xml)
        _, rules_ir, _ = enumerate_paths_and_build_ir(
            nodes=nodes,
            edges=edges,
            gateway_outgoing_index=gw_index,
            task_props=task_props,
        )

        ttl = to_turtle(recs, "test_source", BASE_IRI, rules_ir=rules_ir)
        assert "a owl:NamedIndividual, norma:TriggerEvent ;" in ttl
        assert "norma:activatesNorm" not in ttl
        assert "norma:hasOutcome norma:TrueOutcome" in ttl or "norma:hasOutcome norma:FalseOutcome" in ttl

    def test_multi_gateway_rules_keep_atomic_conditions_in_abox(self):
        recs = _records(MULTI_GATEWAY_BPMN)
        nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(MULTI_GATEWAY_BPMN)
        _, rules_ir, _ = enumerate_paths_and_build_ir(
            nodes=nodes,
            edges=edges,
            gateway_outgoing_index=gw_index,
            task_props=task_props,
        )

        ttl = to_turtle(recs, "test_source", BASE_IRI, rules_ir=rules_ir)
        assert 'rdfs:label "Is the system high risk?"@en' in ttl
        assert 'rdfs:label "Is the system real-life tested?"@en' in ttl
        assert "ConditionPath_" not in ttl

    def test_repeated_gateway_question_reuses_one_atomic_condition(self):
        recs = _records(REPEATED_CONDITION_BPMN)
        nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(REPEATED_CONDITION_BPMN)
        _, rules_ir, _ = enumerate_paths_and_build_ir(
            nodes=nodes,
            edges=edges,
            gateway_outgoing_index=gw_index,
            task_props=task_props,
        )

        ttl = to_turtle(recs, "test_source", BASE_IRI, rules_ir=rules_ir)
        assert ttl.count('rdfs:label "Is the system used in public spaces?"@en') == 1
        assert "Condition_Is_the_system_used_in_public_spaces" in ttl

    def test_reuses_first_norm_instance_when_signature_matches(self):
        records = [
            {
                "bpmn_id": "Task_A",
                "bpmn_name": "First obligation",
                "element_type": "task",
                "deontic_type": "obligation",
                "deontic_id": "OBL_First",
                "norm_statement": "Providers must comply",
                "agent": "AI provider",
                "action": "comply",
                "object": "AI system",
                "trigger_condition": "",
                "fact_statement": "",
                "binding_force": "hard_law",
                "norm_status": "active",
                "risk_level": "high",
                "extraction_method": "",
                "review_status": "",
                "jurisdiction": "",
                "effective_date": "",
                "deadline": "",
                "exception": "",
                "sanction": "",
                "annotator": "",
                "regulation": "EU AI Act",
                "article": "50",
                "paragraph": "1",
                "confidence": "",
                "annotation_date": "",
                "last_review_date": "",
                "regulation_uri": "",
            },
            {
                "bpmn_id": "Task_B",
                "bpmn_name": "Second obligation",
                "element_type": "task",
                "deontic_type": "obligation",
                "deontic_id": "OBL_Second",
                "norm_statement": "Providers must comply",
                "agent": "AI provider",
                "action": "comply",
                "object": "AI system",
                "trigger_condition": "",
                "fact_statement": "",
                "binding_force": "hard_law",
                "norm_status": "active",
                "risk_level": "high",
                "extraction_method": "",
                "review_status": "",
                "jurisdiction": "",
                "effective_date": "",
                "deadline": "",
                "exception": "",
                "sanction": "",
                "annotator": "",
                "regulation": "EU AI Act",
                "article": "50",
                "paragraph": "1",
                "confidence": "",
                "annotation_date": "",
                "last_review_date": "",
                "regulation_uri": "",
            },
        ]
        normalized, _ = normalize(records)
        assert normalized[0]["deontic_id"] == "OBL_First"
        assert normalized[1]["deontic_id"] == "OBL_First"

        ttl = to_turtle(normalized, "test_source", BASE_IRI)
        assert ttl.count("a owl:NamedIndividual, <https://w3id.org/def/norma-o#Obligation>") == 1
