"""
Shared fixtures for the NORMA test suite.

The SAMPLE_BPMN string is a minimal but complete annotated process:
  - Gateway: "Generation of synthetic content?" (Yes/No)
  - Yes branch → Task OBL_1: obligation, AI owner, Art. 50, hard_law
  - No  branch → Task REC_1: recommendation, AI owner, Art. 95, soft_law

This covers one condition, two deontic types, two binding forces,
and the normalizer scenario where the two tasks share the regulation
label "EU AI Act" (same label → one LegalSource individual in the ABox).
"""

import pytest

SAMPLE_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions
    xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:zeebe="http://camunda.org/schema/zeebe/1.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    id="Definitions_test" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_test" isExecutable="true">

    <bpmn:startEvent id="Start_1" name="start">
      <bpmn:outgoing>Flow_s_gw</bpmn:outgoing>
    </bpmn:startEvent>

    <bpmn:exclusiveGateway id="GW_1" name="Generation of synthetic content?">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType"    value="exclusiveGateway" />
          <zeebe:property name="gw_conditionStatement"     value="Generation of synthetic content?" />
          <zeebe:property name="gw_trueBranch"             value="Yes" />
          <zeebe:property name="gw_falseBranch"            value="No" />
          <zeebe:property name="compliance_status"         value="active" />
          <zeebe:property name="compliance_regulation"     value="EU AI Act" />
          <zeebe:property name="compliance_extractionMethod" value="manual_lawyer" />
          <zeebe:property name="compliance_legalReview"    value="approved" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_s_gw</bpmn:incoming>
      <bpmn:outgoing>Flow_gw_obl</bpmn:outgoing>
      <bpmn:outgoing>Flow_gw_rec</bpmn:outgoing>
    </bpmn:exclusiveGateway>

    <bpmn:sequenceFlow id="Flow_s_gw"   sourceRef="Start_1" targetRef="GW_1" />
    <bpmn:sequenceFlow id="Flow_gw_obl" name="Yes" sourceRef="GW_1" targetRef="Task_OBL" />
    <bpmn:sequenceFlow id="Flow_gw_rec" name="No"  sourceRef="GW_1" targetRef="Task_REC" />

    <bpmn:task id="Task_OBL" name="Marking obligation">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType"    value="task" />
          <zeebe:property name="compliance_deonticType"    value="obligation" />
          <zeebe:property name="compliance_deonticId"      value="OBL_1" />
          <zeebe:property name="compliance_agent"          value="AI owner" />
          <zeebe:property name="compliance_action"         value="mark synthetic content" />
          <zeebe:property name="compliance_object"         value="AI generated content" />
          <zeebe:property name="compliance_bindingForce"   value="hard_law" />
          <zeebe:property name="compliance_status"         value="active" />
          <zeebe:property name="compliance_riskLevel"      value="high" />
          <zeebe:property name="compliance_regulation"     value="EU AI Act" />
          <zeebe:property name="compliance_article"        value="50" />
          <zeebe:property name="compliance_paragraph"      value="2" />
          <zeebe:property name="compliance_extractionMethod" value="manual_lawyer" />
          <zeebe:property name="compliance_confidence"     value="0.95" />
          <zeebe:property name="compliance_legalReview"    value="approved" />
          <zeebe:property name="compliance_annotator"      value="test" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_gw_obl</bpmn:incoming>
      <bpmn:outgoing>Flow_obl_end</bpmn:outgoing>
    </bpmn:task>

    <bpmn:task id="Task_REC" name="Voluntary codes of conduct">
      <bpmn:extensionElements>
        <zeebe:properties>
          <zeebe:property name="compliance_elementType"    value="task" />
          <zeebe:property name="compliance_deonticType"    value="recommendation" />
          <zeebe:property name="compliance_deonticId"      value="REC_1" />
          <zeebe:property name="compliance_agent"          value="AI owner" />
          <zeebe:property name="compliance_action"         value="adopt voluntary codes" />
          <zeebe:property name="compliance_object"         value="generated content" />
          <zeebe:property name="compliance_bindingForce"   value="soft_law" />
          <zeebe:property name="compliance_status"         value="active" />
          <zeebe:property name="compliance_riskLevel"      value="low" />
          <zeebe:property name="compliance_regulation"     value="EU AI Act" />
          <zeebe:property name="compliance_article"        value="95" />
          <zeebe:property name="compliance_paragraph"      value="2" />
          <zeebe:property name="compliance_extractionMethod" value="manual_lawyer" />
          <zeebe:property name="compliance_confidence"     value="0.90" />
          <zeebe:property name="compliance_legalReview"    value="approved" />
          <zeebe:property name="compliance_annotator"      value="test" />
        </zeebe:properties>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_gw_rec</bpmn:incoming>
      <bpmn:outgoing>Flow_rec_end</bpmn:outgoing>
    </bpmn:task>

    <bpmn:sequenceFlow id="Flow_obl_end" sourceRef="Task_OBL" targetRef="End_1" />
    <bpmn:sequenceFlow id="Flow_rec_end" sourceRef="Task_REC" targetRef="End_1" />

    <bpmn:endEvent id="End_1" name="end">
      <bpmn:incoming>Flow_obl_end</bpmn:incoming>
      <bpmn:incoming>Flow_rec_end</bpmn:incoming>
    </bpmn:endEvent>

  </bpmn:process>
</bpmn:definitions>
"""


@pytest.fixture
def sample_bpmn_xml() -> str:
    return SAMPLE_BPMN
