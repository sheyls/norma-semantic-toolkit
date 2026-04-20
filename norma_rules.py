#!/usr/bin/env python3
"""
norma_rules.py
==============
NORMA Rule Extraction — BPMN file →  SWRL/OWL.

Builds a reduced directed graph from an annotated BPMN file, enumerates
all start→end paths via DFS (one path = one execution scenario = one rule),
and exports the resulting RuleIR objects to three complementary formats.

Usage
-----
python norma_rules.py regulations/eu-ai-act/bpmn/art50-art95.bpmn
python norma_rules.py path/to/file.bpmn outputs/my_rules.txt
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Dict

from norma.parsing.bpmn_parser import parse_bpmn_to_reduced_graph, Node, ReducedEdge
from norma.rules.extractor import enumerate_paths_and_build_ir
from norma.exporters.swrl import export_rules_to_owl


TaskProps = Dict[str, Dict[str, str]]  # task_id -> props


# =============================================================================
# Formatting helpers (used only for the human-readable DDL report)
# =============================================================================

def _node_line(n: Node) -> str:
    return f"- {n.id:<18} | {n.type:<16} | {n.name}"


def _task_brief(task_id: str, task_props: TaskProps) -> str:
    """Pretty-print a task id with its deontic fields if annotated."""
    from norma.kg.builder import auto_deontic_id
    props = task_props.get(task_id, {})
    dt    = props.get("compliance_deonticType") or ""
    raw   = (props.get("compliance_deonticId") or "").strip()
    name  = (props.get("_bpmn_name") or "").strip()
    did   = raw if raw else (auto_deontic_id(dt, name, task_id) if dt else "")
    if did or dt:
        return f"{task_id}{{{did or '?'}:{dt or 'unknown'}}}"
    return task_id


def _edge_line(e: ReducedEdge, nodes: Dict[str, Node], task_props: TaskProps) -> str:
    guard    = f" [{e.guard}]" if e.guard else ""
    src_name = nodes[e.src].name if e.src in nodes else ""
    dst_name = nodes[e.dst].name if e.dst in nodes else ""
    tasks    = ", ".join(_task_brief(t, task_props) for t in e.tasks) if e.tasks else "(no tasks)"
    flows    = ", ".join(e.via_flows) if e.via_flows else "(none)"
    return (
        f"{e.src}{guard} -> {e.dst} | "
        f"src='{src_name}' dst='{dst_name}' | "
        f"tasks: {tasks} | via_flows: {flows}"
    )


def _path_block(path: List[ReducedEdge], task_props: TaskProps, idx: int) -> str:
    lines = [f"Path {idx}:"]
    for e in path:
        guard = f" [{e.guard}]" if e.guard else ""
        tasks = ", ".join(_task_brief(t, task_props) for t in e.tasks) if e.tasks else "(no tasks)"
        lines.append(f"  {e.src}{guard} -> {e.dst} | tasks: {tasks}")
    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

ABOX_BASE = "https://w3id.org/norma-abox"


def _default_iris(in_path: Path) -> tuple[str, str]:
    """Derive stable (abox_iri, rules_iri) from the BPMN input path.

    For regulations/<pack>/bpmn/<file>.bpmn:
      abox_iri  = https://w3id.org/norma-abox/<pack>
      rules_iri = https://w3id.org/norma-abox/<pack>/rules
    """
    parts = in_path.parts
    if "regulations" in parts:
        idx = parts.index("regulations")
        if idx + 1 < len(parts):
            pack = parts[idx + 1].lower().replace("_", "-")
            return f"{ABOX_BASE}/{pack}", f"{ABOX_BASE}/{pack}/rules"
    stem = in_path.stem.lower().replace("_", "-")
    return f"{ABOX_BASE}/{stem}", f"{ABOX_BASE}/{stem}/rules"


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="NORMA Rule Extraction — BPMN → SWRL/OWL"
    )
    parser.add_argument("input",  nargs="?",
        default="regulations/eu-ai-act/bpmn/art50-art95.bpmn",
        help="Input .bpmn file")
    parser.add_argument("output", nargs="?",
        default=None,
        help="Output SWRL/OWL file (default: <input-stem>.swrl.owl alongside input)")
    parser.add_argument("--rules-iri", default=None,
        help="Ontology IRI for the SWRL file (default: derived from input path)")
    parser.add_argument("--abox-iri", default=None,
        help="ABox IRI to owl:imports in the SWRL file (default: derived from input path)")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    default_abox, default_rules = _default_iris(in_path)
    rules_iri = args.rules_iri or default_rules
    abox_iri  = args.abox_iri  or default_abox

    if args.output:
        swrl_path = Path(args.output)
    else:
        swrl_path = in_path.with_suffix("").with_suffix(".swrl.owl")

    swrl_path.parent.mkdir(parents=True, exist_ok=True)

    xml = in_path.read_text(encoding="utf-8")

    # BPMN → reduced graph
    nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(xml)

    # Reduced graph → RuleIR (1 path per rule) + superiority relations
    paths, rules_ir, superiority = enumerate_paths_and_build_ir(
        nodes=nodes,
        edges=edges,
        gateway_outgoing_index=gw_index,
        task_props=task_props,
        collect_paths=True,
    )


    # ── SWRL/OWL ─────────────────────────────────────────────────────────────
    export_rules_to_owl(
        rules_ir,
        out_file=str(swrl_path),
        rules_iri=rules_iri,
        abox_iri=abox_iri,
    )
    print(f"[✓] SWRL/OWL:    {swrl_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
