from __future__ import annotations

import gc
import io
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

from norma_engine.exporters.human_readable import rule_ir_to_human_readable
from backend.sparql_presets import SPARQL_PRESETS

from backend.database import (
    CAMUNDA_TEMPLATE_PATH,
    GRAPH_STORES_DIR,
    ONTOLOGY_PATH,
    REGULATIONS_DIR,
    UPLOADS_DIR,
    pack_registry,
)
from backend.persistence import (
    clear_uploaded_pack_rows,
    compute_pack_fingerprint,
    deserialize_rules_ir,
    init_db,
    load_official_pack_row,
    sync_official_pack_files,
    upsert_official_pack,
)
from backend.services.graphdb import OX_AVAILABLE, build_store, open_store, semantic_graph_data
from backend.services.swrl_eval import evaluate_swrl_rules, parse_swrl_rules_xml
from backend.services.pipeline import (
    KG_AVAILABLE,
    NORM_FIELD_MAP,
    NORMALIZER_AVAILABLE,
    TASK_PROP_NORM_MAP,
    all_norms,
    build_abox_from_dir,
    export_swrl,
    norm_identity_candidates,
    norm_ids_in_rule,
    norm_to_dict,
    pack_graph_data,
    pack_summary,
    rules_from_bpmn_dir,
)

log = logging.getLogger(__name__)


def _coerce_answer_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1"}:
        return True
    if text in {"false", "f", "no", "n", "0", "", "null", "none"}:
        return False
    return bool(value)


def _rule_iri_suffix(rule_iri: str) -> str:
    if "#" in rule_iri:
        return rule_iri.rsplit("#", 1)[-1]
    return rule_iri.rstrip("/").rsplit("/", 1)[-1]


def _rule_ids_to_lookup(pack: dict[str, Any]) -> dict[str, Any]:
    return {str(rule.rid): rule for rule in pack.get("rules_ir", [])}


def _get_parsed_swrl_ruleset(pack: dict[str, Any]):
    swrl_text = pack.get("swrl_owl") or ""
    if not swrl_text.strip():
        return None
    if pack.get("_parsed_swrl_source") == swrl_text and pack.get("_parsed_swrl_ruleset") is not None:
        return pack["_parsed_swrl_ruleset"]
    ruleset = parse_swrl_rules_xml(swrl_text)
    pack["_parsed_swrl_source"] = swrl_text
    pack["_parsed_swrl_ruleset"] = ruleset
    return ruleset


def _evaluate_pack_via_rule_ir(pack: dict[str, Any], answers: dict[str, bool]) -> list[dict[str, Any]]:
    seen_norm_ids: set[str] = set()
    matched: list[dict[str, Any]] = []
    for rule in pack["rules_ir"]:
        condition_names = {c.predicate.name for c in rule.conditions}
        if not condition_names.issubset(answers.keys()):
            continue
        if not all(answers[c.predicate.name] == c.value for c in rule.conditions):
            continue
        for norm_id in norm_ids_in_rule(rule):
            if norm_id in seen_norm_ids:
                continue
            seen_norm_ids.add(norm_id)
            matched.append(norm_to_dict(norm_id, rule))
    return matched


def _evaluate_pack_via_swrl(pack: dict[str, Any], answers: dict[str, bool]) -> tuple[list[dict[str, Any]], int]:
    ruleset = _get_parsed_swrl_ruleset(pack)
    if ruleset is None:
        raise ValueError("Pack has no SWRL ruleset to evaluate")

    outcome = evaluate_swrl_rules(ruleset, answers)
    rule_lookup = _rule_ids_to_lookup(pack)
    seen_norm_ids: set[str] = set()
    matched: list[dict[str, Any]] = []

    for rule_iri in outcome.matched_rule_iris:
        rule = rule_lookup.get(_rule_iri_suffix(rule_iri))
        if rule is None:
            continue
        for norm_id in norm_ids_in_rule(rule):
            if norm_id in seen_norm_ids:
                continue
            seen_norm_ids.add(norm_id)
            matched.append(norm_to_dict(norm_id, rule))
    return matched, len(outcome.matched_rule_iris)

def require_pack(name: str) -> dict[str, Any]:
    pack = pack_registry.get(name)
    if pack is None:
        raise HTTPException(404, f"Pack '{name}' not found. Available: {list(pack_registry.keys())}")
    return pack


def _official_store_path(pack_name: str) -> Path:
    return GRAPH_STORES_DIR / pack_name


