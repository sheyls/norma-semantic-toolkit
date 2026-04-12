from __future__ import annotations

from typing import Dict, List, Tuple, Optional
from collections import deque

from norma.parsing.bpmn_parser import Node, ReducedEdge
from norma.rules.ir import (
    Ref,
    RuleIR,
    Condition,
    Action,
    RelationAtom,
    DataAtom,
)
from norma.utils import to_symbol


TaskProps = Dict[str, Dict[str, str]]  # task_id -> {prop_name: prop_value}


def v(name: str) -> Ref:
    return Ref("var", to_symbol(name))


def abox(name: str) -> Ref:
    return Ref("abox", to_symbol(name))


def tbox(name: str) -> Ref:
    return Ref("tbox", to_symbol(name))


def rules(name: str) -> Ref:
    return Ref("rules", to_symbol(name))


def compute_min_depths_from_start(
    nodes: Dict[str, Node],
    edges: List[ReducedEdge],
) -> Dict[str, int]:
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
        for nxt in adj.get(u, []):
            if nxt not in depth:
                depth[nxt] = depth[u] + 1
                q.append(nxt)

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
    raw = (gateway_name or "").replace("\n", " ").strip()
    raw = raw[:-1] if raw.endswith("?") else raw
    parts = raw.split(None, 1)

    if len(parts) == 2:
        actor, pred = parts[0], parts[1]
        return actor, pred.replace(" ", "")

    return "x", raw.replace(" ", "") or "unnamed"


def _binding_force_ref(raw: str) -> Optional[Ref]:
    mapping = {
        "hard_law": "HardLaw",
        "soft_law": "SoftLaw",
        "internal_policy": "InternalPolicy",
        "contractual": "Contractual",
    }
    key = to_symbol(raw or "").lower()
    target = mapping.get(key)
    return tbox(target) if target else None


def _risk_level_ref(raw: str) -> Optional[Ref]:
    mapping = {
        "critical": "CriticalRisk",
        "high": "HighRisk",
        "medium": "MediumRisk",
        "low": "LowRisk",
    }
    key = to_symbol(raw or "").lower()
    target = mapping.get(key)
    return tbox(target) if target else None


