from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse

try:
    import pyoxigraph as ox

    OX_AVAILABLE = True
except ImportError:  # pragma: no cover
    ox = None  # type: ignore[assignment]
    OX_AVAILABLE = False


def build_store(ttl_text: str, ontology_path: Path, store_path: Optional[Path] = None):
    if not OX_AVAILABLE:
        return None
    if store_path:
        store_path.mkdir(parents=True, exist_ok=True)
        store = ox.Store(str(store_path))
        store.clear()
    else:
        store = ox.Store()
    store.load(ttl_text, format=ox.RdfFormat.TURTLE)
    if ontology_path.exists():
        store.load(ontology_path.read_text(encoding="utf-8"), format=ox.RdfFormat.TURTLE)
    if store_path:
        store.optimize()
    return store


def open_store(store_path: Path):
    if not OX_AVAILABLE:
        return None
    if not store_path.exists():
        return None
    return ox.Store.read_only(str(store_path))


def local_name(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rstrip("/").rsplit("/", 1)[-1]


def binding_value(row: Any, key: str) -> Optional[str]:
    try:
        value = row[key]
    except Exception:
        return None
    return value.value if value is not None else None


def _node_payload_from_store(store: Any, node_uri: str) -> Optional[dict[str, Any]]:
    metadata_query = f"""
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?type ?label ?regulation ?article ?paragraph ?source
                ?deonticId ?normStatement ?conditionStatement ?trigger
                ?agentText ?actionText ?objectText ?trueBranch ?falseBranch
                ?annotationDate ?confidenceScore
WHERE {{
  BIND(<{node_uri}> AS ?node)
  ?node rdf:type ?type .
  FILTER(
    STRSTARTS(STR(?type), "https://w3id.org/norma-ontology#") &&
    STR(?type) != "https://w3id.org/norma-ontology#NormativeContent" &&
    STR(?type) != "https://w3id.org/norma-ontology#RegulativeNorm"
  )
  OPTIONAL {{ ?node rdfs:label ?label . }}
  OPTIONAL {{ ?node norma:fromRegulation ?regulation . }}
  OPTIONAL {{ ?node norma:fromArticle ?article . }}
  OPTIONAL {{ ?node norma:fromParagraph ?paragraph . }}
  OPTIONAL {{ ?node norma:sourceURI ?source . }}
  OPTIONAL {{ ?node norma:deonticId ?deonticId . }}
  OPTIONAL {{ ?node norma:normStatement ?normStatement . }}
  OPTIONAL {{ ?node norma:conditionStatement ?conditionStatement . }}
  OPTIONAL {{ ?node norma:conditionTrigger ?trigger . }}
  OPTIONAL {{ ?node norma:agentText ?agentText . }}
  OPTIONAL {{ ?node norma:actionText ?actionText . }}
  OPTIONAL {{ ?node norma:objectText ?objectText . }}
  OPTIONAL {{ ?node norma:trueBranchLabel ?trueBranch . }}
  OPTIONAL {{ ?node norma:falseBranchLabel ?falseBranch . }}
  OPTIONAL {{ ?node norma:annotationDate ?annotationDate . }}
  OPTIONAL {{ ?node norma:confidenceScore ?confidenceScore . }}
}}
ORDER BY ?type
LIMIT 1
"""
    for row in store.query(metadata_query):
        type_uri = binding_value(row, "type")
        if not type_uri:
            continue
        return {
            "id": node_uri,
            "label": binding_value(row, "label") or local_name(node_uri),
            "type": local_name(type_uri),
            "regulation": binding_value(row, "regulation"),
            "article": binding_value(row, "article"),
            "paragraph": binding_value(row, "paragraph"),
            "source": binding_value(row, "source"),
            "deontic_id": binding_value(row, "deonticId"),
            "norm_statement": binding_value(row, "normStatement"),
            "condition_statement": binding_value(row, "conditionStatement"),
            "trigger_condition": binding_value(row, "trigger"),
            "agent": binding_value(row, "agentText"),
            "action": binding_value(row, "actionText"),
            "object": binding_value(row, "objectText"),
            "true_branch": binding_value(row, "trueBranch"),
            "false_branch": binding_value(row, "falseBranch"),
            "annotation_date": binding_value(row, "annotationDate"),
            "confidence": binding_value(row, "confidenceScore"),
        }
    return None


def semantic_graph_data(store: Any, pack: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if not OX_AVAILABLE or store is None:
        raise HTTPException(503, "Semantic graph store unavailable")

    node_query = """
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?node ?type ?label ?regulation ?article ?paragraph ?source
                ?deonticId ?normStatement ?conditionStatement ?trigger
                ?agentText ?actionText ?objectText ?trueBranch ?falseBranch
                ?annotationDate ?confidenceScore
WHERE {
  ?node rdf:type ?type .
  FILTER(STRSTARTS(STR(?node), "https://w3id.org/norma-abox/"))
  FILTER(STRSTARTS(STR(?type), "https://w3id.org/norma-ontology#"))
  FILTER(
    STR(?type) != "https://w3id.org/norma-ontology#NormativeContent" &&
    STR(?type) != "https://w3id.org/norma-ontology#RegulativeNorm"
  )
  OPTIONAL { ?node rdfs:label ?label . }
  OPTIONAL { ?node norma:fromRegulation ?regulation . }
  OPTIONAL { ?node norma:fromArticle ?article . }
  OPTIONAL { ?node norma:fromParagraph ?paragraph . }
  OPTIONAL { ?node norma:sourceURI ?source . }
  OPTIONAL { ?node norma:deonticId ?deonticId . }
  OPTIONAL { ?node norma:normStatement ?normStatement . }
  OPTIONAL { ?node norma:conditionStatement ?conditionStatement . }
  OPTIONAL { ?node norma:conditionTrigger ?trigger . }
  OPTIONAL { ?node norma:agentText ?agentText . }
  OPTIONAL { ?node norma:actionText ?actionText . }
  OPTIONAL { ?node norma:objectText ?objectText . }
  OPTIONAL { ?node norma:trueBranchLabel ?trueBranch . }
  OPTIONAL { ?node norma:falseBranchLabel ?falseBranch . }
  OPTIONAL { ?node norma:annotationDate ?annotationDate . }
  OPTIONAL { ?node norma:confidenceScore ?confidenceScore . }
}
ORDER BY ?type ?node
"""

    edge_query = """
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?source ?predicate ?target ?predicateLabel
WHERE {
  VALUES ?predicate {
    norma:hasLegalAgent norma:hasLegalAction norma:hasLegalObject
    norma:hasLegalSource norma:hasSourceExpression norma:triggersNorm
    norma:hasBindingForce norma:hasComplianceCriticality norma:hasNormStatus
    norma:hasExtractionMethod norma:hasReviewStatus
    norma:wasGeneratedByAnnotationActivity norma:wasAttributedToAnnotator
    norma:wasAssociatedWithAnnotator norma:usedLegalSource
    norma:wasDerivedFromSource norma:relatesTo norma:supersededBy
  }
  ?source ?predicate ?target .
  FILTER(isIRI(?source) && isIRI(?target))
  FILTER(
    STRSTARTS(STR(?source), "https://w3id.org/norma-abox/") &&
    STRSTARTS(STR(?target), "https://w3id.org/norma-abox/")
  )
  OPTIONAL { ?predicate rdfs:label ?predicateLabel . }
}
ORDER BY ?predicate ?source ?target
"""

    nodes: dict[str, dict[str, Any]] = {}
    edges = []
    seen_edges: set[tuple[str, str, str]] = set()

    node_results = store.query(node_query)
    for row in node_results:
        node_uri = binding_value(row, "node")
        type_uri = binding_value(row, "type")
        if not node_uri or not type_uri:
            continue
        node_id = node_uri
        node_type = local_name(type_uri)
        label = binding_value(row, "label") or local_name(node_uri)
        regulation = binding_value(row, "regulation")
        article = binding_value(row, "article")
        source = binding_value(row, "source")
        paragraph = binding_value(row, "paragraph")
        deontic_id = binding_value(row, "deonticId")
        norm_statement = binding_value(row, "normStatement")
        condition_statement = binding_value(row, "conditionStatement")
        trigger = binding_value(row, "trigger")
        agent_text = binding_value(row, "agentText")
        action_text = binding_value(row, "actionText")
        object_text = binding_value(row, "objectText")
        true_branch = binding_value(row, "trueBranch")
        false_branch = binding_value(row, "falseBranch")
        annotation_date = binding_value(row, "annotationDate")
        confidence = binding_value(row, "confidenceScore")
        existing = nodes.get(node_id)
        if existing is None:
            nodes[node_id] = {
                "id": node_id,
                "label": label,
                "type": node_type,
                "regulation": regulation,
                "article": article,
                "paragraph": paragraph,
                "source": source,
                "deontic_id": deontic_id,
                "norm_statement": norm_statement,
                "condition_statement": condition_statement,
                "trigger_condition": trigger,
                "agent": agent_text,
                "action": action_text,
                "object": object_text,
                "true_branch": true_branch,
                "false_branch": false_branch,
                "annotation_date": annotation_date,
                "confidence": confidence,
            }
        else:
            if not existing.get("label") and label:
                existing["label"] = label
            if regulation and not existing.get("regulation"):
                existing["regulation"] = regulation
            if article and not existing.get("article"):
                existing["article"] = article
            if paragraph and not existing.get("paragraph"):
                existing["paragraph"] = paragraph
            if source and not existing.get("source"):
                existing["source"] = source
            if deontic_id and not existing.get("deontic_id"):
                existing["deontic_id"] = deontic_id
            if norm_statement and not existing.get("norm_statement"):
                existing["norm_statement"] = norm_statement
            if condition_statement and not existing.get("condition_statement"):
                existing["condition_statement"] = condition_statement
            if trigger and not existing.get("trigger_condition"):
                existing["trigger_condition"] = trigger
            if agent_text and not existing.get("agent"):
                existing["agent"] = agent_text
            if action_text and not existing.get("action"):
                existing["action"] = action_text
            if object_text and not existing.get("object"):
                existing["object"] = object_text
            if true_branch and not existing.get("true_branch"):
                existing["true_branch"] = true_branch
            if false_branch and not existing.get("false_branch"):
                existing["false_branch"] = false_branch
            if annotation_date and not existing.get("annotation_date"):
                existing["annotation_date"] = annotation_date
            if confidence and not existing.get("confidence"):
                existing["confidence"] = confidence

    edge_results = store.query(edge_query)
    for row in edge_results:
        source_uri = binding_value(row, "source")
        target_uri = binding_value(row, "target")
        predicate_uri = binding_value(row, "predicate")
        if not source_uri or not target_uri or not predicate_uri:
            continue
        label = binding_value(row, "predicateLabel") or local_name(predicate_uri)
        if source_uri not in nodes or target_uri not in nodes:
            continue
        key = (source_uri, target_uri, label)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append({"source": source_uri, "target": target_uri, "label": label})

    return {"nodes": list(nodes.values()), "edges": edges}


async def extract_sparql_query(request: Request) -> Optional[str]:
    if request.method == "GET":
        return request.query_params.get("query")
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        return form.get("query")
    body = await request.body()
    return body.decode("utf-8") if body else None


def sparql_response(results: Any) -> Response:
    if isinstance(results, ox.QuerySolutions):
        variables = results.variables
        var_names = [v.value for v in variables]
        bindings = []
        for solution in results:
            row: dict[str, dict[str, str]] = {}
            for var in variables:
                val = solution[var]
                if val is None:
                    continue
                if isinstance(val, ox.NamedNode):
                    row[var.value] = {"type": "uri", "value": val.value}
                elif isinstance(val, ox.BlankNode):
                    row[var.value] = {"type": "bnode", "value": val.value}
                elif isinstance(val, ox.Literal):
                    entry: dict[str, str] = {"type": "literal", "value": val.value}
                    dt = val.datatype.value if val.datatype else None
                    if dt and dt != "http://www.w3.org/2001/XMLSchema#string":
                        entry["datatype"] = dt
                    if val.language:
                        entry["xml:lang"] = val.language
                    row[var.value] = entry
            bindings.append(row)
        data = {"head": {"vars": var_names}, "results": {"bindings": bindings}}
        return Response(
            content=json.dumps(data),
            media_type="application/sparql-results+json",
        )
    if isinstance(results, bool):
        return Response(
            content=json.dumps({"boolean": results}),
            media_type="application/sparql-results+json",
        )

    lines = []
    for triple in results:
        lines.append(f"{triple.subject.n3()} {triple.predicate.n3()} {triple.object.n3()} .")
    return Response(content="\n".join(lines), media_type="application/n-triples")


def rdf_download(ttl_text: str, pack: str) -> StreamingResponse:
    if not OX_AVAILABLE:
        raise HTTPException(503, "pyoxigraph not available - cannot convert to RDF/XML")
    store = ox.Store()
    store.load(ttl_text, format=ox.RdfFormat.TURTLE)
    buf = io.BytesIO()
    store.dump(buf, format=ox.RdfFormat.RDF_XML, from_graph=ox.DefaultGraph())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/rdf+xml",
        headers={"Content-Disposition": f'attachment; filename="{pack}.abox.rdf"'},
    )