def _slugify_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _unique_pack_name(base_name: str) -> str:
    candidate = _slugify_name(base_name) or "pack"
    if candidate not in pack_registry:
        return candidate
    index = 2
    while f"{candidate}-{index}" in pack_registry:
        index += 1
    return f"{candidate}-{index}"


def _ensure_runtime_pack_dirs(storage_dir: Path) -> Path:
    storage_dir.mkdir(parents=True, exist_ok=True)
    bpmn_dir = storage_dir / "bpmn"
    bpmn_dir.mkdir(parents=True, exist_ok=True)
    return bpmn_dir


def _sanitize_filename(filename: str) -> str:
    # Keep only the basename (drop any directory traversal component), then restrict
    # characters to alphanumerics, dots, hyphens, and underscores.
    name = Path(filename).name
    safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in name)
    return safe or "upload.bpmn"


def _write_runtime_bpmn(storage_dir: Path, filename: str, xml: str) -> Path:
    bpmn_dir = _ensure_runtime_pack_dirs(storage_dir)
    safe_name = _sanitize_filename(filename)
    target = bpmn_dir / safe_name
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix or ".bpmn"
    index = 2
    while target.exists():
        target = bpmn_dir / f"{stem}-{index}{suffix}"
        index += 1
    target.write_text(xml, encoding="utf-8")
    return target


def _build_runtime_pack_from_dir(pack_name: str, storage_dir: Path) -> dict[str, Any]:
    abox_iri = f"https://w3id.org/norma-abox/{pack_name}"
    entity_override = storage_dir / "entities.json"
    abox_ttl, norm_report = build_abox_from_dir(storage_dir, abox_iri, override_file=entity_override)
    rules_ir, task_props = rules_from_bpmn_dir(storage_dir, override_path=entity_override)
    swrl_text = export_swrl(rules_ir, abox_iri=abox_iri, rules_iri=f"{abox_iri}/rules") if rules_ir else None

    abox_path = None
    if abox_ttl:
        abox_path = storage_dir / f"{pack_name}.abox.ttl"
        abox_path.write_text(abox_ttl, encoding="utf-8")

    swrl_path = None
    if swrl_text:
        swrl_path = storage_dir / f"{pack_name}.swrl.owl"
        swrl_path.write_text(swrl_text, encoding="utf-8")

    pack_registry[pack_name] = {
        "abox_ttl": abox_ttl or "",
        "swrl_owl": swrl_text,
        "store": build_store(abox_ttl, ONTOLOGY_PATH) if abox_ttl and OX_AVAILABLE else None,
        "rules_ir": rules_ir,
        "task_props": task_props,
        "norm_report": norm_report,
        "uploaded": True,
        "storage_dir": str(storage_dir),
    }
    return {
        "pack": pack_name,
        "rules_count": len(rules_ir),
        "has_abox": abox_ttl is not None,
        "has_swrl": bool(swrl_text),
    }


def _materialize_workspace_from_official(source_pack: dict[str, Any], target_pack_name: str) -> Path:
    target_dir = UPLOADS_DIR / target_pack_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    bpmn_dir = _ensure_runtime_pack_dirs(target_dir)
    reg_dir = Path(source_pack["reg_dir"])
    source_bpmn_dir = reg_dir / "bpmn"
    for path in sorted(source_bpmn_dir.glob("*.bpmn")):
        shutil.copy2(path, bpmn_dir / path.name)
    entity_file = reg_dir / "entities.json"
    if entity_file.exists():
        shutil.copy2(entity_file, target_dir / "entities.json")
    return target_dir


def _pack_from_db_row(row: Any) -> dict[str, Any]:
    abox_ttl = row["abox_ttl"] or ""
    store_path = Path(row["graph_store_path"]) if row["graph_store_path"] else _official_store_path(row["name"])
    store = open_store(store_path)
    if store is None and abox_ttl and OX_AVAILABLE:
        store = build_store(abox_ttl, ONTOLOGY_PATH, store_path=store_path)
    return {
        "abox_ttl": abox_ttl,
        "swrl_owl": row["swrl_owl"],
        "store": store,
        "rules_ir": deserialize_rules_ir(row["rules_ir_json"]),
        "task_props": json.loads(row["task_props_json"] or "{}"),
        "norm_report": None,
        "reg_dir": row["reg_dir"],
        "official": True,
    }


