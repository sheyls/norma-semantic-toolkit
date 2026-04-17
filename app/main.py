#!/usr/bin/env python3
"""
NORMA Web App
=============
FastAPI demo for the NORMA norm-determination pipeline.

Start:
    cd /path/to/deontic-rules-bpmn
    uvicorn app.main:app --reload

Endpoints:
    GET  /                          HTML UI
    GET  /api/packs                 List loaded packs
    GET  /api/pack/{pack}/abox      ABox Turtle text
    GET  /api/pack/{pack}/swrl      SWRL OWL/XML text
    GET  /api/pack/{pack}/download/abox
    GET  /api/pack/{pack}/download/swrl
    GET  /api/pack/{pack}/conditions   List gateway conditions
    POST /api/pack/{pack}/evaluate     Evaluate conditions → applicable norms
    GET  /api/sparql/{pack}?query=...  SPARQL 1.1 endpoint (pyoxigraph)
    POST /api/sparql/{pack}            SPARQL 1.1 endpoint
    GET  /api/sparql-presets           List of preset SPARQL queries (from sparql_presets.py)
    POST /api/upload                   Upload + process a BPMN file
    GET   /api/download/template        Download Camunda element template JSON
    PATCH /api/pack/{pack}/norm/{id}    Update annotation fields for a norm (in-memory)
"""

from __future__ import annotations

import dataclasses
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

# Project root on the Python path so "norma" package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates

# ── NORMA pipeline ────────────────────────────────────────────────────────────
from app.sparql_presets import SPARQL_PRESETS

from norma.parsing.bpmn_parser import parse_bpmn_to_reduced_graph
from norma.rules.extractor import enumerate_paths_and_build_ir
from norma.rules.ir import RuleIR
from norma.exporters.swrl import export_rules_to_owl
from norma.utils import to_symbol

try:
    from norma.kg.builder import parse_bpmn_folder, to_json, to_turtle, auto_deontic_id
    _KG_AVAILABLE = True
except ImportError:
    _KG_AVAILABLE = False
    def auto_deontic_id(dtype: str, bpmn_name: str, bpmn_id: str) -> str:  # type: ignore[misc]
        return bpmn_id

# ── pyoxigraph ────────────────────────────────────────────────────────────────
try:
    import pyoxigraph as ox
    _OX_AVAILABLE = True
except ImportError:
    _OX_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
REGS_DIR     = ROOT / "regulations"
ONTOLOGY     = ROOT / "ontology" / "norma-ontology-v1.ttl"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="NORMA", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# In-memory pack registry: name → {abox_ttl, swrl_owl, store, rules_ir}
_packs: dict[str, dict[str, Any]] = {}


# =============================================================================
# Startup: load pre-built regulation packs
# =============================================================================

@app.on_event("startup")
async def load_packs() -> None:
    if not REGS_DIR.exists():
        print(f"[norma] regulations/ not found at {REGS_DIR}")
        return
    for reg_dir in sorted(REGS_DIR.iterdir()):
        if not reg_dir.is_dir():
            continue

        abox_iri  = f"https://w3id.org/norma-abox/{reg_dir.name}"
        bpmn_dir  = reg_dir / "bpmn"
        abox_ttl: Optional[str] = None

        # ── Prefer building ABox live from all BPMN files in bpmn/ ──────────
        if _KG_AVAILABLE and bpmn_dir.is_dir() and any(bpmn_dir.glob("*.bpmn")):
            try:
                elements, _ = parse_bpmn_folder(bpmn_dir)
                records  = to_json(elements)
                abox_ttl = to_turtle(records, str(bpmn_dir), abox_iri)
            except Exception as exc:
                print(f"[norma] Warning: ABox build failed for {reg_dir.name}: {exc}")

        # ── Fall back to pre-built .abox.ttl ────────────────────────────────
        if not abox_ttl:
            abox_file = next(reg_dir.glob("*.abox.ttl"), None)
            if abox_file:
                abox_ttl = abox_file.read_text(encoding="utf-8")

        if not abox_ttl:
            continue

        rules_ir, task_props = _rules_from_bpmn_dir(reg_dir)
        swrl_file = next(reg_dir.glob("*.swrl.owl"), None)
        store = _build_store(abox_ttl) if _OX_AVAILABLE else None

        _packs[reg_dir.name] = {
            "abox_ttl":   abox_ttl,
            "swrl_owl":   swrl_file.read_text(encoding="utf-8") if swrl_file else None,
            "store":      store,
            "rules_ir":   rules_ir,
            "task_props": task_props or {},
        }
        print(f"[norma] Loaded: {reg_dir.name} — {len(rules_ir)} rule(s)")


