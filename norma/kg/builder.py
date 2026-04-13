#!/usr/bin/env python3
"""
kg_builder.py
=============
NORMA Knowledge Graph Builder — BPMN folder → ABox Turtle + JSON intermediate.

Parses BPMN files annotated with Zeebe compliance properties and produces:
  - A JSON intermediate record list (one record per annotated element)
  - A Turtle ABox that imports the NORMA TBox and declares all individuals

Usage (standalone CLI)
----------------------
python kg_builder.py examples/1.bpmn --ttl outputs/1.abox.ttl
python kg_builder.py regulations/eu-ai-act/bpmn/ --normalize --ttl eu_ai_act.abox.ttl
python kg_builder.py regulations/eu-ai-act/bpmn/ --template overrides.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

# ── Namespace map ──────────────────────────────────────────────────────────────

NS = {
    "bpmn":  "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "zeebe": "http://camunda.org/schema/zeebe/1.0",
}

NORMA_IRI = "https://w3id.org/norma-ontology#"
NORMA_ONT = "https://w3id.org/norma-ontology"

# ── Controlled-vocabulary mappings (template dropdown → OWL individual IRI) ───

DEONTIC_CLASS = {
    "obligation":       f"{NORMA_IRI}Obligation",
    "prohibition":      f"{NORMA_IRI}Prohibition",
    "permission":       f"{NORMA_IRI}Permission",
    "recommendation":   f"{NORMA_IRI}Recommendation",
    "recommendation_not": f"{NORMA_IRI}NegativeRecommendation",
    "fact":             f"{NORMA_IRI}ConstitutiveRule",
}

BINDING_FORCE = {
    "hard_law":        f"{NORMA_IRI}HardLaw",
    "soft_law":        f"{NORMA_IRI}SoftLaw",
    "internal_policy": f"{NORMA_IRI}InternalPolicy",
    "contractual":     f"{NORMA_IRI}Contractual",
}

NORM_STATUS = {
    "active":       f"{NORMA_IRI}Active",
    "under_review": f"{NORMA_IRI}UnderReview",
    "disputed":     f"{NORMA_IRI}Disputed",
    "superseded":   f"{NORMA_IRI}Superseded",
    "pending":      f"{NORMA_IRI}NotYetInForce",
}

RISK_LEVEL = {
    "critical": f"{NORMA_IRI}CriticalRisk",
    "high":     f"{NORMA_IRI}HighRisk",
    "medium":   f"{NORMA_IRI}MediumRisk",
    "low":      f"{NORMA_IRI}LowRisk",
}

EXTRACTION = {
    "manual_lawyer":   f"{NORMA_IRI}ManualLawyer",
    "manual_analyst":  f"{NORMA_IRI}ManualAnalyst",
    "llm":             f"{NORMA_IRI}LLMExtraction",
    "pattern-matching": f"{NORMA_IRI}PatternMatching",
    "rule-based":      f"{NORMA_IRI}RuleBased",
}

REVIEW = {
    "approved": f"{NORMA_IRI}Approved",
    "pending":  f"{NORMA_IRI}PendingReview",
    "none":     f"{NORMA_IRI}NotReviewed",
}

# ── Optional normalizer ────────────────────────────────────────────────────────

try:
    from norma.kg.normalizer import normalize as _normalize, save_override_template as _save_template
    _NORMALIZER_AVAILABLE = True
except ImportError:
    _NORMALIZER_AVAILABLE = False


# =============================================================================
# String helpers
# =============================================================================

def slug(text: str) -> str:
    """Convert an arbitrary label to a valid IRI local name."""
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_]", "_", text.strip())).strip("_")


def esc(s: str) -> str:
    """Escape a string for use inside a Turtle double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def lit(value: str, dtype: str = "xsd:string") -> str:
    """Wrap a value as a typed Turtle literal."""
    return f'"{esc(value)}"^^{dtype}'


# =============================================================================
# Turtle triple helpers
# =============================================================================

def _dp(triples: list, prop: str, val: str, dtype: str = "xsd:string") -> None:
    """Append a data-property triple if val is non-empty."""
    if val:
        triples.append(f"    norma:{prop} {lit(val, dtype)} ;")


def _op(triples: list, prop: str, vocab: dict, record: dict, key: str) -> None:
    """Append an object-property triple using a controlled-vocabulary dict."""
    v = record.get(key, "")
    if v and v in vocab:
        triples.append(f"    norma:{prop} <{vocab[v]}> ;")


def _close(triples: list) -> None:
    """Replace the trailing ' ;' on the last triple with '.'."""
    triples[-1] = triples[-1].rstrip(" ;") + "."


