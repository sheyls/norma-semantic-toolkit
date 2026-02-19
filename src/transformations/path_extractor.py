from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from collections import deque

from src.transformations.bpmn_parser import Node, ReducedEdge
from src.transformations.rule_ir import RuleIR, Condition, Action
from utils import to_symbol


TaskProps = Dict[str, Dict[str, str]]  # task_id -> {prop_name: prop_value}


def compute_min_depths_from_start(nodes: Dict[str, Node], edges: List[ReducedEdge]) -> Dict[str, int]:
    start_ids = [nid for nid, n in nodes.items() if n.type == "startEvent"]
    if len(start_ids) != 1:
        raise ValueError("Expected exactly one startEvent")
    start = start_ids[0]

    adj: Dict[str, List[str]] = {}
    for e in edges:
        adj.setdefault(e.src, []).append(e.dst)

    depth: Dict[str, int] = {start: 0}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if v not in depth:
                depth[v] = depth[u] + 1
                q.append(v)
    return depth


def _edge_priority(
    e: ReducedEdge,
    nodes: Dict[str, Node],
    depth_map: Dict[str, int],
    gateway_out_index: Dict[str, Dict[str, int]],
) -> Tuple[int, int]:
    BIG = 10**9
    if nodes[e.src].type != "exclusiveGateway":
        return (BIG, BIG)
    d = depth_map.get(e.src, BIG)
    chosen_flow = e.via_flows[0] if e.via_flows else None
    if not chosen_flow:
        return (d, BIG)
    return (d, gateway_out_index.get(e.src, {}).get(chosen_flow, BIG))


def _split_actor_predicate(gateway_name: str) -> Tuple[str, str]:
    """
    Expected style: "AIsystem generatesSyntethicContent?"
    We split on first whitespace: actor + rest (predicate with ? removed).
    Fallback: if no space, actor="x", predicate=normalized name.
    """
    raw = (gateway_name or "").replace("\n", " ").strip()
    raw = raw[:-1] if raw.endswith("?") else raw
    parts = raw.split(None, 1)
    if len(parts) == 2:
        actor, pred = parts[0], parts[1]
        pred = pred.replace(" ", "")
        return actor, pred
    return "x", raw.replace(" ", "") or "unnamed"


def _action_from_deontic_props(props: Dict[str, str]) -> Action:
    """
    Build an Action from Zeebe compliance properties.

    We keep it minimal and compatible with your existing SWRL exporter:
      - Action.actor = normalized compliance_agent
      - Action.name  = a canonical payload string with deontic+AoO (+legal trace)
        Example:
          OBL|OBL_001|marking_as_synthetic|AI_content|IA_act|4|2
    """
    dtype = (props.get("compliance_deonticType") or "").strip().lower()
    did = (props.get("compliance_deonticId") or "").strip()

    agent = (props.get("compliance_agent") or "x").strip()
    act = (props.get("compliance_action") or "").strip()
    obj = (props.get("compliance_object") or "").strip()

    reg = (props.get("compliance_regulation") or "").strip()
    art = (props.get("compliance_article") or "").strip()
    par = (props.get("compliance_paragraph") or "").strip()

    # normalize
    actor = to_symbol(agent)
    name = "|".join(
        [
            (dtype or "unknown").upper(),
            did or "NO_ID",
            to_symbol(act) if act else "NO_ACTION",
            to_symbol(obj) if obj else "NO_OBJECT",
            to_symbol(reg) if reg else "NO_REG",
            art or "NO_ART",
            par or "NO_PAR",
        ]
    )
    return Action(actor=actor, name=name)


def build_rule_ir_from_path(
    path_edges: List[ReducedEdge],
    nodes: Dict[str, Node],
    rid: str,
    task_props: TaskProps,
    *,
    # v0: if you want ONLY obligations, set {"obligation"}
    allowed_deontic: Optional[set[str]] = None,
    # if True: ignore tasks without compliance props
    ignore_non_compliance_tasks: bool = True,
) -> RuleIR:
    conds: List[Condition] = []
    actions: List[Action] = []

    if allowed_deontic is None:
        allowed_deontic = {"obligation", "prohibition", "permission"}

    for e in path_edges:
        # conditions from exclusiveGateway + guard
        if nodes[e.src].type == "exclusiveGateway" and e.guard in {"Yes", "No"}:
            actor, pred = _split_actor_predicate(nodes[e.src].name)
            conds.append(Condition(actor=actor, predicate=pred, value=(e.guard == "Yes")))

        # actions from tasks (task IDs)
        for task_id in e.tasks:
            props = task_props.get(task_id)

            if not props:
                if ignore_non_compliance_tasks:
                    continue
                # fallback: keep something, using the task_id as name
                actions.append(Action(actor="x", name=to_symbol(task_id)))
                continue

            dtype = (props.get("compliance_deonticType") or "").strip().lower()
            if dtype and dtype not in allowed_deontic:
                continue

            actions.append(_action_from_deontic_props(props))

    # dedup (preserve order)
    seen_c = set()
    out_c: List[Condition] = []
    for c in conds:
        key = (c.actor, c.predicate, c.value)
        if key not in seen_c:
            seen_c.add(key)
            out_c.append(c)

    seen_a = set()
    out_a: List[Action] = []
    for a in actions:
        key = (a.actor, a.name)
        if key not in seen_a:
            seen_a.add(key)
            out_a.append(a)

    return RuleIR(rid=rid, conditions=tuple(out_c), actions=tuple(out_a))


def enumerate_paths_and_build_ir(
    *,
    nodes: Dict[str, Node],
    edges: List[ReducedEdge],
    gateway_outgoing_index: Dict[str, Dict[str, int]],
    task_props: TaskProps,
    collect_paths: bool = False,
) -> Tuple[Optional[List[List[ReducedEdge]]], List[RuleIR], List[str]]:
    start_ids = [nid for nid, n in nodes.items() if n.type == "startEvent"]
    end_ids = {nid for nid, n in nodes.items() if n.type == "endEvent"}
    if len(start_ids) != 1:
        raise ValueError("Expected exactly one startEvent")
    start = start_ids[0]

    depth_map = compute_min_depths_from_start(nodes, edges)

    adj: Dict[str, List[ReducedEdge]] = {}
    for e in edges:
        adj.setdefault(e.src, []).append(e)
    for src, out_edges in adj.items():
        out_edges.sort(key=lambda ed: _edge_priority(ed, nodes, depth_map, gateway_outgoing_index))

    paths_out: Optional[List[List[ReducedEdge]]] = [] if collect_paths else None
    rules_ir: List[RuleIR] = []
    superiority: List[str] = []

    last_rule: Optional[str] = None
    pid = 0

    def dfs(cur: str, stack: List[ReducedEdge], visited: set[str]):
        nonlocal pid, last_rule
        if cur in end_ids:
            pid += 1
            rid = f"r{pid}"
            if paths_out is not None:
                paths_out.append(list(stack))

            ir = build_rule_ir_from_path(stack, nodes, rid, task_props)
            rules_ir.append(ir)

            if last_rule is not None:
                superiority.append(f"{last_rule} > {rid}.")
            last_rule = rid
            return

        if cur in visited:
            return
        visited.add(cur)
        for e in adj.get(cur, []):
            stack.append(e)
            dfs(e.dst, stack, visited)
            stack.pop()
        visited.remove(cur)

    dfs(start, [], set())
    return paths_out, rules_ir, superiority