def _rules_from_bpmn_dir(reg_dir: Path):
    bpmn_dir = reg_dir / "bpmn"
    if not bpmn_dir.is_dir():
        return [], {}
    rules_ir: list = []
    all_task_props: dict = {}
    for bpmn_file in sorted(bpmn_dir.glob("*.bpmn")):
        try:
            xml = bpmn_file.read_text(encoding="utf-8")
            nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(xml)
            # Tag every element with its source file so the UI can show it
            for props in task_props.values():
                props.setdefault("_bpmn_source", bpmn_file.name)
            all_task_props.update(task_props)
            _, ir, _ = enumerate_paths_and_build_ir(
                nodes=nodes,
                edges=edges,
                gateway_outgoing_index=gw_index,
                task_props=task_props,
            )
            # Tag each rule with the source BPMN filename
            rules_ir.extend(
                dataclasses.replace(r, source=bpmn_file.name) for r in ir
            )
        except Exception as exc:
            print(f"[norma] Warning: could not extract rules from {bpmn_file.name}: {exc}")
    return rules_ir, all_task_props


def _build_store(ttl_text: str):
    """Load Turtle into a pyoxigraph in-memory store, optionally including TBox."""
    if not _OX_AVAILABLE:
        return None
    store = ox.Store()
    store.load(ttl_text, format=ox.RdfFormat.TURTLE)
    if ONTOLOGY.exists():
        store.load(ONTOLOGY.read_text(encoding="utf-8"), format=ox.RdfFormat.TURTLE)
    return store


# =============================================================================
# UI
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    packs = [
        {
            "name":       k,
            "rule_count": len(v["rules_ir"]),
            "has_abox":   v["abox_ttl"] is not None,
            "has_swrl":   v["swrl_owl"] is not None,
        }
        for k, v in _packs.items()
    ]
    return templates.TemplateResponse("index.html", {
        "request":      request,
        "packs":        packs,
        "kg_available": _KG_AVAILABLE,
        "ox_available": _OX_AVAILABLE,
    })


# =============================================================================
# API: pack listing & content
# =============================================================================

@app.get("/api/packs")
async def list_packs():
    return [
        {
            "name":       k,
            "rule_count": len(v["rules_ir"]),
            "has_abox":   v["abox_ttl"] is not None,
            "has_swrl":   v["swrl_owl"] is not None,
        }
        for k, v in _packs.items()
    ]


@app.get("/api/pack/{pack}/abox")
async def get_abox(pack: str):
    p = _require_pack(pack)
    return PlainTextResponse(p["abox_ttl"], media_type="text/turtle")


@app.get("/api/pack/{pack}/swrl")
async def get_swrl(pack: str):
    p = _require_pack(pack)
    if not p["swrl_owl"]:
        raise HTTPException(404, "No SWRL file for this pack")
    return PlainTextResponse(p["swrl_owl"], media_type="application/rdf+xml")


@app.get("/api/pack/{pack}/download/abox")
async def download_abox(pack: str):
    p = _require_pack(pack)
    return StreamingResponse(
        io.BytesIO(p["abox_ttl"].encode()),
        media_type="text/turtle",
        headers={"Content-Disposition": f'attachment; filename="{pack}.abox.ttl"'},
    )


@app.get("/api/pack/{pack}/download/abox-rdf")
async def download_abox_rdf(pack: str):
    """Convert the ABox Turtle to RDF/XML and serve it as a download."""
    p = _require_pack(pack)
    ttl = p.get("abox_ttl") or ""
    if not ttl:
        raise HTTPException(404, "No ABox for this pack")
    if not _OX_AVAILABLE:
        raise HTTPException(503, "pyoxigraph not available — cannot convert to RDF/XML")
    store = ox.Store()
    store.load(ttl, format=ox.RdfFormat.TURTLE)
    buf = io.BytesIO()
    store.dump(buf, format=ox.RdfFormat.RDF_XML, from_graph=ox.DefaultGraph())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/rdf+xml",
        headers={"Content-Disposition": f'attachment; filename="{pack}.abox.rdf"'},
    )


