from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
APP_ROOT = BACKEND_DIR.parent
CORE_ROOT = APP_ROOT.parent


def _path_from_env(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def _resolve_asset_path(env_name: str, default_path: Path) -> Path:
    configured = _path_from_env(env_name)
    if configured is not None:
        return configured
    return default_path


DATA_DIR = _path_from_env("NORMA_DATA_DIR") or (BACKEND_DIR / "data")
BPMN_DATA_DIR = DATA_DIR / "bpmn"
DB_PATH = DATA_DIR / "norma.sqlite3"
GRAPH_STORES_DIR = DATA_DIR / "graph-stores"
UPLOADS_DIR = DATA_DIR / "uploads"

REGULATIONS_DIR = _resolve_asset_path(
    "NORMA_REGULATIONS_DIR",
    CORE_ROOT / "regulations",
)
ONTOLOGY_PATH = _resolve_asset_path(
    "NORMA_ONTOLOGY_PATH",
    CORE_ROOT / "norma-ontology" / "norma-ontology-v1.ttl",
)
CAMUNDA_TEMPLATE_PATH = _resolve_asset_path(
    "NORMA_CAMUNDA_TEMPLATE_PATH",
    CORE_ROOT / "camunda-template" / "camunda8-compliance-template.json",
)

pack_registry: dict[str, dict[str, Any]] = {}
