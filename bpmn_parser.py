"""
Parse a BPMN XML (Camunda Modeler style) into a *reduced* directed graph
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET


# -----------------------------
# Data model
# -----------------------------

@dataclass(frozen=True)
class Node:
    id: str
    type: str  # startEvent, endEvent, exclusiveGateway, task, parallelGateway, etc.
    name: str = ""


@dataclass(frozen=True)
class ReducedEdge:
    src: str
    dst: str
    guard: Optional[str]
    # NOTE: tasks are task IDs now (e.g., Activity_07zrvnr), not labels
    tasks: Tuple[str, ...]
    via_flows: Tuple[str, ...]


# -----------------------------
# XML helpers
# -----------------------------

def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag
# Complexity: Time O(1), Space O(1).


def _get_nsmap(root: ET.Element) -> Dict[str, str]:
    """
    Tries to recover namespace URIs from root attributes like:
      xmlns:zeebe="http://camunda.org/schema/zeebe/1.0"
    """
    ns: Dict[str, str] = {}
    for k, v in root.attrib.items():
        if k.startswith("xmlns:"):
            ns[k.split(":", 1)[1]] = v
    return ns


# -----------------------------
# BPMN parsing (full graph + gateway order)
# -----------------------------

@dataclass(frozen=True)
class _Flow:
    id: str
    src: str
    dst: str
    name: Optional[str]


_KEEP_TYPES: Set[str] = {"startEvent", "endEvent", "exclusiveGateway"}


@dataclass(frozen=True)
class BpmnParseArtifacts:
    nodes: Dict[str, Node]
    flows: Dict[str, _Flow]
    outgoing: Dict[str, List[str]]
    incoming: Dict[str, List[str]]
    # exclusiveGateway -> [flow_id] (XML order)
    gateway_outgoing_order: Dict[str, List[str]]
    # exclusiveGateway -> {flow_id: idx} for O(1) index lookup
    gateway_outgoing_index: Dict[str, Dict[str, int]]
    # NEW: task_id -> {prop_name: prop_value}
    task_props: Dict[str, Dict[str, str]]


def parse_bpmn_full(xml: str) -> BpmnParseArtifacts:
    """
    Parse BPMN XML into:
      nodes: element_id -> Node
      flows: flow_id -> _Flow
      outgoing: element_id -> [flow_id]
      incoming: element_id -> [flow_id]
      gateway_outgoing_order/index: exclusiveGateway outgoing flow IDs in XML order.
      task_props: task_id -> {zeebe_property_name: zeebe_property_value}

    Notes:
    - Only first bpmn:process is considered.
    - BPMN-DI is ignored; semantics come from sequenceFlow sourceRef/targetRef.
    """
    root = ET.fromstring(xml)
    _ = _get_nsmap(root)  # not strictly needed because we use _local()

    # Find first process
    process_el: Optional[ET.Element] = None
    for el in root.iter():
        if _local(el.tag) == "process":
            process_el = el
            break
    if process_el is None:
        raise ValueError("No <bpmn:process> found")

    nodes: Dict[str, Node] = {}
    flows: Dict[str, _Flow] = {}
    outgoing: Dict[str, List[str]] = {}
    incoming: Dict[str, List[str]] = {}

    gateway_outgoing_order: Dict[str, List[str]] = {}
    gateway_outgoing_index: Dict[str, Dict[str, int]] = {}

    task_props: Dict[str, Dict[str, str]] = {}

    # 1) Nodes + gateway outgoing order + task properties
    for el in process_el:
        t = _local(el.tag)
        el_id = el.attrib.get("id")
        if not el_id:
            continue

        if t == "sequenceFlow":
            continue

        name = el.attrib.get("name", "") or ""
        nodes[el_id] = Node(id=el_id, type=t, name=name)

        # Gateway outgoing order (XML order)
        if t == "exclusiveGateway":
            outs: List[str] = []
            for child in el:
                if _local(child.tag) == "outgoing" and (child.text or "").strip():
                    outs.append(child.text.strip())
            if outs:
                gateway_outgoing_order[el_id] = outs
                gateway_outgoing_index[el_id] = {fid: i for i, fid in enumerate(outs)}

        # Zeebe properties for tasks (extensionElements -> properties -> property[name,value])
        if t == "task":
            props: Dict[str, str] = {}
            for ext in el:
                if _local(ext.tag) != "extensionElements":
                    continue
                for zprops in ext:
                    if _local(zprops.tag) != "properties":
                        continue
                    for zp in zprops:
                        if _local(zp.tag) != "property":
                            continue
                        k = (zp.attrib.get("name") or "").strip()
                        v = (zp.attrib.get("value") or "").strip()
                        if k:
                            props[k] = v
            if props:
                task_props[el_id] = props

    # 2) sequenceFlows
    for el in process_el:
        if _local(el.tag) != "sequenceFlow":
            continue
        fid = el.attrib.get("id")
        src = el.attrib.get("sourceRef")
        dst = el.attrib.get("targetRef")
        if not (fid and src and dst):
            continue
        name = el.attrib.get("name")
        flows[fid] = _Flow(id=fid, src=src, dst=dst, name=name)
        outgoing.setdefault(src, []).append(fid)
        incoming.setdefault(dst, []).append(fid)

    # Ensure every node has outgoing/incoming lists
    for nid in nodes.keys():
        outgoing.setdefault(nid, [])
        incoming.setdefault(nid, [])

    return BpmnParseArtifacts(
        nodes=nodes,
        flows=flows,
        outgoing=outgoing,
        incoming=incoming,
        gateway_outgoing_order=gateway_outgoing_order,
        gateway_outgoing_index=gateway_outgoing_index,
        task_props=task_props,
    )


def parse_bpmn_to_reduced_graph(
    xml: str,
) -> Tuple[
    Dict[str, Node],
    List[ReducedEdge],
    Dict[str, List[str]],
    Dict[str, Dict[str, int]],
    Dict[str, Dict[str, str]],  # task_props
]:
    """
    Return:
      kept_nodes, reduced_edges, gateway_outgoing_order, gateway_outgoing_index, task_props
    """
    art = parse_bpmn_full(xml)

    # Identify kept nodes
    kept: Dict[str, Node] = {
        nid: Node(id=n.id, type=n.type, name=(n.name or ""))
        for nid, n in art.nodes.items()
        if n.type in _KEEP_TYPES
    }

    # Sanity: start & end
    start_ids = [nid for nid, n in kept.items() if n.type == "startEvent"]
    end_ids = [nid for nid, n in kept.items() if n.type == "endEvent"]
    if len(start_ids) != 1:
        raise ValueError(f"Expected exactly 1 startEvent; got {len(start_ids)}")
    if len(end_ids) < 1:
        raise ValueError("Expected at least 1 endEvent")

    # Precompute task-ness for O(1)
    is_task: Dict[str, bool] = {nid: (n.type == "task") for nid, n in art.nodes.items()}

    reduced_edges_set: Set[ReducedEdge] = set()

    # Traverse from each kept node to reach other kept nodes
    for src_id in kept.keys():
        src_type = kept[src_id].type
        for first_flow_id in art.outgoing.get(src_id, []):
            f0 = art.flows[first_flow_id]
            guard = f0.name if src_type == "exclusiveGateway" else None

            initial_tasks: Tuple[str, ...] = ()
            if is_task.get(f0.dst, False):
                initial_tasks = (f0.dst,)

            _walk_from_flow(
                full_nodes=art.nodes,
                flows=art.flows,
                outgoing=art.outgoing,
                kept=kept,
                is_task=is_task,
                src_kept=src_id,
                current_node=f0.dst,
                guard=guard,
                tasks_acc=initial_tasks,
                via_flows_acc=(first_flow_id,),
                reduced_edges_out=reduced_edges_set,
            )

    reduced_edges = sorted(reduced_edges_set, key=lambda e: (e.src, e.dst, e.guard or "", e.tasks))
    return (
        kept,
        reduced_edges,
        art.gateway_outgoing_order,
        art.gateway_outgoing_index,
        art.task_props,
    )


def _walk_from_flow(
    *,
    full_nodes: Dict[str, Node],
    flows: Dict[str, _Flow],
    outgoing: Dict[str, List[str]],
    kept: Dict[str, Node],
    is_task: Dict[str, bool],
    src_kept: str,
    current_node: str,
    guard: Optional[str],
    tasks_acc: Tuple[str, ...],
    via_flows_acc: Tuple[str, ...],
    reduced_edges_out: Set[ReducedEdge],
    _seen: Optional[Set[Tuple[str, str]]] = None,
) -> None:
    """
    Recursive walk from a node until reaching a kept node.

    Optimization: _seen tracks (current_node, last_flow_id) not the whole prefix.
    This cuts memory and still prevents trivial cycles. It is conservative:
    - avoids infinite loops
    - may prune some distinct paths in highly cyclic BPMN models
      (acceptable for process diagrams intended as DAG-like flows).
    """
    if _seen is None:
        _seen = set()

    last_flow_id = via_flows_acc[-1] if via_flows_acc else ""
    state = (current_node, last_flow_id)
    if state in _seen:
        return
    _seen.add(state)

    # If we reached a kept node, emit reduced edge
    if current_node in kept and current_node != src_kept:
        reduced_edges_out.add(
            ReducedEdge(
                src=src_kept,
                dst=current_node,
                guard=guard,
                tasks=tasks_acc,
                via_flows=via_flows_acc,
            )
        )
        return

    # Otherwise, continue along all outgoing flows
    for fid in outgoing.get(current_node, []):
        f = flows[fid]
        nxt = f.dst

        new_tasks = tasks_acc
        if is_task.get(nxt, False):
            new_tasks = tasks_acc + (nxt,)

        _walk_from_flow(
            full_nodes=full_nodes,
            flows=flows,
            outgoing=outgoing,
            kept=kept,
            is_task=is_task,
            src_kept=src_kept,
            current_node=nxt,
            guard=guard,  # guard determined by first flow leaving src_kept if exclusiveGateway
            tasks_acc=new_tasks,
            via_flows_acc=via_flows_acc + (fid,),
            reduced_edges_out=reduced_edges_out,
            _seen=_seen,
        )