@app.get("/api/pack/{pack}/download/swrl")
async def download_swrl(pack: str):
    p = _require_pack(pack)
    if not p["swrl_owl"]:
        raise HTTPException(404, "No SWRL file for this pack")
    return StreamingResponse(
        io.BytesIO(p["swrl_owl"].encode()),
        media_type="application/rdf+xml",
        headers={"Content-Disposition": f'attachment; filename="{pack}.swrl.owl"'},
    )


# =============================================================================
# API: norm evaluator
# =============================================================================

@app.get("/api/pack/{pack}/conditions")
async def get_conditions(pack: str):
    """Return the unique gateway conditions across all rules in this pack."""
    p = _require_pack(pack)
    seen: Any = {}
    for rule in p["rules_ir"]:
        for cond in rule.conditions:
            if cond.predicate.name not in seen:
                seen[cond.predicate.name] = {
                    "predicate": cond.predicate.name,
                    "label": cond.predicate.name.replace("_", " "),
                }
    return {"conditions": list(seen.values())}


@app.post("/api/pack/{pack}/evaluate")
async def evaluate_conditions(pack: str, request: Request):
    """
    Body: {predicate_name: bool, ...}
    Returns one result per applicable norm (deduplicated across matched paths).
    A rule matches when ALL its conditions are answered and satisfied.
    """
    p = _require_pack(pack)
    answers: Any = await request.json()

    seen_norm_ids: set = set()
    matched: list = []

    for rule in p["rules_ir"]:
        cond_names = {c.predicate.name for c in rule.conditions}
        if not cond_names.issubset(answers.keys()):
            continue  # some conditions unanswered — skip
        if not all(answers[c.predicate.name] == c.value for c in rule.conditions):
            continue  # conditions not satisfied

        # Rule matches — emit one entry per norm on this path, deduplicated
        for norm_id in _norm_ids_in_rule(rule):
            if norm_id in seen_norm_ids:
                continue
            seen_norm_ids.add(norm_id)
            matched.append(_norm_to_dict(norm_id, rule))

    return {"matched_rules": matched}


def _norm_ids_in_rule(rule: RuleIR) -> list[str]:
    """Return the deontic IDs of every norm on this rule's path, in order."""
    seen: set = set()
    ids: list = []
    for d in rule.data_atoms:
        if d.predicate.name == "deonticId" and d.value not in seen:
            seen.add(d.value)
            ids.append(d.value)
    return ids


def _norm_to_dict(norm_id: str, rule: RuleIR) -> Any:
    """Build an evaluate result dict for a single norm using per-subject filtering."""
    sym = to_symbol(norm_id)

    def _dat(pred: str) -> Optional[str]:
        return next(
            (d.value for d in rule.data_atoms
             if d.predicate.name == pred and d.subject.name == sym),
            None,
        )

    def _rel_obj(pred: str) -> Optional[str]:
        """Object-property where THIS norm is the subject."""
        return next(
            (r.object.name for r in rule.relations
             if r.predicate.name == pred and r.subject.name == sym),
            None,
        )

    def _rel_subj(pred: str) -> Optional[str]:
        """Object-property where THIS norm is the object."""
        return next(
            (r.subject.name for r in rule.relations
             if r.predicate.name == pred and r.object.name == sym),
            None,
        )

    object_label = _dat("objectText") or None
    if not object_label:
        raw = _rel_obj("hasObject") or ""
        object_label = raw.replace("Object_", "").replace("_", " ").strip() or None

    agent_id = _rel_subj("isLegalAgentOf")

    return {
        "rule_id":       rule.rid,
        "norm_id":       norm_id,
        "bpmn_source":   rule.source,
        "conditions":    [{"predicate": c.predicate.name, "value": c.value} for c in rule.conditions],
        "agent":         agent_id,
        "action":        _dat("actionText"),
        "object":        object_label,
        "binding_force": _rel_obj("hasBindingForce"),
        "risk_level":    _rel_obj("hasComplianceCriticality"),
        "regulation":    _dat("fromRegulation"),
        "article":       _dat("fromArticle"),
        "paragraph":     _dat("fromParagraph"),
        "source_uri":    _dat("sourceURI"),
    }