# =============================================================================
# BPMN parsing
# =============================================================================

def extract_props(el: ET.Element) -> dict:
    """Return the Zeebe property map for a BPMN element (empty if none)."""
    bns, zns = NS["bpmn"], NS["zeebe"]
    props: dict = {}
    ext = el.find(f"{{{bns}}}extensionElements")
    if ext is None:
        return props
    zp = ext.find(f"{{{zns}}}properties")
    if zp is None:
        return props
    for z in zp.findall(f"{{{zns}}}property"):
        name = z.get("name")
        if name:
            props[name] = z.get("value", "").strip()
    return props


def parse_bpmn(path: str | Path) -> list[dict]:
    """Parse a single BPMN file. Returns a list of annotated element dicts."""
    bns = NS["bpmn"]
    tree = ET.parse(path)
    root = tree.getroot()
    els: list[dict] = []

    task_tags = [
        "task", "userTask", "serviceTask", "manualTask",
        "businessRuleTask", "sendTask", "scriptTask",
    ]
    for tag in task_tags:
        for el in root.iter(f"{{{bns}}}{tag}"):
            p = extract_props(el)
            if p:
                els.append({
                    "id":          el.get("id"),
                    "bpmn_type":   "task",
                    "bpmn_name":   el.get("name", ""),
                    "props":       p,
                    "source_file": str(path),
                })

    for el in root.iter(f"{{{bns}}}exclusiveGateway"):
        p = extract_props(el)
        if p:
            els.append({
                "id":          el.get("id"),
                "bpmn_type":   "exclusiveGateway",
                "bpmn_name":   el.get("name", ""),
                "props":       p,
                "source_file": str(path),
            })

    return els


def parse_bpmn_folder(folder: str | Path) -> tuple[list[dict], list[Path]]:
    """Parse all *.bpmn files in a folder. Returns (elements, file_list)."""
    folder = Path(folder)
    bpmn_files = sorted(folder.glob("*.bpmn"))
    if not bpmn_files:
        raise FileNotFoundError(f"No .bpmn files found in {folder}")
    all_elements: list[dict] = []
    for f in bpmn_files:
        elements = parse_bpmn(f)
        all_elements.extend(elements)
        print(f"    {f.name}: {len(elements)} elements")
    return all_elements, bpmn_files


# =============================================================================
# JSON intermediate
# =============================================================================

def to_json(elements: list[dict]) -> list[dict]:
    """Convert parsed BPMN elements to the JSON intermediate record format."""
    records: list[dict] = []
    for el in elements:
        p = el["props"]
        etype = p.get("compliance_elementType", el["bpmn_type"])
        r: dict = {
            "bpmn_id":      el["id"],
            "bpmn_name":    el["bpmn_name"],
            "element_type": etype,
        }

        if etype == "task":
            trigger = p.get("compliance_triggerCondition") or p.get("compliance_condition", "")
            r.update({
                "deontic_type":      p.get("compliance_deonticType", ""),
                "binding_force":     p.get("compliance_bindingForce", ""),
                "norm_status":       p.get("compliance_status", ""),
                "risk_level":        p.get("compliance_riskLevel", ""),
                "extraction_method": p.get("compliance_extractionMethod", ""),
                "review_status":     p.get("compliance_legalReview", ""),
                "deontic_id":        p.get("compliance_deonticId", ""),
                "norm_statement":    p.get("compliance_normStatement", ""),
                "agent":             p.get("compliance_agent", ""),
                "action":            p.get("compliance_action", ""),
                "object":            p.get("compliance_object", ""),
                "fact_statement":    p.get("compliance_factStatement", ""),
                "trigger_condition": trigger,
                "jurisdiction":      p.get("compliance_jurisdiction", ""),
                "effective_date":    p.get("compliance_effectiveDate", ""),
                "deadline":          p.get("compliance_deadline", ""),
                "exception":         p.get("compliance_exception", ""),
                "sanction":          p.get("compliance_sanction", ""),
                "cross_refs":        p.get("compliance_crossRefs", ""),
                "regulation":        p.get("compliance_regulation", ""),
                "article":           p.get("compliance_article", ""),
                "paragraph":         p.get("compliance_paragraph", ""),
                "original_text":     p.get("compliance_originalText", ""),
                "regulation_uri":    p.get("compliance_regulationURI", ""),
                "confidence":        p.get("compliance_confidence", ""),
                "annotator":         p.get("compliance_annotator", ""),
                "annotation_date":   p.get("compliance_annotationDate", ""),
                "last_review_date":  p.get("compliance_lastReviewDate", ""),
            })

        elif etype == "exclusiveGateway":
            r.update({
                "norm_status":        p.get("compliance_status", ""),
                "extraction_method":  p.get("compliance_extractionMethod", ""),
                "review_status":      p.get("compliance_legalReview", ""),
                "condition_statement": p.get("gw_conditionStatement", ""),
                "true_branch":        p.get("gw_trueBranch", "Yes"),
                "false_branch":       p.get("gw_falseBranch", "No"),
                "cross_refs":         p.get("gw_crossRefs", ""),
                "jurisdiction":       p.get("compliance_jurisdiction", ""),
                "effective_date":     p.get("compliance_effectiveDate", ""),
                "deadline":           p.get("compliance_deadline", ""),
                "regulation":         p.get("compliance_regulation", ""),
                "article":            p.get("compliance_article", ""),
                "paragraph":          p.get("compliance_paragraph", ""),
                "original_text":      p.get("compliance_originalText", ""),
                "regulation_uri":     p.get("compliance_regulationURI", ""),
                "confidence":         p.get("compliance_confidence", ""),
                "annotator":          p.get("compliance_annotator", ""),
                "annotation_date":    p.get("compliance_annotationDate", ""),
                "last_review_date":   p.get("compliance_lastReviewDate", ""),
            })

        records.append(r)
    return records


