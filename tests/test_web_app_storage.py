from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web-app"))

from backend import database, persistence
from backend.services import storage


@pytest.fixture
def isolated_runtime_storage(monkeypatch, tmp_path):
    data_dir = tmp_path / "web-data"
    db_path = data_dir / "norma.sqlite3"
    uploads_dir = data_dir / "uploads"
    graph_stores_dir = data_dir / "graph-stores"

    monkeypatch.setattr(database, "DATA_DIR", data_dir)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(database, "GRAPH_STORES_DIR", graph_stores_dir)

    monkeypatch.setattr(persistence, "DB_PATH", db_path)
    monkeypatch.setattr(persistence, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(persistence, "GRAPH_STORES_DIR", graph_stores_dir)

    monkeypatch.setattr(storage, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(storage, "GRAPH_STORES_DIR", graph_stores_dir)

    storage.pack_registry.clear()
    persistence.init_db()

    yield {
        "db_path": db_path,
        "uploads_dir": uploads_dir,
    }

    storage.pack_registry.clear()


def test_create_uploaded_pack_keeps_temporary_pack_out_of_db(sample_bpmn_xml, isolated_runtime_storage):
    result = storage.create_uploaded_pack("temporary-sample.bpmn", sample_bpmn_xml)

    assert result["pack"] == "temporary-sample"
    assert (isolated_runtime_storage["uploads_dir"] / result["pack"] / "bpmn" / "temporary-sample.bpmn").exists()

    with persistence.connect_db() as conn:
        uploaded_count = conn.execute("SELECT COUNT(*) FROM uploaded_packs").fetchone()[0]
        official_count = conn.execute("SELECT COUNT(*) FROM official_packs").fetchone()[0]

    assert uploaded_count == 0
    assert official_count == 0


def test_appending_to_official_pack_creates_runtime_workspace_without_uploaded_db_rows(
    sample_bpmn_xml,
    isolated_runtime_storage,
):
    storage.load_regulation_packs()

    result = storage.append_bpmn_to_pack("eu-ai-act", "added-flow.bpmn", sample_bpmn_xml)

    assert result["source_pack"] == "eu-ai-act"
    assert result["workspace_pack"] == result["pack"]
    assert result["workspace_pack"] != "eu-ai-act"
    assert (isolated_runtime_storage["uploads_dir"] / result["workspace_pack"] / "bpmn" / "added-flow.bpmn").exists()

    with persistence.connect_db() as conn:
        uploaded_count = conn.execute("SELECT COUNT(*) FROM uploaded_packs").fetchone()[0]
        official_count = conn.execute("SELECT COUNT(*) FROM official_packs").fetchone()[0]

    assert uploaded_count == 0
    assert official_count > 0


def test_sparql_store_uses_latest_abox_after_appending_to_temporary_pack(
    sample_bpmn_xml,
    isolated_runtime_storage,
):
    if not storage.OX_AVAILABLE:
        pytest.skip("pyoxigraph not installed")

    result = storage.create_uploaded_pack("temporary-sample.bpmn", sample_bpmn_xml)
    pack_name = result["pack"]

    modified_bpmn = (
        sample_bpmn_xml
        .replace("OBL_1", "OBL_2")
        .replace("REC_1", "REC_2")
        .replace("Marking obligation", "Second obligation")
        .replace("Voluntary codes of conduct", "Second recommendation")
        .replace("mark synthetic content", "publish safety report")
        .replace("adopt voluntary codes", "report incidents")
    )

    storage.append_bpmn_to_pack(pack_name, "extra.bpmn", modified_bpmn)
    store = storage.sparql_store_for_pack(pack_name)
    assert store is not None

    query = """
PREFIX norma: <https://w3id.org/def/norma-o#>
SELECT ?id
WHERE {
  ?n norma:deonticId ?id .
}
ORDER BY ?id
"""

    norm_ids = [row["id"].value for row in store.query(query)]
    assert norm_ids == ["OBL_1", "OBL_2", "REC_1", "REC_2"]