# =============================================================================
# API: SPARQL endpoint (pyoxigraph)
# =============================================================================

@app.get("/api/sparql/{pack}")
@app.post("/api/sparql/{pack}")
async def sparql_endpoint(pack: str, request: Request):
    if not _OX_AVAILABLE:
        raise HTTPException(503, "pyoxigraph not installed — run: pip install pyoxigraph")
    p = _require_pack(pack)
    store = p.get("store")
    if store is None:
        raise HTTPException(503, "SPARQL store unavailable for this pack")

    query = await _extract_sparql_query(request)
    if not query:
        raise HTTPException(400, "Missing SPARQL query")

    try:
        results = store.query(query)
    except Exception as exc:
        raise HTTPException(400, f"SPARQL error: {exc}")

    return _sparql_response(results)


async def _extract_sparql_query(request: Request) -> Optional[str]:
    if request.method == "GET":
        return request.query_params.get("query")
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        return form.get("query")
    body = await request.body()
    return body.decode("utf-8") if body else None


def _sparql_response(results: Any) -> Response:
    if isinstance(results, ox.QuerySolutions):
        variables = results.variables
        var_names = [v.value for v in variables]
        bindings = []
        for solution in results:
            row: dict[str, dict] = {}
            for var in variables:
                val = solution[var]
                if val is None:
                    continue
                if isinstance(val, ox.NamedNode):
                    row[var.value] = {"type": "uri", "value": val.value}
                elif isinstance(val, ox.BlankNode):
                    row[var.value] = {"type": "bnode", "value": val.value}
                elif isinstance(val, ox.Literal):
                    entry: dict = {"type": "literal", "value": val.value}
                    dt = val.datatype.value if val.datatype else None
                    if dt and dt != "http://www.w3.org/2001/XMLSchema#string":
                        entry["datatype"] = dt
                    if val.language:
                        entry["xml:lang"] = val.language
                    row[var.value] = entry
            bindings.append(row)
        data: dict = {"head": {"vars": var_names}, "results": {"bindings": bindings}}
        return Response(
            content=json.dumps(data),
            media_type="application/sparql-results+json",
        )
    elif isinstance(results, bool):
        return Response(
            content=json.dumps({"boolean": results}),
            media_type="application/sparql-results+json",
        )
    else:
        # CONSTRUCT / DESCRIBE — serialize as N-Triples
        lines = []
        for triple in results:
            lines.append(f"{triple.subject.n3()} {triple.predicate.n3()} {triple.object.n3()} .")
        return Response(content="\n".join(lines), media_type="application/n-triples")


# =============================================================================
# API: BPMN upload & live processing
# =============================================================================

@app.post("/api/upload")
async def upload_bpmn(file: UploadFile = File(...)):
    if not (file.filename or "").endswith(".bpmn"):
        raise HTTPException(400, "Only .bpmn files are accepted")

    xml       = (await file.read()).decode("utf-8")
    stem      = Path(file.filename).stem  # type: ignore[arg-type]
    pack_name = stem.lower().replace(" ", "-").replace("_", "-")
    abox_iri  = f"https://w3id.org/norma-abox/{pack_name}"
    rules_iri = f"{abox_iri}/rules"

    # ── Rule extraction ───────────────────────────────────────────────────────
    try:
        nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(xml)
        for props in task_props.values():
            props.setdefault("_bpmn_source", file.filename or "upload.bpmn")
        _, rules_ir_raw, _ = enumerate_paths_and_build_ir(
            nodes=nodes,
            edges=edges,
            gateway_outgoing_index=gw_index,
            task_props=task_props,
        )
        rules_ir = [
            dataclasses.replace(r, source=file.filename or "upload.bpmn")
            for r in rules_ir_raw
        ]
    except Exception as exc:
        raise HTTPException(422, f"Rule extraction failed: {exc}")

    # ── SWRL export ───────────────────────────────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".swrl.owl", delete=False, mode="w") as tf:
        tmp_swrl = tf.name
    try:
        export_rules_to_owl(
            rules_ir,
            out_file=tmp_swrl,
            rules_iri=rules_iri,
            abox_iri=abox_iri,
        )
        swrl_owl = Path(tmp_swrl).read_text(encoding="utf-8")
    finally:
        Path(tmp_swrl).unlink(missing_ok=True)

    # ── ABox build (optional) ─────────────────────────────────────────────────
    abox_ttl: Optional[str] = None
    if _KG_AVAILABLE:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                bpmn_path = Path(tmpdir) / (file.filename or "upload.bpmn")
                bpmn_path.write_text(xml, encoding="utf-8")
                elements, _ = parse_bpmn_folder(Path(tmpdir))
                records  = to_json(elements)
                abox_ttl = to_turtle(records, str(bpmn_path.parent), abox_iri)
        except Exception as exc:
            print(f"[norma] ABox build skipped: {exc}")

    store = _build_store(abox_ttl) if (abox_ttl and _OX_AVAILABLE) else None

    _packs[pack_name] = {
        "abox_ttl":   abox_ttl or "",
        "swrl_owl":   swrl_owl,
        "store":      store,
        "rules_ir":   rules_ir,
        "task_props": task_props,
        "uploaded":   True,
    }

    return {
        "pack":        pack_name,
        "rules_count": len(rules_ir),
        "has_abox":    abox_ttl is not None,
        "has_swrl":    True,
    }