def load_regulation_packs() -> None:
    init_db()
    clear_uploaded_pack_rows()
    if not REGULATIONS_DIR.exists():
        return
    for reg_dir in sorted(REGULATIONS_DIR.iterdir()):
        if reg_dir.is_dir():
            pack_name = reg_dir.name
            fingerprint = compute_pack_fingerprint(reg_dir)
            row = load_official_pack_row(pack_name)
            if row and row["source_fingerprint"] == fingerprint and row["abox_ttl"]:
                sync_official_pack_files(pack_name, reg_dir)
                pack_registry[pack_name] = _pack_from_db_row(row)
            else:
                rebuild_regulation_pack(pack_name, reg_dir)


def rebuild_regulation_pack(pack_name: str, reg_dir: Path) -> None:
    abox_iri = f"https://w3id.org/norma-abox/{pack_name}"
    entity_override = reg_dir / "entities.json"
    source_fingerprint = compute_pack_fingerprint(reg_dir)
    existing_pack = pack_registry.get(pack_name)

    if existing_pack is not None and existing_pack.get("store") is not None:
        existing_pack["store"] = None
        gc.collect()

    abox_ttl = None
    norm_report = None
    try:
        abox_ttl, norm_report = build_abox_from_dir(reg_dir, abox_iri, override_file=entity_override)
    except Exception as exc:
        log.warning("ABox build failed for %s: %s", pack_name, exc)

    if not abox_ttl:
        abox_file = next(reg_dir.glob("*.abox.ttl"), None)
        if abox_file:
            abox_ttl = abox_file.read_text(encoding="utf-8")

    if not abox_ttl:
        return

    try:
        rules_ir, task_props = rules_from_bpmn_dir(reg_dir, override_path=entity_override)
    except Exception as exc:
        log.warning("Rule extraction failed for %s: %s", pack_name, exc)
        rules_ir, task_props = [], {}

    swrl_text = None
    swrl_file = next(reg_dir.glob("*.swrl.owl"), None)
    if swrl_file:
        swrl_text = swrl_file.read_text(encoding="utf-8")
    elif rules_ir:
        try:
            swrl_text = export_swrl(
                rules_ir,
                abox_iri=abox_iri,
                rules_iri=f"{abox_iri}/rules",
            )
        except Exception as exc:
            log.warning("SWRL export failed for %s: %s", pack_name, exc)

    store_path = _official_store_path(pack_name)
    if OX_AVAILABLE:
        writable_store = build_store(abox_ttl, ONTOLOGY_PATH, store_path=store_path)
        writable_store = None
        gc.collect()
        store = open_store(store_path)
    else:
        store = None

    upsert_official_pack(
        name=pack_name,
        reg_dir=str(reg_dir),
        entity_override_path=str(entity_override) if entity_override.exists() else None,
        source_fingerprint=source_fingerprint,
        abox_ttl=abox_ttl,
        swrl_owl=swrl_text,
        task_props=task_props or {},
        rules_ir=rules_ir,
        graph_store_path=str(store_path),
    )
    sync_official_pack_files(pack_name, reg_dir)

    pack_registry[pack_name] = {
        "abox_ttl": abox_ttl,
        "swrl_owl": swrl_text,
        "store": store,
        "rules_ir": rules_ir,
        "task_props": task_props or {},
        "norm_report": norm_report,
        "reg_dir": str(reg_dir),
        "official": True,
    }


def rebuild_pack(pack_name: str) -> dict[str, Any]:
    pack = require_pack(pack_name)
    reg_dir_str = pack.get("reg_dir")
    if not reg_dir_str:
        raise HTTPException(400, f"Pack '{pack_name}' is not folder-backed and cannot be rebuilt")

    reg_dir = Path(reg_dir_str)
    rebuild_regulation_pack(pack_name, reg_dir)
    refreshed = require_pack(pack_name)
    return {
        "pack": pack_name,
        "rule_count": len(refreshed.get("rules_ir", [])),
        "has_abox": bool(refreshed.get("abox_ttl")),
        "has_swrl": bool(refreshed.get("swrl_owl")),
        "rebuild_source": str(reg_dir),
    }


def list_pack_summaries() -> list[dict[str, Any]]:
    return [pack_summary(name, pack) for name, pack in pack_registry.items()]


def pack_rules(pack_name: str) -> dict[str, Any]:
    pack = require_pack(pack_name)
    rules = []
    for rule in pack["rules_ir"]:
        rules.append(
            {
                "rid": rule.rid,
                "source": rule.source,
                "is_conditional": bool(rule.conditions),
                "conditions": [{"predicate": c.predicate.name, "value": c.value} for c in rule.conditions],
                "human_readable": rule_ir_to_human_readable(rule, multiline=False),
                "human_readable_compact": rule_ir_to_human_readable(rule, multiline=False, compact=True),
            }
        )
    return {"pack": pack_name, "rule_count": len(rules), "rules": rules}


