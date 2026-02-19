from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from collections import deque

from src.transformations.bpmn_parser import Node, ReducedEdge
from src.transformations.rule_ir import RuleIR, Condition, Action, RelationAtom, DataAtom
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


def _action_from_deontic_props(props: Dict[str, str], task_id: str) -> Tuple[Action, Tuple[RelationAtom, ...], Tuple[DataAtom, ...]]:
    """
    Build a rich Action + RelationAtoms + DataAtoms from compliance props.
    """
    dtype  = (props.get("compliance_deonticType") or "unknown").strip().lower()
    did    = (props.get("compliance_deonticId")   or "NO_ID").strip()
    agent  = to_symbol(props.get("compliance_agent")  or "x")
    action = to_symbol(props.get("compliance_action") or "")
    obj    = to_symbol(props.get("compliance_object")  or "")
    reg    = to_symbol(props.get("compliance_regulation") or "")
    art    = (props.get("compliance_article")   or "").strip()
    par    = (props.get("compliance_paragraph") or "").strip()
    uri    = (props.get("compliance_regulationURI") or "").strip()
    risk   = (props.get("compliance_riskLevel") or "").strip()
    bind   = (props.get("compliance_bindingForce") or "").strip()

    # Canonical action node id (e.g. obl_001 or task_Activity_07zrvnr)
    node_id = to_symbol(did) if did != "NO_ID" else f"task_{to_symbol(task_id)}"

    main_action = Action(actor=agent, name=f"{dtype.upper()}|{node_id}|{action}|{obj}")

    relations: List[RelationAtom] = [
        RelationAtom(predicate="performsAction", subject=agent,   object=node_id),
        RelationAtom(predicate="actsOn",         subject=node_id, object=obj),
    ]

    data: List[DataAtom] = [
        DataAtom(predicate="hasDeonticType",  subject=node_id, value=dtype),
        DataAtom(predicate="hasDeonticId",    subject=node_id, value=did),
        DataAtom(predicate="hasBindingForce", subject=node_id, value=bind),
        DataAtom(predicate="fromRegulation",  subject=node_id, value=reg),
        DataAtom(predicate="fromArticle",     subject=node_id, value=art),
        DataAtom(predicate="fromParagraph",   subject=node_id, value=par),
    ]

    if uri:
        data.append(DataAtom(predicate="regulationURI", subject=node_id, value=uri, datatype="xsd:anyURI"))
    if risk:
        data.append(DataAtom(predicate="hasRiskLevel", subject=node_id, value=risk))

    return main_action, tuple(relations), tuple(data)

def build_rule_ir_from_path(
    path_edges: List[ReducedEdge],
    nodes: Dict[str, Node],
    rid: str,
    task_props: TaskProps,
    *,
    allowed_deontic: Optional[set[str]] = None,
    ignore_non_compliance_tasks: bool = True,
) -> RuleIR:
    conds: List[Condition] = []
    actions: List[Action] = []
    all_relations: List[RelationAtom] = []
    all_data: List[DataAtom] = []

    if allowed_deontic is None:
        allowed_deontic = {
            "obligation", "prohibition", "permission",
            "recommendation", "recommendation_not",
        }

    for e in path_edges:
        # Conditions from exclusiveGateway
        if nodes[e.src].type == "exclusiveGateway":
            gw_props = task_props.get(e.src, {})

            if gw_props.get("gw_conditionStatement"):
                # Use annotated condition statement (preferred)
                statement  = to_symbol(gw_props["gw_conditionStatement"])
                true_label = gw_props.get("gw_trueBranch",  "Yes")
                value = (e.guard.lower() == true_label.lower()) if e.guard else False
                conds.append(Condition(actor="x", predicate=statement, value=value))
            elif e.guard in {"Yes", "No"}:
                # Fallback: parse gateway name
                actor, pred = _split_actor_predicate(nodes[e.src].name)
                conds.append(Condition(actor=actor, predicate=pred, value=(e.guard == "Yes")))

        # Actions from tasks
        for task_id in e.tasks:
            props = task_props.get(task_id)

            if not props:
                if ignore_non_compliance_tasks:
                    continue
                actions.append(Action(actor="x", name=to_symbol(task_id)))
                continue

            dtype = (props.get("compliance_deonticType") or "").strip().lower()
            if dtype and dtype not in allowed_deontic:
                continue

            action, rels, dats = _action_from_deontic_props(props, task_id)
            actions.append(action)
            all_relations.extend(rels)
            all_data.extend(dats)

    # dedup conditions (preserve order)
    seen_c: set = set()
    out_c: List[Condition] = []
    for c in conds:
        key = (c.actor, c.predicate, c.value)
        if key not in seen_c:
            seen_c.add(key)
            out_c.append(c)

    # dedup actions (preserve order)
    seen_a: set = set()
    out_a: List[Action] = []
    for a in actions:
        key = (a.actor, a.name)
        if key not in seen_a:
            seen_a.add(key)
            out_a.append(a)

    return RuleIR(
        rid=rid,
        conditions=tuple(out_c),
        actions=tuple(out_a),
        relations=tuple(all_relations),
        data_atoms=tuple(all_data),
    )

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
