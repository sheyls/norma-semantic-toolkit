from __future__ import annotations

from typing import Dict, List, Tuple, Optional
from collections import deque
import re

from norma_engine.parsing.bpmn_parser import Node, ReducedEdge
from norma_engine.kg.builder import auto_deontic_id
from norma_engine.rules.ir import (
    Ref,
    RuleIR,
    Condition,
    Action,
    ClassAtom,
    RelationAtom,
    DataAtom,
)
from norma_engine.utils import to_symbol


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


_DTYPE_CLASS: dict = {
    "obligation":         "Obligation",
    "prohibition":        "Prohibition",
    "permission":         "Permission",
    "recommendation":     "Recommendation",
    "recommendation_not": "NegativeRecommendation",
    "fact":               "ConstitutiveRule",
}


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
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    key = to_symbol(raw or "").lower()
    target = mapping.get(key)
    return tbox(target) if target else None


def _norm_status_ref(raw: str) -> Optional[Ref]:
    mapping = {
        "active": "Active",
        "under_review": "UnderReview",
        "disputed": "Disputed",
        "superseded": "Superseded",
        "pending": "NotYetInForce",
    }
    key = to_symbol(raw or "").lower()
    target = mapping.get(key)
    return tbox(target) if target else None


def _extraction_method_ref(raw: str) -> Optional[Ref]:
    mapping = {
        "manual_lawyer": "ManualLawyer",
        "manual_analyst": "ManualAnalyst",
        "llm": "LLMExtraction",
        "pattern_matching": "PatternMatching",
        "rule_based": "RuleBased",
    }
    key = to_symbol(raw or "").lower()
    target = mapping.get(key)
    return tbox(target) if target else None


def _review_status_ref(raw: str) -> Optional[Ref]:
    mapping = {
        "approved": "Approved",
        "pending": "PendingReview",
        "none": "NotReviewed",
    }
    key = to_symbol(raw or "").lower()
    target = mapping.get(key)
    return tbox(target) if target else None


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_iso_date(value: str) -> bool:
    return bool(_ISO_DATE_RE.match((value or "").strip()))


def _add_string_data_atom(data: List[DataAtom], predicate_name: str, subject: Ref, value: str) -> None:
    if value:
        data.append(
            DataAtom(
                predicate=tbox(predicate_name),
                subject=subject,
                value=value,
            )
        )


def _add_dateish_data_atom(data: List[DataAtom], predicate_name: str, subject: Ref, value: str) -> None:
    if not value:
        return
    datatype = "xsd:date" if _is_iso_date(value) else "xsd:string"
    data.append(
        DataAtom(
            predicate=tbox(predicate_name),
            subject=subject,
            value=value,
            datatype=datatype,
        )
    )