def conditions_for_pack(pack_name: str) -> dict[str, Any]:
    pack = require_pack(pack_name)
    seen: dict[str, dict[str, str]] = {}
    for rule in pack["rules_ir"]:
        for cond in rule.conditions:
            seen.setdefault(
                cond.predicate.name,
                {"predicate": cond.predicate.name, "label": cond.predicate.name.replace("_", " ")},
            )
    return {"conditions": list(seen.values())}


def evaluate_pack(pack_name: str, answers: Any) -> dict[str, Any]:
    pack = require_pack(pack_name)
    if not isinstance(answers, dict):
        raise HTTPException(422, "Request body must be a JSON object mapping condition names to booleans")
    coerced: dict[str, bool] = {str(k): _coerce_answer_bool(v) for k, v in answers.items()}
    try:
        matched, matched_rule_count = _evaluate_pack_via_swrl(pack, coerced)
        return {
            "matched_rules": matched,
            "engine": "swrl",
            "matched_rule_count": matched_rule_count,
        }
    except Exception as exc:
        log.warning("SWRL evaluation failed for %s, falling back to RuleIR matcher: %s", pack_name, exc)
        return {
            "matched_rules": _evaluate_pack_via_rule_ir(pack, coerced),
            "engine": "rule_ir",
        }


def graph_for_pack(pack_name: str) -> dict[str, Any]:
    pack = require_pack(pack_name)
    if pack.get("store") is not None:
        return semantic_graph_data(pack["store"], pack=pack)
    return pack_graph_data(pack)


def sparql_store_for_pack(pack_name: str):
    pack = require_pack(pack_name)
    if not OX_AVAILABLE:
        return None

    # Runtime packs should always query against the latest generated ABox.
    # Rebuilding the in-memory store here avoids any stale cache edge case
    # after appending BPMN files to an existing temporary pack.
    if pack.get("storage_dir"):
        abox_ttl = pack.get("abox_ttl") or ""
        if not abox_ttl:
            return None
        pack["store"] = build_store(abox_ttl, ONTOLOGY_PATH)
        return pack["store"]

    return pack.get("store")


def norms_for_pack(pack_name: str) -> dict[str, Any]:
    return all_norms(require_pack(pack_name))


def update_norm(pack_name: str, norm_id: str, body: dict[str, Any]) -> dict[str, Any]:
    pack = require_pack(pack_name)
    raw_props: dict[str, dict[str, str]] = pack.setdefault("task_props", {})

    target_key = None
    for task_key, props in raw_props.items():
        explicit = (props.get("compliance_deonticId") or "").strip()
        if explicit == norm_id:
            target_key = task_key
            break

    if target_key is None:
        target_key = norm_id
        raw_props[target_key] = {"compliance_deonticId": norm_id}

    updated = []
    for field_key, value in body.items():
        prop_key = NORM_FIELD_MAP.get(field_key)
        if prop_key:
            raw_props[target_key][prop_key] = str(value)
            updated.append(field_key)

    return {"norm_id": norm_id, "updated": updated}


def entities_for_pack(pack_name: str) -> dict[str, Any]:
    pack = require_pack(pack_name)
    reg_dir_str = pack.get("reg_dir")
    norm_report = pack.get("norm_report")

    override: dict[str, Any] = {
        "regulation": {},
        "agent": {},
        "object": {},
        "action": {},
        "deontic_id": {},
        "condition_statement": {},
        "_confirmed_separate": [],
    }
    if reg_dir_str:
        entity_file = Path(reg_dir_str) / "entities.json"
        if entity_file.exists():
            override = json.loads(entity_file.read_text(encoding="utf-8"))

    decisions = []
    warnings = []
    if norm_report:
        for decision in norm_report.decisions:
            decisions.append(
                {
                    "field": decision.field,
                    "raw_labels": decision.raw_labels,
                    "winner": decision.winner,
                    "reason": decision.reason,
                    "confidence": decision.confidence,
                }
            )
        for warning in norm_report.warnings:
            warnings.append(
                {
                    "field": warning.field,
                    "labels": warning.labels,
                    "message": warning.message,
                    "suggestion": warning.suggestion,
                }
            )

    task_props = pack.get("task_props", {})
    all_values: dict[str, set[str]] = {field: set() for field in TASK_PROP_NORM_MAP}
    for props in task_props.values():
        for norm_field, prop_key in TASK_PROP_NORM_MAP.items():
            value = (props.get(prop_key) or "").strip()
            if value:
                all_values[norm_field].add(value)

    return {
        "pack": pack_name,
        "decisions": decisions,
        "warnings": warnings,
        "norm_duplicates": norm_identity_candidates(pack),
        "override": override,
        "all_values": {key: sorted(values) for key, values in all_values.items() if values},
        "has_reg_dir": bool(reg_dir_str),
    }


