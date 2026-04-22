from __future__ import annotations

import dataclasses
import json
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from norma_engine.exporters.human_readable import rule_ir_to_human_readable
from norma_engine.exporters.swrl import export_rules_to_owl
from norma_engine.parsing.bpmn_parser import parse_bpmn_to_reduced_graph
from norma_engine.rules.extractor import enumerate_paths_and_build_ir
from norma_engine.rules.ir import RuleIR
from norma_engine.utils import to_symbol

try:
    from norma_engine.kg.builder import auto_deontic_id, parse_bpmn_folder, to_json, to_turtle

    KG_AVAILABLE = True
except ImportError:  # pragma: no cover
    KG_AVAILABLE = False

    def auto_deontic_id(dtype: str, bpmn_name: str, bpmn_id: str) -> str:  # type: ignore[misc]
        return bpmn_id

    def parse_bpmn_folder(_: Path):  # type: ignore[misc]
        raise RuntimeError("Knowledge-graph builder not available")

    def to_json(_: Any):  # type: ignore[misc]
        raise RuntimeError("Knowledge-graph builder not available")

    def to_turtle(_: Any, __: str, ___: str):  # type: ignore[misc]
        raise RuntimeError("Knowledge-graph builder not available")

try:
    from norma_engine.kg.normalizer import normalize as normalize_entities
    from norma_engine.kg.normalizer import canonical_norm_signature_from_props

    NORMALIZER_AVAILABLE = True
except ImportError:  # pragma: no cover
    NORMALIZER_AVAILABLE = False
    normalize_entities = None  # type: ignore[assignment]
    canonical_norm_signature_from_props = None  # type: ignore[assignment]

TASK_PROP_NORM_MAP = {
    "agent": "compliance_agent",
    "action": "compliance_action",
    "object": "compliance_object",
    "regulation": "compliance_regulation",
    "deontic_id": "compliance_deonticId",
    "condition_statement": "gw_conditionStatement",
}

NORM_FIELD_MAP = {
    "element_type": "compliance_elementType",
    "deontic_type": "compliance_deonticType",
    "norm_statement": "compliance_normStatement",
    "gw_condition_statement": "gw_conditionStatement",
    "gw_true_branch": "gw_trueBranch",
    "gw_false_branch": "gw_falseBranch",
    "agent": "compliance_agent",
    "action": "compliance_action",
    "object": "compliance_object",
    "fact_statement": "compliance_factStatement",
    "binding_force": "compliance_bindingForce",
    "regulation": "compliance_regulation",
    "article": "compliance_article",
    "paragraph": "compliance_paragraph",
    "original_text": "compliance_originalText",
    "regulation_uri": "compliance_regulationURI",
    "jurisdiction": "compliance_jurisdiction",
    "trigger_condition": "compliance_triggerCondition",
    "status": "compliance_status",
    "effective_date": "compliance_effectiveDate",
    "deadline": "compliance_deadline",
    "risk_level": "compliance_riskLevel",
    "sanction": "compliance_sanction",
    "exception": "compliance_exception",
    "extraction_method": "compliance_extractionMethod",
    "confidence": "compliance_confidence",
    "legal_review": "compliance_legalReview",
    "annotator": "compliance_annotator",
    "annotation_date": "compliance_annotationDate",
    "last_review_date": "compliance_lastReviewDate",
}


