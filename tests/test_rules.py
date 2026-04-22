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
        assert "hasLegalAction" in predicates
        assert "hasLegalObject" in predicates
        assert "hasObject" not in predicates

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
        relation_subjects = {rel.subject.name for rel in obligation_rule.relations}
        assert "isLegalAgentOf" not in relation_predicates
        assert "Agent_x" not in relation_subjects


class TestSuperiority:
    def test_one_superiority_relation(self, sample_bpmn_xml):
        _, _, superiority = _run(sample_bpmn_xml)
        assert len(superiority) == 1

    def test_superiority_format(self, sample_bpmn_xml):
        _, _, superiority = _run(sample_bpmn_xml)
        # Must follow "r1 > r2." pattern
        assert superiority[0].strip().endswith(".")
        assert ">" in superiority[0]