def _action_from_deontic_props(
    props: Dict[str, str],
    task_id: str,
) -> Tuple[Action, Tuple[RelationAtom, ...], Tuple[DataAtom, ...], Tuple[ClassAtom, ...]]:
    dtype = (props.get("compliance_deonticType") or "unknown").strip().lower()
    raw_did = (props.get("compliance_deonticId") or "").strip()
    bpmn_name = (props.get("_bpmn_name") or "").strip()
    did = raw_did if raw_did else auto_deontic_id(dtype, bpmn_name, task_id)

    agent_raw = (props.get("compliance_agent") or "").strip()
    agent = to_symbol(agent_raw) if agent_raw else ""
    action_name = to_symbol(props.get("compliance_action") or "")
    obj = to_symbol(props.get("compliance_object") or "")
    reg = (props.get("compliance_regulation") or "").strip()
    art = (props.get("compliance_article") or "").strip()
    par = (props.get("compliance_paragraph") or "").strip()
    uri = (props.get("compliance_regulationURI") or "").strip()
    risk = (props.get("compliance_riskLevel") or "").strip()
    bind = (props.get("compliance_bindingForce") or "").strip()
    status = (props.get("compliance_status") or "").strip()
    extraction_method = (props.get("compliance_extractionMethod") or "").strip()
    review_status = (props.get("compliance_legalReview") or "").strip()
    norm_statement = (props.get("compliance_normStatement") or "").strip()
    fact_statement = (props.get("compliance_factStatement") or "").strip()
    trigger_condition = (
        props.get("compliance_triggerCondition")
        or props.get("compliance_condition")
        or ""
    ).strip()
    jurisdiction = (props.get("compliance_jurisdiction") or "").strip()
    effective_date = (props.get("compliance_effectiveDate") or "").strip()
    deadline = (props.get("compliance_deadline") or "").strip()
    exception = (props.get("compliance_exception") or "").strip()
    sanction = (props.get("compliance_sanction") or "").strip()
    confidence = (props.get("compliance_confidence") or "").strip()
    annotator = (props.get("compliance_annotator") or "").strip()
    annotation_date = (props.get("compliance_annotationDate") or "").strip()
    last_review_date = (props.get("compliance_lastReviewDate") or "").strip()

    node_id = to_symbol(did)

    agent_ref = abox(f"Agent_{agent}") if agent else None
    action_ref = abox(f"Action_{action_name}") if action_name else None
    object_ref = abox(f"Object_{obj}") if obj else None
    norm_ref = abox(node_id)
    source_ref = abox(f"Regulation_{to_symbol(reg)}") if reg else None
    annotator_ref = abox(f"Annotator_{to_symbol(annotator)}") if annotator else None
    activity_ref = (
        abox(f"AnnotationActivity_{node_id}")
        if annotator or annotation_date or confidence
        else None
    )

    action_summary = Action(
        subject=agent_ref or norm_ref,
        predicate=tbox(dtype.capitalize()) if False else None,  # summary only; ontology uses class membership in ABox
        name=f"{dtype.upper()}|{node_id}|{action_name}|{obj}",
    )

    relations: List[RelationAtom] = []

    if agent_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasLegalAgent"),
                subject=norm_ref,
                object=agent_ref,
            )
        )

    if action_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasLegalAction"),
                subject=norm_ref,
                object=action_ref,
            )
        )

    if obj:
        relations.append(
            RelationAtom(
                predicate=tbox("hasLegalObject"),
                subject=norm_ref,
                object=object_ref,
            )
        )

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
                predicate=tbox("hasComplianceCriticality"),
                subject=norm_ref,
                object=risk_ref,
            )
        )

    status_ref = _norm_status_ref(status)
    if status_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasNormStatus"),
                subject=norm_ref,
                object=status_ref,
            )
        )

    extraction_ref = _extraction_method_ref(extraction_method)
    if extraction_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasExtractionMethod"),
                subject=norm_ref,
                object=extraction_ref,
            )
        )

    review_ref = _review_status_ref(review_status)
    if review_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasReviewStatus"),
                subject=norm_ref,
                object=review_ref,
            )
        )

    if source_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("hasLegalSource"),
                subject=norm_ref,
                object=source_ref,
            )
        )
        relations.append(
            RelationAtom(
                predicate=tbox("wasDerivedFromSource"),
                subject=norm_ref,
                object=source_ref,
            )
        )

    if annotator_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("wasAttributedToAnnotator"),
                subject=norm_ref,
                object=annotator_ref,
            )
        )

    if activity_ref is not None:
        relations.append(
            RelationAtom(
                predicate=tbox("wasGeneratedByAnnotationActivity"),
                subject=norm_ref,
                object=activity_ref,
            )
        )
        if annotator_ref is not None:
            relations.append(
                RelationAtom(
                    predicate=tbox("wasAssociatedWithAnnotator"),
                    subject=activity_ref,
                    object=annotator_ref,
                )
            )
        if source_ref is not None:
            relations.append(
                RelationAtom(
                    predicate=tbox("usedLegalSource"),
                    subject=activity_ref,
                    object=source_ref,
                )
            )

    # Recover the human-readable labels before symbolisation
    agent_label_raw  = agent_raw
    action_label_raw = (props.get("compliance_action") or "").strip()
    object_label_raw = (props.get("compliance_object") or "").strip()

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

    _add_string_data_atom(data, "normStatement", norm_ref, norm_statement)
    _add_string_data_atom(data, "factStatement", norm_ref, fact_statement)
    _add_string_data_atom(data, "conditionTrigger", norm_ref, trigger_condition)
    _add_string_data_atom(data, "exception", norm_ref, exception)
    _add_string_data_atom(data, "sanction", norm_ref, sanction)
    _add_dateish_data_atom(data, "effectiveDate", norm_ref, effective_date)
    _add_string_data_atom(data, "deadline", norm_ref, deadline)
    _add_dateish_data_atom(data, "lastReviewDate", norm_ref, last_review_date)

    if agent_label_raw:
        _add_string_data_atom(data, "agentText", norm_ref, agent_label_raw)

    if action_label_raw:
        _add_string_data_atom(data, "actionText", norm_ref, action_label_raw)

    if object_label_raw:
        _add_string_data_atom(data, "objectText", norm_ref, object_label_raw)

    if uri:
        data.append(
            DataAtom(
                predicate=tbox("sourceURI"),
                subject=norm_ref,
                value=uri,
                datatype="xsd:anyURI",
            )
        )

    if activity_ref is not None:
        if confidence:
            data.append(
                DataAtom(
                    predicate=tbox("confidenceScore"),
                    subject=activity_ref,
                    value=confidence,
                    datatype="xsd:decimal",
                )
            )
        _add_dateish_data_atom(data, "annotationDate", activity_ref, annotation_date)

    # ClassAtom: asserts the OWL class for this norm in the SWRL head,
    # so a reasoner can derive the deontic modality from the rule alone.
    norm_class = _DTYPE_CLASS.get(dtype, "RegulativeNorm")
    class_atoms_list: List[ClassAtom] = [
        ClassAtom(class_ref=tbox(norm_class), subject=norm_ref),
    ]

    return action_summary, tuple(relations), tuple(data), tuple(class_atoms_list)


