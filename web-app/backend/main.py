from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# `web-app` lives inside the monorepo and depends on the core `norma_engine`
# package at the repository root. `NORMA_CORE_ROOT` is only needed if that root moves.
BACKEND_DIR = Path(__file__).resolve().parent
APP_ROOT = BACKEND_DIR.parent
CORE_ROOT = APP_ROOT.parent

if importlib.util.find_spec("norma_engine") is None:
    candidate_roots: list[Path] = []
    env_core_root = os.getenv("NORMA_CORE_ROOT", "").strip()
    if env_core_root:
        candidate_roots.append(Path(env_core_root).expanduser().resolve())
    candidate_roots.append(CORE_ROOT)

    for root in candidate_roots:
        if (root / "norma_engine").exists() and str(root) not in sys.path:
            sys.path.insert(0, str(root))
            break

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.services.graphdb import OX_AVAILABLE, extract_sparql_query, rdf_download, sparql_response
from backend.services.storage import (
    abox_response,
    append_bpmn_to_pack,
    capabilities,
    conditions_for_pack,
    create_uploaded_pack,
    download_text,
    entities_for_pack,
    evaluate_pack,
    graph_for_pack,
    list_pack_summaries,
    load_regulation_packs,
    norms_for_pack,
    pack_rules,
    rebuild_pack,
    require_pack,
    sparql_presets_payload,
    swrl_response,
    template_download,
    update_entities,
    update_norm,
)

app = FastAPI(title="NORMA API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    load_regulation_packs()


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "project_root": str(APP_ROOT),
        "capabilities": capabilities(),
    }


@app.get("/api/packs")
async def packs():
    return list_pack_summaries()


@app.get("/api/pack/{pack}/abox")
async def pack_abox(pack: str):
    return abox_response(pack)


@app.get("/api/pack/{pack}/swrl")
async def pack_swrl(pack: str):
    return swrl_response(pack)


@app.get("/api/pack/{pack}/rules")
async def pack_rules_endpoint(pack: str):
    return pack_rules(pack)


@app.post("/api/pack/{pack}/rebuild")
async def rebuild_pack_endpoint(pack: str):
    return rebuild_pack(pack)


@app.get("/api/pack/{pack}/download/abox")
async def download_abox(pack: str):
    current = require_pack(pack)
    return download_text(f"{pack}.abox.ttl", current["abox_ttl"], "text/turtle")


@app.get("/api/pack/{pack}/download/abox-rdf")
async def download_abox_rdf(pack: str):
    current = require_pack(pack)
    if not current.get("abox_ttl"):
        raise HTTPException(404, "No ABox for this pack")
    return rdf_download(current["abox_ttl"], pack)


@app.get("/api/pack/{pack}/download/swrl")
async def download_swrl(pack: str):
    current = require_pack(pack)
    if not current.get("swrl_owl"):
        raise HTTPException(404, "No SWRL file for this pack")
    return download_text(f"{pack}.swrl.owl", current["swrl_owl"], "application/rdf+xml")


@app.get("/api/pack/{pack}/conditions")
async def pack_conditions(pack: str):
    return conditions_for_pack(pack)


@app.post("/api/pack/{pack}/evaluate")
async def evaluate(pack: str, request: Request):
    return evaluate_pack(pack, await request.json())


@app.get("/api/sparql/{pack}")
@app.post("/api/sparql/{pack}")
async def sparql_endpoint(pack: str, request: Request):
    if not OX_AVAILABLE:
        raise HTTPException(503, "pyoxigraph not installed")
    current = require_pack(pack)
    if current.get("store") is None:
        raise HTTPException(503, "SPARQL store unavailable for this pack")
    query = await extract_sparql_query(request)
    if not query:
        raise HTTPException(400, "Missing SPARQL query")
    try:
        results = current["store"].query(query)
    except Exception as exc:
        raise HTTPException(400, f"SPARQL error: {exc}")
    return sparql_response(results)


@app.post("/api/upload")
async def upload_bpmn(file: UploadFile = File(...)):
    if not (file.filename or "").endswith(".bpmn"):
        raise HTTPException(400, "Only .bpmn files are accepted")
    xml = (await file.read()).decode("utf-8")
    return create_uploaded_pack(file.filename or "upload.bpmn", xml)


@app.post("/api/pack/{pack}/append")
async def append_bpmn(pack: str, file: UploadFile = File(...)):
    if not (file.filename or "").endswith(".bpmn"):
        raise HTTPException(400, "Only .bpmn files are accepted")
    xml = (await file.read()).decode("utf-8")
    return append_bpmn_to_pack(pack, file.filename or "upload.bpmn", xml)


@app.get("/api/pack/{pack}/graph")
async def pack_graph(pack: str):
    return graph_for_pack(pack)


@app.get("/api/pack/{pack}/norms")
async def pack_norms(pack: str):
    return norms_for_pack(pack)


@app.patch("/api/pack/{pack}/norm/{norm_id}")
async def patch_norm(pack: str, norm_id: str, request: Request):
    return update_norm(pack, norm_id, await request.json())


@app.get("/api/pack/{pack}/entities")
async def pack_entities(pack: str):
    return entities_for_pack(pack)


@app.post("/api/pack/{pack}/entities")
async def patch_entities(pack: str, request: Request):
    return update_entities(pack, await request.json())


@app.get("/api/sparql-presets")
async def sparql_presets():
    return sparql_presets_payload()


@app.get("/api/download/template")
async def download_template():
    return template_download()