# =============================================================================
# API: KG graph data for visualization
# =============================================================================

@app.get("/api/pack/{pack}/graph")
async def pack_graph(pack: str):
    """Return nodes and edges for interactive D3 force-graph visualization."""
    p = _require_pack(pack)

    nodes: dict = {}
    edges: list = []
    seen_edges: set = set()

    def add_node(nid: str, label: str, ntype: str, meta: Optional[dict] = None) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, "type": ntype}
            if meta:
                nodes[nid].update(meta)

    def add_edge(src: str, tgt: str, lbl: str) -> None:
        key = (src, tgt, lbl)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({"source": src, "target": tgt, "label": lbl})

    def camel_split(s: str) -> str:
        return " ".join(re.findall(r"[A-Z][a-z]*|[a-z]+", s)) or s

    for rule in p["rules_ir"]:
        dat  = {d.predicate.name: d.value for d in rule.data_atoms}
        robj = {r.predicate.name: r.object.name for r in rule.relations}
        rsbj = {r.predicate.name: r.subject.name for r in rule.relations}

        norm_id      = dat.get("deonticId") or rule.rid
        action_label = dat.get("actionText") or norm_id

        dtype = "Norm"
        for action in rule.actions:
            if action.name:
                raw = action.name.split("|", 1)[0].strip()
                dtype = raw.capitalize() if raw else "Norm"
                break

        reg      = dat.get("fromRegulation", "")
        article  = dat.get("fromArticle", "")
        src_info = " · ".join(x for x in [reg, f"Art. {article}" if article else ""] if x)
        add_node(norm_id, action_label, dtype, {
            "source":      src_info,
            "regulation":  reg,
            "article":     article,
            "bpmn_source": rule.source,
        })

        agent_id = rsbj.get("isLegalAgentOf")
        if agent_id:
            agent_label = agent_id.replace("Agent_", "").replace("_", " ").title()
            add_node(agent_id, agent_label, "Agent")
            add_edge(agent_id, norm_id, "performs")

        obj_id = robj.get("hasObject")
        if obj_id:
            obj_label = dat.get("objectText") or obj_id.replace("Object_", "").replace("_", " ").title()
            add_node(obj_id, obj_label, "Object")
            add_edge(norm_id, obj_id, "acts on")

        bf_id = robj.get("hasBindingForce")
        if bf_id:
            add_node(bf_id, camel_split(bf_id), "BindingForce")
            add_edge(norm_id, bf_id, "binding force")

        risk_id = robj.get("hasComplianceCriticality")
        if risk_id:
            add_node(risk_id, camel_split(risk_id), "RiskLevel")
            add_edge(norm_id, risk_id, "risk level")

        for cond in rule.conditions:
            cond_id    = f"cond_{cond.predicate.name}"
            cond_label = cond.predicate.name.replace("_", " ")
            add_node(cond_id, cond_label, "Condition")
            branch = "when true" if cond.value else "when false"
            add_edge(cond_id, norm_id, branch)

    return {"nodes": list(nodes.values()), "edges": edges}


# =============================================================================
# API: full annotation viewer (all template fields per norm)
# =============================================================================