def _condition_truth_value(
    edge: ReducedEdge,
    gateway_id: str,
    gateway_props: Dict[str, str],
    gateway_outgoing_index: Dict[str, Dict[str, int]],
) -> Optional[bool]:
    true_label = (gateway_props.get("gw_trueBranch") or "Yes").strip().lower()
    false_label = (gateway_props.get("gw_falseBranch") or "No").strip().lower()
    guard = (edge.guard or "").strip().lower()

    if guard:
        if guard == true_label:
            return True
        if guard == false_label:
            return False
        if guard in {"yes", "true", "1", "sim", "ja", "oui", "approved"}:
            return True
        if guard in {"no", "false", "0", "nao", "não", "nein", "non", "rejected"}:
            return False

    chosen_flow = edge.via_flows[0] if edge.via_flows else None
    flow_positions = gateway_outgoing_index.get(gateway_id, {})
    if chosen_flow and len(flow_positions) == 2:
        pos = flow_positions.get(chosen_flow)
        if pos == 0:
            return True
        if pos == 1:
            return False

    return None


def build_rule_ir_from_path(
    path_edges: List[ReducedEdge],
    nodes: Dict[str, Node],
    rid: str,
    task_props: TaskProps,
    *,
    gateway_outgoing_index: Optional[Dict[str, Dict[str, int]]] = None,
    allowed_deontic: Optional[set[str]] = None,
    ignore_non_compliance_tasks: bool = True,
) -> RuleIR:
    conds: List[Condition] = []
    actions: List[Action] = []
    all_relations: List[RelationAtom] = []
    all_data: List[DataAtom] = []
    all_class_atoms: List[ClassAtom] = []

    if allowed_deontic is None:
        allowed_deontic = {
            "obligation",
            "prohibition",
            "permission",
            "recommendation",
            "recommendation_not",
            "fact",
        }
    if gateway_outgoing_index is None:
        gateway_outgoing_index = {}

    for e in path_edges:
        if nodes[e.src].type == "exclusiveGateway":
            gw_props = task_props.get(e.src, {})
            value = _condition_truth_value(e, e.src, gw_props, gateway_outgoing_index)

            if gw_props.get("gw_conditionStatement"):
                statement  = to_symbol(gw_props["gw_conditionStatement"])
                if value is not None:
                    conds.append(
                        Condition(
                            predicate=rules(statement),
                            subject=v("x"),
                            value=value,
                        )
                    )

            elif value is not None:
                # Use the full gateway name via to_symbol for consistent predicate naming
                # (same as the gw_conditionStatement path above, avoids duplicate nodes)
                gw_name   = nodes[e.src].name or ""
                statement = to_symbol(gw_name) if gw_name else "unnamed"
                conds.append(
                    Condition(
                        predicate=rules(statement),
                        subject=v("x"),
                        value=value,
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

            action, rels, dats, cats = _action_from_deontic_props(props, task_id)
            actions.append(action)
            all_relations.extend(rels)
            all_data.extend(dats)
            all_class_atoms.extend(cats)

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

    seen_ca = set()
    out_ca: List[ClassAtom] = []
    for ca in all_class_atoms:
        key = (
            ca.class_ref.kind, ca.class_ref.name,
            ca.subject.kind, ca.subject.name,
        )
        if key not in seen_ca:
            seen_ca.add(key)
            out_ca.append(ca)

    return RuleIR(
        rid=rid,
        conditions=tuple(out_c),
        actions=tuple(out_a),
        relations=tuple(out_r),
        data_atoms=tuple(out_d),
        class_atoms=tuple(out_ca),
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

            ir = build_rule_ir_from_path(
                stack,
                nodes,
                rid,
                task_props,
                gateway_outgoing_index=gateway_outgoing_index,
            )
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