def apply_override_to_task_props(task_props: dict[str, dict[str, str]], override: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for elem_id, props in task_props.items():
        new_props = dict(props)
        for norm_field, prop_key in TASK_PROP_NORM_MAP.items():
            raw = new_props.get(prop_key, "")
            if raw and norm_field in override:
                canonical = override[norm_field].get(raw)
                if canonical:
                    new_props[prop_key] = canonical
        result[elem_id] = new_props
    return result


def canonicalize_task_prop_norm_ids(
    task_groups: list[tuple[Path, dict[str, dict[str, str]]]],
) -> list[tuple[Path, dict[str, dict[str, str]]]]:
    if not canonical_norm_signature_from_props:
        return task_groups

    first_norm_for_signature: dict[tuple[str, ...], str] = {}
    canonicalized: list[tuple[Path, dict[str, dict[str, str]]]] = []

    for bpmn_file, task_props in task_groups:
        next_props: dict[str, dict[str, str]] = {}
        for task_id, props in task_props.items():
            current = dict(props)
            dtype = (current.get("compliance_deonticType") or "").strip().lower()
            explicit = (current.get("compliance_deonticId") or "").strip()
            bpmn_name = (current.get("_bpmn_name") or "").strip()
            generated = explicit or (auto_deontic_id(dtype, bpmn_name, task_id) if dtype else "")

            if current.get("compliance_elementType") == "task" and generated:
                signature = canonical_norm_signature_from_props(current)
                if any(signature):
                    canonical_id = first_norm_for_signature.setdefault(signature, generated)
                    current["compliance_deonticId"] = canonical_id
            next_props[task_id] = current
        canonicalized.append((bpmn_file, next_props))

    return canonicalized


def rules_from_bpmn_dir(reg_dir: Path, override_path: Optional[Path] = None):
    bpmn_dir = reg_dir / "bpmn"
    if not bpmn_dir.is_dir():
        return [], {}

    override: dict[str, dict[str, str]] = {}
    if override_path and override_path.exists():
        loaded = json.loads(override_path.read_text(encoding="utf-8"))
        for key in TASK_PROP_NORM_MAP:
            override[key] = loaded.get(key, {})

    parsed_task_groups: list[tuple[Path, dict[str, dict[str, str]], dict, dict, dict]] = []
    for bpmn_file in sorted(bpmn_dir.glob("*.bpmn")):
        xml = bpmn_file.read_text(encoding="utf-8")
        nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(xml)
        for props in task_props.values():
            props.setdefault("_bpmn_source", bpmn_file.name)
        if override:
            task_props = apply_override_to_task_props(task_props, override)
        parsed_task_groups.append((bpmn_file, task_props, nodes, edges, gw_index))

    canonicalized_props = canonicalize_task_prop_norm_ids(
        [(bpmn_file, task_props) for bpmn_file, task_props, _, _, _ in parsed_task_groups]
    )

    rules_ir = []
    all_task_props: dict[str, dict[str, str]] = {}
    for (bpmn_file, _, nodes, edges, gw_index), (_, task_props) in zip(parsed_task_groups, canonicalized_props):
        all_task_props.update(task_props)
        _, ir, _ = enumerate_paths_and_build_ir(
            nodes=nodes,
            edges=edges,
            gateway_outgoing_index=gw_index,
            task_props=task_props,
        )
        rules_ir.extend(dataclasses.replace(rule, source=bpmn_file.name) for rule in ir)
    return rules_ir, all_task_props


def build_abox_from_dir(reg_dir: Path, abox_iri: str, override_file: Optional[Path] = None):
    if not KG_AVAILABLE:
        return None, None
    bpmn_dir = reg_dir / "bpmn"
    if not bpmn_dir.is_dir() or not any(bpmn_dir.glob("*.bpmn")):
        return None, None

    elements, _ = parse_bpmn_folder(bpmn_dir)
    records = to_json(elements)
    norm_report = None
    if NORMALIZER_AVAILABLE and normalize_entities:
        records, norm_report = normalize_entities(
            records,
            override_file=str(override_file) if override_file and override_file.exists() else None,
        )
    rules_ir, _ = rules_from_bpmn_dir(reg_dir, override_path=override_file)
    abox_ttl = to_turtle(records, str(bpmn_dir), abox_iri, rules_ir=rules_ir)
    return abox_ttl, norm_report


def export_swrl(rules_ir: list[RuleIR], abox_iri: str, rules_iri: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".swrl.owl", delete=False, mode="w") as tf:
        tmp_swrl = tf.name
    try:
        export_rules_to_owl(
            rules_ir,
            out_file=tmp_swrl,
            rules_iri=rules_iri,
            abox_iri=abox_iri,
        )
        return Path(tmp_swrl).read_text(encoding="utf-8")
    finally:
        Path(tmp_swrl).unlink(missing_ok=True)


def process_uploaded_bpmn(filename: str, xml: str) -> dict[str, Any]:
    stem = Path(filename).stem
    pack_name = stem.lower().replace(" ", "-").replace("_", "-")
    abox_iri = f"https://w3id.org/norma-abox/{pack_name}"
    rules_iri = f"{abox_iri}/rules"

    nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(xml)
    for props in task_props.values():
        props.setdefault("_bpmn_source", filename)
    _, raw_rules_ir, _ = enumerate_paths_and_build_ir(
        nodes=nodes,
        edges=edges,
        gateway_outgoing_index=gw_index,
        task_props=task_props,
    )
    rules_ir = [dataclasses.replace(rule, source=filename) for rule in raw_rules_ir]
    swrl_owl = export_swrl(rules_ir, abox_iri=abox_iri, rules_iri=rules_iri)

    abox_ttl: Optional[str] = None
    if KG_AVAILABLE:
        with tempfile.TemporaryDirectory() as tmpdir:
            bpmn_path = Path(tmpdir) / filename
            bpmn_path.write_text(xml, encoding="utf-8")
            elements, _ = parse_bpmn_folder(Path(tmpdir))
            records = to_json(elements)
            abox_ttl = to_turtle(records, str(bpmn_path.parent), abox_iri, rules_ir=rules_ir)

    return {
        "pack_name": pack_name,
        "abox_ttl": abox_ttl,
        "swrl_owl": swrl_owl,
        "rules_ir": rules_ir,
        "task_props": task_props,
    }


def pack_summary(name: str, pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "rule_count": len(pack["rules_ir"]),
        "has_abox": bool(pack["abox_ttl"]),
        "has_swrl": bool(pack["swrl_owl"]),
        "can_rebuild": bool(pack.get("reg_dir")),
    }


def norm_ids_in_rule(rule: RuleIR) -> list[str]:
    seen = set()
    ids = []
    for atom in rule.data_atoms:
        if atom.predicate.name == "deonticId" and atom.value not in seen:
            seen.add(atom.value)
            ids.append(atom.value)
    return ids


def norm_to_dict(norm_id: str, rule: RuleIR) -> dict[str, Any]:
    sym = to_symbol(norm_id)

    def dat(pred: str) -> Optional[str]:
        return next(
            (
                item.value
                for item in rule.data_atoms
                if item.predicate.name == pred and item.subject.name == sym
            ),
            None,
        )

    def rel_obj(pred: str) -> Optional[str]:
        return next(
            (
                rel.object.name
                for rel in rule.relations
                if rel.predicate.name == pred and rel.subject.name == sym
            ),
            None,
        )

    def rel_subj(pred: str) -> Optional[str]:
        return next(
            (
                rel.subject.name
                for rel in rule.relations
                if rel.predicate.name == pred and rel.object.name == sym
            ),
            None,
        )

    object_label = dat("objectText")
    if not object_label:
        raw = rel_obj("hasObject") or ""
        object_label = raw.replace("Object_", "").replace("_", " ").strip() or None

    agent_id = rel_subj("isLegalAgentOf")
    dtype = next(
        (class_atom.class_ref.name for class_atom in rule.class_atoms if class_atom.subject.name == sym),
        None,
    )

    return {
        "rule_id": rule.rid,
        "norm_id": norm_id,
        "deontic_type": dtype,
        "bpmn_source": rule.source,
        "conditions": [{"predicate": c.predicate.name, "value": c.value} for c in rule.conditions],
        "agent": agent_id,
        "action": dat("actionText"),
        "object": object_label,
        "binding_force": rel_obj("hasBindingForce"),
        "risk_level": rel_obj("hasComplianceCriticality"),
        "regulation": dat("fromRegulation"),
        "article": dat("fromArticle"),
        "paragraph": dat("fromParagraph"),
        "source_uri": dat("sourceURI"),
    }


def pack_graph_data(pack: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges = []
    seen_edges = set()
    seen_norm_ids = set()

    def add_node(node_id: str, label: str, node_type: str, meta: Optional[dict[str, Any]] = None) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label, "type": node_type}
            if meta:
                nodes[node_id].update(meta)

    def add_edge(source: str, target: str, label: str) -> None:
        key = (source, target, label)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({"source": source, "target": target, "label": label})

    for rule in pack["rules_ir"]:
        for norm_id in norm_ids_in_rule(rule):
            if norm_id in seen_norm_ids:
                continue
            seen_norm_ids.add(norm_id)
            norm_data = norm_to_dict(norm_id, rule)
            dtype = norm_data["deontic_type"] or "Norm"
            source = " · ".join(
                x
                for x in [
                    norm_data["regulation"] or "",
                    f"Art. {norm_data['article']}" if norm_data["article"] else "",
                ]
                if x
            )
            add_node(
                norm_id,
                norm_data["action"] or norm_id,
                dtype,
                {
                    "source": source,
                    "deontic_type": dtype,
                    "regulation": norm_data["regulation"],
                    "article": norm_data["article"],
                    "bpmn_source": norm_data["bpmn_source"],
                },
            )

            if norm_data["agent"]:
                agent_id = norm_data["agent"]
                add_node(agent_id, agent_id.replace("Agent_", "").replace("_", " ").title(), "Agent")
                add_edge(agent_id, norm_id, "performs")

            if norm_data["object"]:
                object_id = f"object::{norm_data['object']}"
                add_node(object_id, norm_data["object"], "Object")
                add_edge(norm_id, object_id, "acts on")

            for cond in norm_data["conditions"]:
                cond_id = f"cond::{cond['predicate']}"
                add_node(cond_id, cond["predicate"].replace("_", " "), "Condition")
                add_edge(cond_id, norm_id, "when true" if cond["value"] else "when false")

    return {"nodes": list(nodes.values()), "edges": edges}


def all_norms(pack: dict[str, Any]) -> dict[str, Any]:
    raw_props: dict[str, dict[str, str]] = pack.get("task_props", {})
    norm_to_cond_sets: dict[str, list[frozenset[tuple[str, bool]]]] = {}

    for rule in pack["rules_ir"]:
        rule_norm_ids = norm_ids_in_rule(rule)
        rule_cond_set = frozenset((cond.predicate.name, cond.value) for cond in rule.conditions)
        for norm_id in rule_norm_ids:
            norm_to_cond_sets.setdefault(norm_id, []).append(rule_cond_set)

    def minimal_conditions(norm_id: str) -> list[dict[str, Any]]:
        sets = norm_to_cond_sets.get(norm_id)
        if not sets:
            return []
        common = sets[0]
        for current in sets[1:]:
            common &= current
        return [
            {"predicate": pred, "label": pred.replace("_", " "), "value": val}
            for pred, val in sorted(common)
        ]

    def field(props: dict[str, str], key: str) -> str:
        return (props.get(key) or "").strip()

    result = []
    seen = set()
    for bpmn_id, props in raw_props.items():
        dtype = field(props, "compliance_deonticType").lower()
        bpmn_name = field(props, "_bpmn_name")
        raw_did = field(props, "compliance_deonticId")
        norm_id = raw_did or (auto_deontic_id(dtype, bpmn_name, bpmn_id) if dtype else bpmn_id)
        if norm_id in seen:
            continue
        seen.add(norm_id)
        result.append(
            {
                "rule_id": bpmn_id,
                "norm_id": norm_id,
                "bpmn_source": field(props, "_bpmn_source"),
                "element_type": field(props, "compliance_elementType") or "task",
                "deontic_type": dtype,
                "norm_statement": field(props, "compliance_normStatement"),
                "agent": field(props, "compliance_agent"),
                "action": field(props, "compliance_action"),
                "object": field(props, "compliance_object"),
                "fact_statement": field(props, "compliance_factStatement"),
                "binding_force": field(props, "compliance_bindingForce"),
                "gw_condition_statement": field(props, "gw_conditionStatement"),
                "gw_true_branch": field(props, "gw_trueBranch"),
                "gw_false_branch": field(props, "gw_falseBranch"),
                "regulation": field(props, "compliance_regulation"),
                "article": field(props, "compliance_article"),
                "paragraph": field(props, "compliance_paragraph"),
                "original_text": field(props, "compliance_originalText"),
                "regulation_uri": field(props, "compliance_regulationURI"),
                "trigger_condition": field(props, "compliance_triggerCondition"),
                "jurisdiction": field(props, "compliance_jurisdiction"),
                "effective_date": field(props, "compliance_effectiveDate"),
                "deadline": field(props, "compliance_deadline"),
                "status": field(props, "compliance_status"),
                "exception": field(props, "compliance_exception"),
                "sanction": field(props, "compliance_sanction"),
                "risk_level": field(props, "compliance_riskLevel"),
                "extraction_method": field(props, "compliance_extractionMethod"),
                "confidence": field(props, "compliance_confidence"),
                "legal_review": field(props, "compliance_legalReview"),
                "annotator": field(props, "compliance_annotator"),
                "annotation_date": field(props, "compliance_annotationDate"),
                "last_review_date": field(props, "compliance_lastReviewDate"),
                "conditions": minimal_conditions(norm_id),
            }
        )
    return {"norms": result}


def normalized_text(value: str) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").replace("-", " ").split())


def norm_identity_candidates(pack: dict[str, Any]) -> list[dict[str, Any]]:
    norms = all_norms(pack).get("norms", [])
    candidates: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for index, left in enumerate(norms):
        for right in norms[index + 1 :]:
            pair = tuple(sorted((left["norm_id"], right["norm_id"])))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            left_type = normalized_text(left.get("deontic_type", ""))
            right_type = normalized_text(right.get("deontic_type", ""))
            if not left_type or left_type != right_type:
                continue

            reasons: list[str] = []
            score = 0.0

            left_article = normalized_text(left.get("article", ""))
            right_article = normalized_text(right.get("article", ""))
            left_reg = normalized_text(left.get("regulation", ""))
            right_reg = normalized_text(right.get("regulation", ""))
            if left_article and left_article == right_article:
                score += 0.25
                reasons.append(f"same article ({left.get('article')})")
            if left_reg and left_reg == right_reg:
                score += 0.15
                reasons.append(f"same regulation ({left.get('regulation')})")

            field_matches = []
            for field in ["agent", "action", "object"]:
                left_value = normalized_text(left.get(field, ""))
                right_value = normalized_text(right.get(field, ""))
                if left_value and left_value == right_value:
                    score += 0.15
                    field_matches.append(field)
            if field_matches:
                reasons.append(f"same {', '.join(field_matches)}")

            left_statement = normalized_text(
                left.get("norm_statement") or left.get("action") or left.get("gw_condition_statement") or ""
            )
            right_statement = normalized_text(
                right.get("norm_statement") or right.get("action") or right.get("gw_condition_statement") or ""
            )
            if left_statement and right_statement:
                similarity = SequenceMatcher(None, left_statement, right_statement).ratio()
                if similarity >= 0.82:
                    score += 0.30
                    reasons.append(f"statement similarity {round(similarity * 100)}%")

            left_conditions = {
                (normalized_text(cond.get("predicate", "")), bool(cond.get("value")))
                for cond in left.get("conditions", [])
            }
            right_conditions = {
                (normalized_text(cond.get("predicate", "")), bool(cond.get("value")))
                for cond in right.get("conditions", [])
            }
            if left_conditions and left_conditions == right_conditions:
                score += 0.15
                reasons.append("same triggering conditions")

            if score < 0.55:
                continue

            candidates.append(
                {
                    "left_norm_id": left["norm_id"],
                    "right_norm_id": right["norm_id"],
                    "left_label": left.get("norm_statement") or left.get("action") or left["norm_id"],
                    "right_label": right.get("norm_statement") or right.get("action") or right["norm_id"],
                    "deontic_type": left.get("deontic_type") or "",
                    "article": left.get("article") or right.get("article") or "",
                    "regulation": left.get("regulation") or right.get("regulation") or "",
                    "score": round(score, 2),
                    "reasons": reasons,
                    "left_source": left.get("bpmn_source") or "",
                    "right_source": right.get("bpmn_source") or "",
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates
