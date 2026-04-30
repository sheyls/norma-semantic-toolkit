"""
Layer 3 — Rule extraction tests.

Verifies DFS path enumeration, RuleIR construction, condition value
assignment (true/false branch), and superiority relation generation.
"""

import pytest
from norma_engine.parsing.bpmn_parser import parse_bpmn_to_reduced_graph
from norma_engine.rules.extractor import enumerate_paths_and_build_ir
from norma_engine.rules.ir import Ref


def _run(sample_bpmn_xml):
    nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(sample_bpmn_xml)
    paths, rules, superiority = enumerate_paths_and_build_ir(
        nodes=nodes,
        edges=edges,
        gateway_outgoing_index=gw_index,
        task_props=task_props,
        collect_paths=True,
    )
    return paths, rules, superiority


REPEATED_CONDITION_SAME_VALUE_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions
    xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:zeebe="http://camunda.org/schema/zeebe/1.0"
    id="Definitions_repeat_same" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_repeat_same" isExecutable="true">
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


REPEATED_CONDITION_CONTRADICTION_BPMN = REPEATED_CONDITION_SAME_VALUE_BPMN.replace(
    'id="Flow_gw2_task" name="Yes" sourceRef="GW_2" targetRef="Task_OBL" />',
    'id="Flow_gw2_task" name="No" sourceRef="GW_2" targetRef="Task_OBL" />',
).replace(
    'id="Flow_gw2_end" name="No" sourceRef="GW_2" targetRef="End_1" />',
    'id="Flow_gw2_end" name="Yes" sourceRef="GW_2" targetRef="End_1" />',
)


class TestPathEnumeration:
    def test_two_paths_found(self, sample_bpmn_xml):
        paths, _, _ = _run(sample_bpmn_xml)
        assert len(paths) == 2

    def test_each_path_has_one_task(self, sample_bpmn_xml):
        paths, _, _ = _run(sample_bpmn_xml)
        for path in paths:
            tasks = [tid for e in path for tid in e.tasks]
            assert len(tasks) == 1


class TestRuleIR:
    def test_two_rules_generated(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        assert len(rules) == 2

    def test_rule_ids_sequential(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        assert {r.rid for r in rules} == {"r1", "r2"}

    def test_each_rule_has_one_condition(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        for rule in rules:
            assert len(rule.conditions) == 1

    def test_conditions_are_opposite_truth_values(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        condition_values = {r.conditions[0].value for r in rules}
        assert condition_values == {True, False}

    def test_obligation_rule_has_true_condition(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        obl_rule = next(
            r for r in rules
            if any("OBLIGATION" in a.name.upper() or "OBL" in a.name.upper()
                   for a in r.actions)
        )
        assert obl_rule.conditions[0].value is True

    def test_recommendation_rule_has_false_condition(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        rec_rule = next(
            r for r in rules
            if any("RECOMMENDATION" in a.name.upper() or "REC" in a.name.upper()
                   for a in r.actions)
        )
        assert rec_rule.conditions[0].value is False

    def test_each_rule_has_one_action(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        for rule in rules:
            assert len(rule.actions) == 1

    def test_relation_atoms_present(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        for rule in rules:
            assert len(rule.relations) > 0

    def test_uses_legal_action_and_object_relations(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        predicates = {
            rel.predicate.name
            for rule in rules
            for rel in rule.relations
        }
        assert "hasLegalAgent" in predicates
        assert "hasLegalAction" in predicates
        assert "hasLegalObject" in predicates
        assert "hasObject" not in predicates
        assert "isLegalAgentOf" not in predicates

    def test_rule_atoms_include_template_semantics(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        relation_predicates = {
            rel.predicate.name
            for rule in rules
            for rel in rule.relations
        }
        data_predicates = {
            dat.predicate.name
            for rule in rules
            for dat in rule.data_atoms
        }
        assert "hasNormStatus" in relation_predicates
        assert "hasExtractionMethod" in relation_predicates
        assert "hasReviewStatus" in relation_predicates
        assert "hasLegalSource" in relation_predicates
        assert "wasGeneratedByAnnotationActivity" in relation_predicates
        assert "normStatement" in data_predicates or "factStatement" in data_predicates
        assert "confidenceScore" in data_predicates

    def test_data_atoms_include_deontic_id(self, sample_bpmn_xml):
        _, rules, _ = _run(sample_bpmn_xml)
        for rule in rules:
            deontic_ids = [
                d.value for d in rule.data_atoms
                if d.predicate == Ref("tbox", "deonticId")
            ]
            assert len(deontic_ids) == 1
            assert deontic_ids[0] in {"OBL_1", "REC_1"}

    def test_missing_agent_does_not_create_placeholder_agent(self, sample_bpmn_xml):
        xml = sample_bpmn_xml.replace(
            '<zeebe:property name="compliance_agent"          value="AI owner" />',
            "",
            1,
        )
        _, rules, _ = _run(xml)
        obligation_rule = next(
            r for r in rules
            if any(d.value == "OBL_1" for d in r.data_atoms if d.predicate == Ref("tbox", "deonticId"))
        )
        relation_predicates = {rel.predicate.name for rel in obligation_rule.relations}
        relation_objects = {rel.object.name for rel in obligation_rule.relations}
        assert "hasLegalAgent" not in relation_predicates
        assert "Agent_x" not in relation_objects

    def test_custom_gateway_branch_labels_are_mapped(self, sample_bpmn_xml):
        xml = sample_bpmn_xml.replace('name="Yes"', 'name="Approved"', 1).replace('name="No"', 'name="Rejected"', 1)
        xml = xml.replace('value="Yes"', 'value="Approved"', 1).replace('value="No"', 'value="Rejected"', 1)
        _, rules, _ = _run(xml)
        condition_values = {r.conditions[0].value for r in rules}
        assert condition_values == {True, False}

    def test_repeated_same_condition_with_same_value_is_deduplicated(self):
        _, rules, _ = _run(REPEATED_CONDITION_SAME_VALUE_BPMN)
        activating_rules = [rule for rule in rules if rule.trigger_atoms]
        assert len(activating_rules) == 1
        assert len(activating_rules[0].conditions) == 1
        assert activating_rules[0].conditions[0].predicate.name == "Is_the_system_used_in_public_spaces"
        assert activating_rules[0].conditions[0].value is True

    def test_contradictory_repeated_condition_path_is_skipped(self):
        _, rules, _ = _run(REPEATED_CONDITION_CONTRADICTION_BPMN)
        assert [rule for rule in rules if rule.trigger_atoms] == []


class TestSuperiority:
    def test_one_superiority_relation(self, sample_bpmn_xml):
        _, _, superiority = _run(sample_bpmn_xml)
        assert len(superiority) == 1

    def test_superiority_format(self, sample_bpmn_xml):
        _, _, superiority = _run(sample_bpmn_xml)
        # Must follow "r1 > r2." pattern
        assert superiority[0].strip().endswith(".")
        assert ">" in superiority[0]
