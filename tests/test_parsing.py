"""
Layer 1 — BPMN parsing tests.

Tests that bpmn_parser correctly extracts nodes, reduced edges,
gateway ordering, and Zeebe compliance properties.
"""

import pytest
from norma_engine.parsing.bpmn_parser import parse_bpmn_to_reduced_graph, parse_bpmn_full


class TestParseBpmnFull:
    def test_finds_all_elements(self, sample_bpmn_xml):
        art = parse_bpmn_full(sample_bpmn_xml)
        types = {n.type for n in art.nodes.values()}
        assert "startEvent"       in types
        assert "endEvent"         in types
        assert "exclusiveGateway" in types
        assert "task"             in types

    def test_task_zeebe_props_extracted(self, sample_bpmn_xml):
        art = parse_bpmn_full(sample_bpmn_xml)
        props = art.task_props.get("Task_OBL")
        assert props is not None
        assert props["compliance_deonticType"] == "obligation"
        assert props["compliance_agent"]       == "AI owner"
        assert props["compliance_article"]     == "50"

    def test_gateway_zeebe_props_extracted(self, sample_bpmn_xml):
        art = parse_bpmn_full(sample_bpmn_xml)
        props = art.task_props.get("GW_1")
        assert props is not None
        assert props["gw_conditionStatement"] == "Generation of synthetic content?"
        assert props["gw_trueBranch"]         == "Yes"
        assert props["gw_falseBranch"]        == "No"

    def test_gateway_outgoing_order_preserved(self, sample_bpmn_xml):
        art = parse_bpmn_full(sample_bpmn_xml)
        order = art.gateway_outgoing_order.get("GW_1", [])
        assert len(order) == 2
        # Yes branch (Flow_gw_obl) must come before No branch (Flow_gw_rec)
        assert order.index("Flow_gw_obl") < order.index("Flow_gw_rec")


class TestReducedGraph:
    def test_reduced_nodes_only_control_points(self, sample_bpmn_xml):
        nodes, edges, _, _, _ = parse_bpmn_to_reduced_graph(sample_bpmn_xml)
        types = {n.type for n in nodes.values()}
        # Tasks must not appear in the reduced graph
        assert "task" not in types
        assert "startEvent"       in types
        assert "endEvent"         in types
        assert "exclusiveGateway" in types

    def test_tasks_accumulated_on_edges(self, sample_bpmn_xml):
        _, edges, _, _, _ = parse_bpmn_to_reduced_graph(sample_bpmn_xml)
        # Each edge from the gateway should carry exactly one task
        gw_edges = [e for e in edges if e.src == "GW_1"]
        assert len(gw_edges) == 2
        for e in gw_edges:
            assert len(e.tasks) == 1

    def test_guard_labels_on_gateway_edges(self, sample_bpmn_xml):
        _, edges, _, _, _ = parse_bpmn_to_reduced_graph(sample_bpmn_xml)
        gw_edges = {e.guard for e in edges if e.src == "GW_1"}
        assert "Yes" in gw_edges
        assert "No"  in gw_edges

    def test_exactly_one_start_and_one_end(self, sample_bpmn_xml):
        nodes, _, _, _, _ = parse_bpmn_to_reduced_graph(sample_bpmn_xml)
        starts = [n for n in nodes.values() if n.type == "startEvent"]
        ends   = [n for n in nodes.values() if n.type == "endEvent"]
        assert len(starts) == 1
        assert len(ends)   == 1