@app.get("/api/pack/{pack}/norms")
async def pack_norms(pack: str):
    """
    Return every annotated BPMN element (one entry per task / gateway),
    with the complete Camunda template fields read directly from task_props
    and the minimal gateway conditions that trigger each norm.
    """
    p = _require_pack(pack)
    raw_props: dict = p.get("task_props", {})

    # ── Build norm_id → minimal conditions across all rules that contain it ──
    #    "minimal" = intersection of condition sets: conditions that are the
    #    same (same predicate + same value) on every path that includes this norm.
    norm_to_cond_sets: dict = {}  # norm_id → list[frozenset[(pred, val)]]
    norm_to_first_conds: dict = {}  # norm_id → first condition list (for label fallback)
    for rule in p["rules_ir"]:
        rule_norm_ids = _norm_ids_in_rule(rule)
        rule_cond_set = frozenset((c.predicate.name, c.value) for c in rule.conditions)
        rule_cond_list = [
            {"predicate": c.predicate.name, "label": c.predicate.name.replace("_", " "), "value": c.value}
            for c in rule.conditions
        ]
        for nid in rule_norm_ids:
            norm_to_cond_sets.setdefault(nid, []).append(rule_cond_set)
            norm_to_first_conds.setdefault(nid, rule_cond_list)

    def _minimal_conditions(norm_id: str) -> list:
        sets = norm_to_cond_sets.get(norm_id)
        if not sets:
            return []
        common = sets[0]
        for s in sets[1:]:
            common = common & s
        # Sort by predicate name for stable output
        return [
            {"predicate": pred, "label": pred.replace("_", " "), "value": val}
            for pred, val in sorted(common)
        ]

    def g(d: dict, key: str) -> str:
        return (d.get(key) or "").strip()

    result = []
    seen: set = set()

    for bpmn_id, props in raw_props.items():
        etype     = (props.get("compliance_elementType") or "task").strip()
        dtype     = (props.get("compliance_deonticType") or "").strip().lower()
        bpmn_name = (props.get("_bpmn_name") or "").strip()

        # Compute canonical norm_id — same logic as extractor
        raw_did = (props.get("compliance_deonticId") or "").strip()
        if raw_did:
            norm_id = raw_did
        elif dtype:
            norm_id = auto_deontic_id(dtype, bpmn_name, bpmn_id)
        else:
            norm_id = bpmn_id  # gateway with no deontic type

        if norm_id in seen:
            continue
        seen.add(norm_id)

        result.append({
            "rule_id":    bpmn_id,
            "norm_id":    norm_id,
            # ── Source provenance ─────────────────────────────────────────────
            "bpmn_source":  g(props, "_bpmn_source"),
            "element_type": etype,
            # ── Deontic Norm ──────────────────────────────────────────────────
            "deontic_type":   dtype,
            "norm_statement": g(props, "compliance_normStatement"),
            "agent":          g(props, "compliance_agent"),
            "action":         g(props, "compliance_action"),
            "object":         g(props, "compliance_object"),
            "fact_statement": g(props, "compliance_factStatement"),
            "binding_force":  g(props, "compliance_bindingForce"),
            # ── Legal Condition (gateway fields) ──────────────────────────────
            "gw_condition_statement": g(props, "gw_conditionStatement"),
            "gw_true_branch":         g(props, "gw_trueBranch"),
            "gw_false_branch":        g(props, "gw_falseBranch"),
            # ── Legal Source ──────────────────────────────────────────────────
            "regulation":     g(props, "compliance_regulation"),
            "article":        g(props, "compliance_article"),
            "paragraph":      g(props, "compliance_paragraph"),
            "original_text":  g(props, "compliance_originalText"),
            "regulation_uri": g(props, "compliance_regulationURI"),
            # ── Scope & Temporal ──────────────────────────────────────────────
            "trigger_condition": g(props, "compliance_triggerCondition"),
            "jurisdiction":      g(props, "compliance_jurisdiction"),
            "effective_date":    g(props, "compliance_effectiveDate"),
            "deadline":          g(props, "compliance_deadline"),
            "status":            g(props, "compliance_status"),
            # ── Consequences & Exceptions ─────────────────────────────────────
            "exception":  g(props, "compliance_exception"),
            "sanction":   g(props, "compliance_sanction"),
            "risk_level": g(props, "compliance_riskLevel"),
            # ── Annotation Metadata ───────────────────────────────────────────
            "extraction_method": g(props, "compliance_extractionMethod"),
            "confidence":        g(props, "compliance_confidence"),
            "legal_review":      g(props, "compliance_legalReview"),
            "annotator":         g(props, "compliance_annotator"),
            "annotation_date":   g(props, "compliance_annotationDate"),
            "last_review_date":  g(props, "compliance_lastReviewDate"),
            # ── Conditions: minimal set that triggers this norm ───────────────
            "conditions": _minimal_conditions(norm_id),
        })

    return {"norms": result}