# =============================================================================
# Turtle ABox generator
# =============================================================================

def to_turtle(records: list[dict], source: str, base_iri: str) -> str:
    """Convert JSON intermediate records to a Turtle ABox string."""
    lines: list[str] = []

    # ── Ontology header ───────────────────────────────────────────────────────
    lines += [
        f"# ABox from: {source}",
        f"# TBox:    {NORMA_ONT}",
        "",
        f"@prefix norma: <{NORMA_IRI}> .",
        f"@prefix :      <{base_iri}#> .",
        "@prefix owl:   <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"<{base_iri}>",
        "    a owl:Ontology ;",
        f'    owl:imports <{NORMA_ONT}> .',
        "",
    ]

    # ── Collect unique agents, objects, regulations ───────────────────────────
    agents:      dict[str, str] = {}
    objects:     dict[str, str] = {}
    regulations: dict[str, str] = {}

    for r in records:
        if r["element_type"] == "task":
            ag  = r.get("agent", "")
            ob  = r.get("object", "")
            reg = r.get("regulation", "")
            if ag  and ag  not in agents:      agents[ag]      = f"Agent_{slug(ag)}"
            if ob  and ob  not in objects:     objects[ob]     = f"Object_{slug(ob)}"
            if reg and reg not in regulations: regulations[reg] = f"Regulation_{slug(reg)}"
        elif r["element_type"] == "exclusiveGateway":
            reg = r.get("regulation", "")
            if reg and reg not in regulations: regulations[reg] = f"Regulation_{slug(reg)}"

    # ── Agents ────────────────────────────────────────────────────────────────
    if agents:
        lines.append("# ── Agents ───────────────────────────────────────────────────────")
        for label, local in agents.items():
            lines += [
                f":{local}",
                "    a owl:NamedIndividual, norma:Agent ;",
                f'    rdfs:label "{esc(label)}"@en .',
                "",
            ]

    # ── Legal Objects ─────────────────────────────────────────────────────────
    if objects:
        lines.append("# ── Legal Objects ────────────────────────────────────────────────")
        for label, local in objects.items():
            lines += [
                f":{local}",
                "    a owl:NamedIndividual, norma:LegalObject ;",
                f'    rdfs:label "{esc(label)}"@en .',
                "",
            ]

    # ── Legal Sources (regulations) ───────────────────────────────────────────
    if regulations:
        # Pre-collect provenance (URI + articles) per regulation label
        reg_prov: dict[str, dict] = {}
        for label in regulations:
            uri = ""
            arts: list[tuple[str, str, str]] = []
            seen: set[tuple[str, str]] = set()
            for r in records:
                if r.get("regulation") != label:
                    continue
                if r.get("regulation_uri") and not uri:
                    uri = r["regulation_uri"]
                art = r.get("article", "")
                par = r.get("paragraph", "")
                txt = r.get("original_text", "")
                if art and (art, par) not in seen:
                    seen.add((art, par))
                    arts.append((art, par, txt))
            reg_prov[label] = {"uri": uri, "articles": arts}

        lines.append("# ── Legal Sources ────────────────────────────────────────────────")
        for label, local in regulations.items():
            prov = reg_prov[label]
            T: list[str] = [
                f":{local}",
                "    a owl:NamedIndividual, norma:LegalSource ;",
                f"    norma:regulationName {lit(label)} ;",
            ]
            if prov["uri"]:
                T.append(f'    norma:regulationURI "{esc(prov["uri"])}"^^xsd:anyURI ;')
            for art, par, txt in prov["articles"]:
                T.append(f"    norma:articleNumber {lit(art)} ;")
                if par:
                    T.append(f"    norma:paragraphNumber {lit(par)} ;")
                if txt:
                    T.append(f"    norma:originalText {lit(txt)} ;")
            _close(T)
            lines += T + [""]

    # ── Norms (tasks) ─────────────────────────────────────────────────────────
    lines.append("# ── Norms ────────────────────────────────────────────────────────────")
    for r in records:
        if r["element_type"] != "task":
            continue

        did        = r.get("deontic_id") or r["bpmn_id"]
        dtype      = r.get("deontic_type", "obligation")
        local      = slug(did) or slug(r["bpmn_id"])
        owl_class  = DEONTIC_CLASS.get(dtype, f"{NORMA_IRI}RegulativeNorm")

        T = [
            f":{local}",
            f"    a owl:NamedIndividual, <{owl_class}> ;",
            f'    rdfs:label "{esc(r["bpmn_name"])}"@en ;',
        ]

        # Data properties
        _dp(T, "deonticId",        did)
        _dp(T, "normStatement",    r.get("norm_statement", ""))
        _dp(T, "action",           r.get("action", ""))
        _dp(T, "factStatement",    r.get("fact_statement", ""))
        _dp(T, "conditionTrigger", r.get("trigger_condition", ""))
        _dp(T, "jurisdiction",     r.get("jurisdiction", ""))
        _dp(T, "exception",        r.get("exception", ""))
        _dp(T, "sanction",         r.get("sanction", ""))
        _dp(T, "crossRefsNorm",    r.get("cross_refs", ""))
        _dp(T, "annotator",        r.get("annotator", ""))
        _dp(T, "fromRegulation",   r.get("regulation", ""))
        _dp(T, "fromArticle",      r.get("article", ""))
        _dp(T, "fromParagraph",    r.get("paragraph", ""))

        for prop, key in [
            ("effectiveDate",   "effective_date"),
            ("deadline",        "deadline"),
            ("annotationDate",  "annotation_date"),
            ("lastReviewDate",  "last_review_date"),
        ]:
            if r.get(key):
                T.append(f"    norma:{prop} {lit(r[key], 'xsd:date')} ;")

        if r.get("confidence"):
            T.append(f"    norma:confidenceScore {lit(r['confidence'], 'xsd:decimal')} ;")
        if r.get("regulation_uri"):
            T.append(f'    norma:sourceURI "{esc(r["regulation_uri"])}"^^xsd:anyURI ;')

        # Object properties — controlled vocabularies
        _op(T, "hasBindingForce",     BINDING_FORCE, r, "binding_force")
        _op(T, "hasNormStatus",       NORM_STATUS,   r, "norm_status")
        _op(T, "hasRiskLevel",        RISK_LEVEL,    r, "risk_level")
        _op(T, "hasExtractionMethod", EXTRACTION,    r, "extraction_method")
        _op(T, "hasReviewStatus",     REVIEW,        r, "review_status")

        # Object properties — linked individuals
        ag  = r.get("agent", "")
        ob  = r.get("object", "")
        reg = r.get("regulation", "")
        if ag  and ag  in agents:      T.append(f"    norma:hasAgent       :{agents[ag]} ;")
        if ob  and ob  in objects:     T.append(f"    norma:actsOn         :{objects[ob]} ;")
        if reg and reg in regulations: T.append(f"    norma:hasLegalSource :{regulations[reg]} ;")

        _close(T)
        lines += T + [""]

    # ── Legal Conditions (gateways) ───────────────────────────────────────────
    lines.append("# ── Legal Conditions (Gateways) ──────────────────────────────────────")
    for r in records:
        if r["element_type"] != "exclusiveGateway":
            continue

        local = f"Condition_{slug(r['bpmn_id'])}"
        cond  = r.get("condition_statement", r["bpmn_name"])

        T = [
            f":{local}",
            "    a owl:NamedIndividual, norma:LegalCondition ;",
            f'    rdfs:label "{esc(cond)}"@en ;',
            f"    norma:conditionStatement {lit(cond)} ;",
        ]

        if r.get("true_branch"):
            T.append(f"    norma:trueBranchLabel  {lit(r['true_branch'])} ;")
        if r.get("false_branch"):
            T.append(f"    norma:falseBranchLabel {lit(r['false_branch'])} ;")
        if r.get("cross_refs"):
            T.append(f"    norma:crossRefsGateway {lit(r['cross_refs'])} ;")
        if r.get("confidence"):
            T.append(f"    norma:confidenceScore {lit(r['confidence'], 'xsd:decimal')} ;")
        if r.get("annotator"):
            T.append(f"    norma:annotator {lit(r['annotator'])} ;")
        if r.get("annotation_date"):
            T.append(f"    norma:annotationDate {lit(r['annotation_date'], 'xsd:date')} ;")

        _op(T, "hasNormStatus",       NORM_STATUS, r, "norm_status")
        _op(T, "hasExtractionMethod", EXTRACTION,  r, "extraction_method")
        _op(T, "hasReviewStatus",     REVIEW,      r, "review_status")

        reg = r.get("regulation", "")
        if reg and reg in regulations:
            T.append(f"    norma:hasLegalSource :{regulations[reg]} ;")

        _close(T)
        lines += T + [""]

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="NORMA KG Builder — BPMN folder → Knowledge Graph (ABox Turtle)"
    )
    parser.add_argument("input",
        help="Path to a single .bpmn file or a folder of .bpmn files")
    parser.add_argument("--json",      default=None,
        help="Output JSON intermediate file")
    parser.add_argument("--ttl",       default=None,
        help="Output Turtle ABox file")
    parser.add_argument("--base",      default="https://w3id.org/norma-abox",
        help="ABox base IRI")
    parser.add_argument("--normalize", action="store_true",
        help="Run entity label normalization")
    parser.add_argument("--override",  default=None,
        help="JSON override file for normalization")
    parser.add_argument("--template",  default=None,
        help="Save normalization override template and exit")
    parser.add_argument("--threshold", type=float, default=0.82,
        help="Fuzzy similarity threshold (default: 0.82)")
    args = parser.parse_args()

    input_path = Path(args.input)

    # ── Parse: single file or folder ─────────────────────────────────────────
    print(f"[1] Parsing: {input_path}")
    if input_path.is_dir():
        elements, bpmn_files = parse_bpmn_folder(input_path)
        source_label = str(input_path)
        out_stem     = input_path.name
    elif input_path.is_file() and input_path.suffix == ".bpmn":
        elements     = parse_bpmn(input_path)
        bpmn_files   = [input_path]
        source_label = str(input_path)
        out_stem     = input_path.stem
    else:
        print("[!] Input must be a .bpmn file or a folder containing .bpmn files.")
        sys.exit(1)

    print(f"    Total: {len(elements)} elements from {len(bpmn_files)} file(s)")
    recs = to_json(elements)

    # ── Override template ─────────────────────────────────────────────────────
    if args.template:
        if not _NORMALIZER_AVAILABLE:
            print("[!] kg_normalizer.py not found.")
        else:
            _save_template(recs, args.template)
            print(f"[norma] Template written: {args.template}")
            print("[norma] Edit then re-run with --override <file>")
        return

    # ── Normalization ─────────────────────────────────────────────────────────
    step = 2
    if args.normalize or args.override:
        if not _NORMALIZER_AVAILABLE:
            print("[!] kg_normalizer.py not found — skipping normalization.")
        else:
            print(f"[{step}] Normalizing entity labels ...")
            recs, report = _normalize(recs, override_file=args.override, threshold=args.threshold)
            report.print()
            if report.has_issues():
                print("[!] Warnings require attention. Use --template to generate an override file.")
            step += 1

    # ── JSON intermediate ─────────────────────────────────────────────────────
    if args.json:
        jp = Path(args.json)
    elif input_path.is_dir():
        jp = input_path / f"{out_stem}.json"
    else:
        jp = input_path.with_suffix(".json")

    jp.write_text(json.dumps(recs, indent=2, ensure_ascii=False))
    print(f"[{step}] JSON: {jp}")
    step += 1

    # ── Turtle ABox ───────────────────────────────────────────────────────────
    ttl = to_turtle(recs, source_label, args.base)

    if args.ttl:
        tp = Path(args.ttl)
    elif input_path.is_dir():
        tp = input_path / f"{out_stem}.abox.ttl"
    else:
        tp = input_path.with_suffix(".abox.ttl")

    tp.write_text(ttl, encoding="utf-8")
    print(f"[{step}] Turtle ABox: {tp}")
    print("[✓] Done.")


if __name__ == "__main__":
    main()
