"""
Pipeline overview:
  1. Parse a BPMN (.bpmn XML) file and construct a reduced directed graph
     that preserves only normatively relevant control points
     (startEvent, endEvent, exclusiveGateway), collapsing tasks into edges.
  2. Enumerate all Start → End paths in the reduced graph using DFS.
     Each path corresponds to one complete execution scenario.
  3. Build a RuleIR object per path:
       - conditions are derived from exclusiveGateway guards,
       - actions (obligations/permissions/prohibitions) are derived from accumulated tasks (Zeebe props),
       - a linear superiority relation is generated according to BPMN order.
  4. Export:
       - Defeasible Deontic Logic (DDL, Governatori-style) rules to a text file,
       - SWRL rules to an executable OWL ontology,
       - LegalRuleML.
  5. Write a single human-readable artifact containing:
       - reduced nodes,
       - reduced edges,
       - enumerated paths,
       - generated DDL rules,
       - superiority relations.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from bpmn_parser import parse_bpmn_to_reduced_graph, Node, ReducedEdge
from path_extractor import enumerate_paths_and_build_ir
from ddl_exporter import rule_ir_to_ddl

from swrl_exporter import export_rules_to_owl
from legalruleml_exporter import export_rules_to_legalruleml


TaskProps = Dict[str, Dict[str, str]]  # task_id -> props


def _node_line(n: Node) -> str:
    return f"- {n.id:<18} | {n.type:<16} | {n.name}"


def _task_brief(task_id: str, task_props: TaskProps) -> str:
    """
    Pretty-print a task id using deontic fields if present.
    Example: Activity_07zrvnr{OBL_001:obligation}
    """
    props = task_props.get(task_id, {})
    did = props.get("compliance_deonticId")
    dt = props.get("compliance_deonticType")
    if did or dt:
        return f"{task_id}{{{did or 'NO_ID'}:{(dt or 'unknown')}}}"
    return task_id


def _edge_line(e: ReducedEdge, nodes: Dict[str, Node], task_props: TaskProps) -> str:
    guard = f" [{e.guard}]" if e.guard else ""
    src_name = nodes[e.src].name if e.src in nodes else ""
    dst_name = nodes[e.dst].name if e.dst in nodes else ""
    tasks = ", ".join(_task_brief(tid, task_props) for tid in e.tasks) if e.tasks else "(no tasks)"
    flows = ", ".join(e.via_flows) if e.via_flows else "(none)"
    return (
        f"{e.src}{guard} -> {e.dst} | "
        f"src='{src_name}' dst='{dst_name}' | "
        f"tasks: {tasks} | via_flows: {flows}"
    )


def _path_block(path: List[ReducedEdge], nodes: Dict[str, Node], task_props: TaskProps, idx: int) -> str:
    lines = [f"Path {idx}:"]
    for e in path:
        guard = f" [{e.guard}]" if e.guard else ""
        tasks = ", ".join(_task_brief(tid, task_props) for tid in e.tasks) if e.tasks else "(no tasks)"
        lines.append(f"  {e.src}{guard} -> {e.dst} | tasks: {tasks}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    in_path = Path(argv[0]) if len(argv) >= 1 else Path("example.bpmn")
    out_path = Path(argv[1]) if len(argv) >= 2 else Path("rules_DDL.txt")

    xml = in_path.read_text(encoding="utf-8")

    # BPMN -> reduced graph (+ gateway outgoing index + task_props)
    nodes, edges, gw_order, gw_index, task_props = parse_bpmn_to_reduced_graph(xml)

    # Reduced graph -> RuleIR rules (1 path = 1 rule) + superiority
    paths, rules_ir, superiority = enumerate_paths_and_build_ir(
        nodes=nodes,
        edges=edges,
        gateway_outgoing_index=gw_index,
        task_props=task_props,
        collect_paths=True,
    )

    out_lines: List[str] = []

    out_lines.append("=== REDUCED NODES ===")
    for nid in sorted(nodes.keys()):
        out_lines.append(_node_line(nodes[nid]))

    out_lines.append("\n=== REDUCED EDGES ===")
    for e in edges:
        out_lines.append(_edge_line(e, nodes, task_props))

    if paths is not None:
        out_lines.append(f"\n=== START → END PATHS ({len(paths)}) ===\n")
        for i, p in enumerate(paths, start=1):
            out_lines.append(_path_block(p, nodes, task_props, i))
            out_lines.append("")

    out_lines.append("% RULES")
    for ir in rules_ir:
        out_lines.append(rule_ir_to_ddl(ir))

    out_lines.append("\n% SUPERIORITY")
    for s in superiority:
        out_lines.append(s)

    out_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")

    # SWRL
    export_rules_to_owl(
        rules_ir,
        out_file="rules_swrl.owl",
        base_iri="http://example.org/bpmn2rules",
        task_predicate="task",
    )

    export_rules_to_legalruleml(
        rules_ir,
        superiority,
        out_file="rules_legalruleml.xml",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