_NORM_FIELD_MAP: dict = {
    "element_type":            "compliance_elementType",
    "deontic_type":            "compliance_deonticType",
    "norm_statement":          "compliance_normStatement",
    "gw_condition_statement":  "gw_conditionStatement",
    "gw_true_branch":          "gw_trueBranch",
    "gw_false_branch":         "gw_falseBranch",
    "agent":              "compliance_agent",
    "action":             "compliance_action",
    "object":             "compliance_object",
    "fact_statement":     "compliance_factStatement",
    "binding_force":      "compliance_bindingForce",
    "regulation":         "compliance_regulation",
    "article":            "compliance_article",
    "paragraph":          "compliance_paragraph",
    "original_text":      "compliance_originalText",
    "regulation_uri":     "compliance_regulationURI",
    "jurisdiction":       "compliance_jurisdiction",
    "trigger_condition":  "compliance_triggerCondition",
    "status":             "compliance_status",
    "effective_date":     "compliance_effectiveDate",
    "deadline":           "compliance_deadline",
    "risk_level":         "compliance_riskLevel",
    "sanction":           "compliance_sanction",
    "exception":          "compliance_exception",
    "extraction_method":  "compliance_extractionMethod",
    "confidence":         "compliance_confidence",
    "legal_review":       "compliance_legalReview",
    "annotator":          "compliance_annotator",
    "annotation_date":    "compliance_annotationDate",
    "last_review_date":   "compliance_lastReviewDate",
}


@app.patch("/api/pack/{pack}/norm/{norm_id}")
async def update_norm(pack: str, norm_id: str, request: Request):
    """Update annotation fields for a single norm in the in-memory task_props store."""
    p = _require_pack(pack)
    body = await request.json()
    raw_props: dict = p.setdefault("task_props", {})

    # Find the task entry whose deontic ID (explicit or auto-generated) matches
    target_key: Optional[str] = None
    for task_key, props in raw_props.items():
        explicit = (props.get("compliance_deonticId") or "").strip()
        if explicit == norm_id:
            target_key = task_key
            break
        # Try auto-generated ID
        dtype = (props.get("compliance_deonticType") or "").strip().lower()
        bpmn_name = (props.get("_bpmn_name") or "").strip()
        if dtype and auto_deontic_id(dtype, bpmn_name, task_key) == norm_id:
            target_key = task_key
            break

    # If no entry found, create one keyed by norm_id
    if target_key is None:
        target_key = norm_id
        raw_props[target_key] = {"compliance_deonticId": norm_id}

    updated: list = []
    for field_key, value in body.items():
        prop_key = _NORM_FIELD_MAP.get(field_key)
        if prop_key:
            raw_props[target_key][prop_key] = str(value)
            updated.append(field_key)

    return {"norm_id": norm_id, "updated": updated}


@app.get("/api/sparql-presets")
async def sparql_presets_list():
    """Return the curated list of SPARQL preset queries from sparql_presets.py."""
    return {"presets": SPARQL_PRESETS}


@app.get("/api/download/template")
async def download_template():
    """Serve the Camunda 8 element template JSON file as a download."""
    template_path = Path(__file__).parent.parent / "camunda-template" / "camunda8-compliance-template.json"
    if not template_path.exists():
        raise HTTPException(404, "Template file not found")
    content = template_path.read_bytes()
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="camunda8-compliance-template.json"'},
    )


# =============================================================================
# Helper
# =============================================================================

def _require_pack(name: str) -> dict[str, Any]:
    p = _packs.get(name)
    if p is None:
        avail = list(_packs.keys())
        raise HTTPException(404, f"Pack '{name}' not found. Available: {avail}")
    return p
