from __future__ import annotations

import dataclasses
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.database import DB_PATH, GRAPH_STORES_DIR, UPLOADS_DIR
from norma_engine.rules.ir import Action, ClassAtom, Condition, DataAtom, Ref, RelationAtom, RuleIR


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_storage_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_STORES_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def connect_db() -> sqlite3.Connection:
    ensure_storage_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS official_packs (
                name TEXT PRIMARY KEY,
                reg_dir TEXT NOT NULL,
                entity_override_path TEXT,
                source_fingerprint TEXT NOT NULL,
                abox_ttl TEXT,
                swrl_owl TEXT,
                task_props_json TEXT NOT NULL DEFAULT '{}',
                rules_ir_json TEXT NOT NULL DEFAULT '[]',
                rule_count INTEGER NOT NULL DEFAULT 0,
                graph_store_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS official_pack_files (
                pack_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                xml_text TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (pack_name, relative_path),
                FOREIGN KEY (pack_name) REFERENCES official_packs(name) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS uploaded_packs (
                name TEXT PRIMARY KEY,
                source_filename TEXT NOT NULL,
                storage_dir TEXT NOT NULL,
                abox_ttl_path TEXT,
                swrl_owl_path TEXT,
                uploaded_at TEXT NOT NULL
            );
            """
        )


def compute_pack_fingerprint(reg_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(reg_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.name == ".DS_Store":
            continue
        digest.update(str(path.relative_to(reg_dir)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def serialize_rules_ir(rules_ir: list[RuleIR]) -> str:
    return json.dumps([dataclasses.asdict(rule) for rule in rules_ir], ensure_ascii=False)


def _ref_from_json(data: dict[str, Any]) -> Ref:
    return Ref(kind=data["kind"], name=data["name"])


def _condition_from_json(data: dict[str, Any]) -> Condition:
    return Condition(
        predicate=_ref_from_json(data["predicate"]),
        subject=_ref_from_json(data["subject"]),
        value=bool(data["value"]),
    )


def _action_from_json(data: dict[str, Any]) -> Action:
    predicate = _ref_from_json(data["predicate"]) if data.get("predicate") else None
    return Action(
        subject=_ref_from_json(data["subject"]),
        name=data["name"],
        predicate=predicate,
        datatype=data.get("datatype", "xsd:string"),
    )


def _relation_from_json(data: dict[str, Any]) -> RelationAtom:
    return RelationAtom(
        predicate=_ref_from_json(data["predicate"]),
        subject=_ref_from_json(data["subject"]),
        object=_ref_from_json(data["object"]),
    )


def _data_atom_from_json(data: dict[str, Any]) -> DataAtom:
    return DataAtom(
        predicate=_ref_from_json(data["predicate"]),
        subject=_ref_from_json(data["subject"]),
        value=data["value"],
        datatype=data.get("datatype", "xsd:string"),
    )


def _class_atom_from_json(data: dict[str, Any]) -> ClassAtom:
    return ClassAtom(
        class_ref=_ref_from_json(data["class_ref"]),
        subject=_ref_from_json(data["subject"]),
    )


def deserialize_rules_ir(payload: str) -> list[RuleIR]:
    raw_rules = json.loads(payload or "[]")
    rules: list[RuleIR] = []
    for item in raw_rules:
        rules.append(
            RuleIR(
                rid=item["rid"],
                conditions=tuple(_condition_from_json(c) for c in item.get("conditions", [])),
                actions=tuple(_action_from_json(a) for a in item.get("actions", [])),
                relations=tuple(_relation_from_json(r) for r in item.get("relations", [])),
                data_atoms=tuple(_data_atom_from_json(d) for d in item.get("data_atoms", [])),
                class_atoms=tuple(_class_atom_from_json(c) for c in item.get("class_atoms", [])),
                source=item.get("source", ""),
            )
        )
    return rules


def upsert_official_pack(
    *,
    name: str,
    reg_dir: str,
    entity_override_path: str | None,
    source_fingerprint: str,
    abox_ttl: str,
    swrl_owl: str | None,
    task_props: dict[str, dict[str, str]],
    rules_ir: list[RuleIR],
    graph_store_path: str,
) -> None:
    now = utc_now_iso()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO official_packs (
                name, reg_dir, entity_override_path, source_fingerprint, abox_ttl, swrl_owl,
                task_props_json, rules_ir_json, rule_count, graph_store_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                reg_dir = excluded.reg_dir,
                entity_override_path = excluded.entity_override_path,
                source_fingerprint = excluded.source_fingerprint,
                abox_ttl = excluded.abox_ttl,
                swrl_owl = excluded.swrl_owl,
                task_props_json = excluded.task_props_json,
                rules_ir_json = excluded.rules_ir_json,
                rule_count = excluded.rule_count,
                graph_store_path = excluded.graph_store_path,
                updated_at = excluded.updated_at
            """,
            (
                name,
                reg_dir,
                entity_override_path,
                source_fingerprint,
                abox_ttl,
                swrl_owl,
                json.dumps(task_props, ensure_ascii=False),
                serialize_rules_ir(rules_ir),
                len(rules_ir),
                graph_store_path,
                now,
                now,
            ),
        )


def sync_official_pack_files(pack_name: str, reg_dir: Path) -> None:
    bpmn_dir = reg_dir / "bpmn"
    rows: list[tuple[str, str, str, str]] = []
    if bpmn_dir.exists():
        for path in sorted(bpmn_dir.glob("*.bpmn")):
            xml_text = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(xml_text.encode("utf-8")).hexdigest()
            rows.append((pack_name, str(path.relative_to(reg_dir)), xml_text, digest, utc_now_iso()))

    with connect_db() as conn:
        conn.execute("DELETE FROM official_pack_files WHERE pack_name = ?", (pack_name,))
        conn.executemany(
            """
            INSERT INTO official_pack_files (
                pack_name, relative_path, xml_text, content_sha256, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )


def load_official_pack_row(name: str) -> sqlite3.Row | None:
    with connect_db() as conn:
        return conn.execute("SELECT * FROM official_packs WHERE name = ?", (name,)).fetchone()


def list_official_pack_rows() -> list[sqlite3.Row]:
    with connect_db() as conn:
        return conn.execute("SELECT * FROM official_packs ORDER BY name").fetchall()


def record_uploaded_pack(
    *,
    name: str,
    source_filename: str,
    storage_dir: str,
    abox_ttl_path: str | None,
    swrl_owl_path: str | None,
) -> None:
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO uploaded_packs (
                name, source_filename, storage_dir, abox_ttl_path, swrl_owl_path, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                source_filename = excluded.source_filename,
                storage_dir = excluded.storage_dir,
                abox_ttl_path = excluded.abox_ttl_path,
                swrl_owl_path = excluded.swrl_owl_path,
                uploaded_at = excluded.uploaded_at
            """,
            (name, source_filename, storage_dir, abox_ttl_path, swrl_owl_path, utc_now_iso()),
        )