def _action_from_deontic_props(
    props: Dict[str, str],
    task_id: str,
) -> Tuple[Action, Tuple[RelationAtom, ...], Tuple[DataAtom, ...]]:
    dtype = (props.get("compliance_deonticType") or "unknown").strip().lower()
    did = (props.get("compliance_deonticId") or "NO_ID").strip()

    agent = to_symbol(props.get("compliance_agent") or "x")
    action_name = to_symbol(props.get("compliance_action") or "")
    obj = to_symbol(props.get("compliance_object") or "")
    reg = (props.get("compliance_regulation") or "").strip()
    art = (props.get("compliance_article") or "").strip()
    par = (props.get("compliance_paragraph") or "").strip()
    uri = (props.get("compliance_regulationURI") or "").strip()
    risk = (props.get("compliance_riskLevel") or "").strip()
    bind = (props.get("compliance_bindingForce") or "").strip()

    node_id = to_symbol(did) if did != "NO_ID" else f"task_{to_symbol(task_id)}"

    agent_ref = abox(f"Agent_{agent}")
    object_ref = abox(f"Object_{obj}")
    norm_ref = abox(node_id)

    action_summary = Action(
        subject=agent_ref,
        predicate=tbox(dtype.capitalize()) if False else None,  # summary only; ontology uses class membership in ABox
        name=f"{dtype.upper()}|{node_id}|{action_name}|{obj}",
    )

    relations: List[RelationAtom] = [
        RelationAtom(
            predicate=tbox("performsAction"),
            subject=agent_ref,
            object=norm_ref,
        ),
        RelationAtom(
            predicate=tbox("actsOn"),
            subject=norm_ref,
            object=object_ref,
        ),
    ]

    bind_ref = _binding_force_ref(bind)
    if bind_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasBindingForce"),
                subject=norm_ref,
                object=bind_ref,
            )
        )

    risk_ref = _risk_level_ref(risk)
    if risk_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasRiskLevel"),
                subject=norm_ref,
                object=risk_ref,
            )
        )

    data: List[DataAtom] = [
        DataAtom(
            predicate=tbox("deonticId"),
            subject=norm_ref,
            value=did,
        ),
        DataAtom(
            predicate=tbox("fromRegulation"),
            subject=norm_ref,
            value=reg,
        ),
        DataAtom(
            predicate=tbox("fromArticle"),
            subject=norm_ref,
            value=art,
        ),
        DataAtom(
            predicate=tbox("fromParagraph"),
            subject=norm_ref,
            value=par,
        ),
    ]

    if uri:
        data.append(
            DataAtom(
                predicate=tbox("sourceURI"),
                subject=norm_ref,
                value=uri,
                datatype="xsd:anyURI",
            )
        )

    return action_summary, tuple(relations), tuple(data)


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
            "obligation",
            "prohibition",
            "permission",
            "recommendation",
            "recommendation_not",
            "fact",
        }

    for e in path_edges:
        if nodes[e.src].type == "exclusiveGateway":
            gw_props = task_props.get(e.src, {})

            if gw_props.get("gw_conditionStatement"):
                statement = to_symbol(gw_props["gw_conditionStatement"])
                true_label = gw_props.get("gw_trueBranch", "Yes")
                value = (e.guard.lower() == true_label.lower()) if e.guard else False

                conds.append(
                    Condition(
                        predicate=rules(statement),
                        subject=v("x"),
                        value=value,
                    )
                )

            elif e.guard in {"Yes", "No"}:
                actor, pred = _split_actor_predicate(nodes[e.src].name)
                conds.append(
                    Condition(
                        predicate=rules(pred),
                        subject=v(actor),
                        value=(e.guard == "Yes"),
                    )
                )

        for task_id in e.tasks:
            props = task_props.get(task_id)

            if not props:
                if ignore_non_compliance_tasks:
                    continue
                actions.append(
                    Action(
                        subject=v("x"),
                        name=to_symbol(task_id),
                    )
                )
                continue

            dtype = (props.get("compliance_deonticType") or "").strip().lower()
            if dtype and dtype not in allowed_deontic:
                continue

            action, rels, dats = _action_from_deontic_props(props, task_id)
            actions.append(action)
            all_relations.extend(rels)
            all_data.extend(dats)

    seen_c = set()
    out_c: List[Condition] = []
    for c in conds:
        key = (c.predicate.kind, c.predicate.name, c.subject.kind, c.subject.name, c.value)
        if key not in seen_c:
            seen_c.add(key)
            out_c.append(c)

    seen_a = set()
    out_a: List[Action] = []
    for a in actions:
        pred_key = None if a.predicate is None else (a.predicate.kind, a.predicate.name)
        key = (a.subject.kind, a.subject.name, pred_key, a.name)
        if key not in seen_a:
            seen_a.add(key)
            out_a.append(a)

    seen_r = set()
    out_r: List[RelationAtom] = []
    for r in all_relations:
        key = (
            r.predicate.kind, r.predicate.name,
            r.subject.kind, r.subject.name,
            r.object.kind, r.object.name,
        )
        if key not in seen_r:
            seen_r.add(key)
            out_r.append(r)

    seen_d = set()
    out_d: List[DataAtom] = []
    for d in all_data:
        key = (
            d.predicate.kind, d.predicate.name,
            d.subject.kind, d.subject.name,
            d.value, d.datatype,
        )
        if key not in seen_d:
            seen_d.add(key)
            out_d.append(d)

    return RuleIR(
        rid=rid,
        conditions=tuple(out_c),
        actions=tuple(out_a),
        relations=tuple(out_r),
        data_atoms=tuple(out_d),
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
        out_edges.sort(
            key=lambda ed: _edge_priority(ed, nodes, depth_map, gateway_outgoing_index)
        )

    paths_out: Optional[List[List[ReducedEdge]]] = [] if collect_paths else None
    rules_ir: List[RuleIR] = []
    superiority: List[str] = []

    last_rule: Optional[str] = None
    pid = 0

    def dfs(cur: str, stack: List[ReducedEdge], visited: set[str]) -> None:
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