def update_entities(pack_name: str, body: dict[str, Any]) -> dict[str, Any]:
    pack = require_pack(pack_name)
    reg_dir_str = pack.get("reg_dir")
    if not reg_dir_str:
        raise HTTPException(400, "This pack has no associated regulation directory")

    reg_dir = Path(reg_dir_str)
    entity_file = reg_dir / "entities.json"
    current = {
        "regulation": {},
        "agent": {},
        "object": {},
        "action": {},
        "deontic_id": {},
        "condition_statement": {},
        "_confirmed_separate": [],
    }
    if entity_file.exists():
        current = json.loads(entity_file.read_text(encoding="utf-8"))

    action = body.get("action")
    if action == "merge":
        field = body.get("field", "")
        label_a = body.get("label_a", "")
        label_b = body.get("label_b", "")
        canonical = body.get("canonical", "")
        if not (field and label_a and label_b and canonical):
            raise HTTPException(400, "merge requires field, label_a, label_b, canonical")
        current.setdefault(field, {})
        current[field][label_a] = canonical
        current[field][label_b] = canonical
    elif action == "confirm_separate":
        label_a = body.get("label_a", "")
        label_b = body.get("label_b", "")
        pair = sorted([label_a, label_b])
        if pair not in [sorted(item) for item in current["_confirmed_separate"]]:
            current["_confirmed_separate"].append(pair)
    elif action == "remove_override":
        field = body.get("field", "")
        label = body.get("label", "")
        if field in current and label in current[field]:
            del current[field][label]
    else:
        raise HTTPException(400, f"Unknown action: {action}")

    entity_file.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    rebuild_regulation_pack(pack_name, reg_dir)
    return {"ok": True, "pack": pack_name}


def create_uploaded_pack(filename: str, xml: str) -> dict[str, Any]:
    pack_name = _unique_pack_name(Path(filename).stem)
    storage_dir = UPLOADS_DIR / pack_name
    _write_runtime_bpmn(storage_dir, filename, xml)
    return _build_runtime_pack_from_dir(pack_name, storage_dir)


def append_bpmn_to_pack(pack_name: str, filename: str, xml: str) -> dict[str, Any]:
    pack = require_pack(pack_name)

    if pack.get("storage_dir"):
        target_pack_name = pack_name
        storage_dir = Path(pack["storage_dir"])
    elif pack.get("reg_dir"):
        target_pack_name = _unique_pack_name(f"{pack_name}-workspace")
        storage_dir = _materialize_workspace_from_official(pack, target_pack_name)
    else:
        raise HTTPException(400, f"Pack '{pack_name}' cannot accept additional BPMN files")

    written = _write_runtime_bpmn(storage_dir, filename, xml)
    result = _build_runtime_pack_from_dir(target_pack_name, storage_dir)
    result["added_bpmn"] = written.name
    result["source_pack"] = pack_name
    result["workspace_pack"] = target_pack_name
    return result


def abox_response(pack_name: str) -> PlainTextResponse:
    pack = require_pack(pack_name)
    return PlainTextResponse(pack["abox_ttl"], media_type="text/turtle")


def swrl_response(pack_name: str) -> PlainTextResponse:
    pack = require_pack(pack_name)
    if not pack["swrl_owl"]:
        raise HTTPException(404, "No SWRL file for this pack")
    return PlainTextResponse(pack["swrl_owl"], media_type="application/rdf+xml")


def download_text(filename: str, content: str, media_type: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def sparql_presets_payload() -> dict[str, Any]:
    return {"presets": SPARQL_PRESETS}


def template_download() -> Response:
    if not CAMUNDA_TEMPLATE_PATH.exists():
        raise HTTPException(404, "Template file not found")
    return Response(
        content=CAMUNDA_TEMPLATE_PATH.read_bytes(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="camunda8-compliance-template.json"'},
    )


def capabilities() -> dict[str, bool]:
    return {
        "kg_available": KG_AVAILABLE,
        "normalizer_available": NORMALIZER_AVAILABLE,
        "graphdb_available": OX_AVAILABLE,
        "official_pack_catalog_db": True,
        "persistent_graph_store": OX_AVAILABLE,
    }
