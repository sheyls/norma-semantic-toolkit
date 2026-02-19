from __future__ import annotations

from typing import Iterable, List, Set, Tuple
from xml.sax.saxutils import escape
import re

from src.transformations.rule_ir import RuleIR, RelationAtom, DataAtom

RDF_NIL    = "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"
XSD_BOOL   = "http://www.w3.org/2001/XMLSchema#boolean"
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"


def _indent(s: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line.strip() else line for line in s.splitlines())


def _var_iri(base_iri: str, actor: str) -> str:
    return f"{base_iri}#var_{actor}"


def _prop_iri(base_iri: str, local_name: str) -> str:
    return f"{base_iri}#{local_name}"


def _swrl_bool_atom(*, predicate_iri: str, var_iri: str, value: bool) -> str:
    return (
        "<swrl:DatavaluedPropertyAtom>\n"
        f'  <swrl:propertyPredicate rdf:resource="{escape(predicate_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(var_iri)}"/>\n'
        f'  <swrl:argument2 rdf:datatype="{XSD_BOOL}">{"true" if value else "false"}</swrl:argument2>\n'
        "</swrl:DatavaluedPropertyAtom>"
    )


def _swrl_task_atom(*, task_predicate_iri: str, var_iri: str, task_string: str) -> str:
    return (
        "<swrl:DatavaluedPropertyAtom>\n"
        f'  <swrl:propertyPredicate rdf:resource="{escape(task_predicate_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(var_iri)}"/>\n'
        f'  <swrl:argument2 rdf:datatype="{XSD_STRING}">{escape(task_string)}</swrl:argument2>\n'
        "</swrl:DatavaluedPropertyAtom>"
    )


def _swrl_object_atom(*, predicate_iri: str, subject_iri: str, object_iri: str) -> str:
    return (
        "<swrl:IndividualPropertyAtom>\n"
        f'  <swrl:propertyPredicate rdf:resource="{escape(predicate_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(subject_iri)}"/>\n'
        f'  <swrl:argument2 rdf:resource="{escape(object_iri)}"/>\n'
        "</swrl:IndividualPropertyAtom>"
    )


def _swrl_data_atom(*, predicate_iri: str, subject_iri: str, value: str, datatype: str) -> str:
    xsd_iri = (
        datatype if datatype.startswith("http")
        else f"http://www.w3.org/2001/XMLSchema#{datatype.replace('xsd:', '')}"
    )
    return (
        "<swrl:DatavaluedPropertyAtom>\n"
        f'  <swrl:propertyPredicate rdf:resource="{escape(predicate_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(subject_iri)}"/>\n'
        f'  <swrl:argument2 rdf:datatype="{escape(xsd_iri)}">{escape(value)}</swrl:argument2>\n'
        "</swrl:DatavaluedPropertyAtom>"
    )


def _deontic_predicate_for_action(a_name: str) -> str:
    s = (a_name or "").strip()

    if "|" in s:
        head = s.split("|", 1)[0].strip().upper()
        mapping = {
            "OBL":                "obligation",
            "OBLIGATION":         "obligation",
            "PRH":                "prohibition",
            "PRO":                "prohibition",
            "PROHIBITION":        "prohibition",
            "PER":                "permission",
            "PERMISSION":         "permission",
            "REC":                "recommendation",
            "RECOMMENDATION":     "recommendation",
            "REC_NOT":            "recommendation_not",
            "RECOMMENDATION_NOT": "recommendation_not",
            "FACT":               "fact",
            "FCT":                "fact",
        }
        if head in mapping:
            return mapping[head]

    m = re.search(r"(?:^|[;,\s])dtype\s*=\s*([a-zA-Z_]+)", s, flags=re.IGNORECASE)
    if m:
        dt = m.group(1).strip().lower()
        mapping = {
            "obligation":         "obligation",
            "permission":         "permission",
            "prohibition":        "prohibition",
            "recommendation":     "recommendation",
            "recommendation_not": "recommendation_not",
            "fact":               "fact",
        }
        if dt in mapping:
            return mapping[dt]

    return "task"


def _atom_list_xml(atoms_xml: List[str], indent: int) -> str:
    pad = " " * indent
    if not atoms_xml:
        return f'{pad}<rdf:Description rdf:about="{RDF_NIL}"/>'

    first = atoms_xml[0]
    rest  = atoms_xml[1:]

    if not rest:
        return (
            f"{pad}<swrl:AtomList>\n"
            f"{pad}  <rdf:first>\n{_indent(first, indent + 4)}\n{pad}  </rdf:first>\n"
            f'{pad}  <rdf:rest rdf:resource="{RDF_NIL}"/>\n'
            f"{pad}</swrl:AtomList>"
        )

    return (
        f"{pad}<swrl:AtomList>\n"
        f"{pad}  <rdf:first>\n{_indent(first, indent + 4)}\n{pad}  </rdf:first>\n"
        f"{pad}  <rdf:rest>\n{_atom_list_xml(rest, indent + 4)}\n{pad}  </rdf:rest>\n"
        f"{pad}</swrl:AtomList>"
    )


def rule_ir_to_swrl_xml(
    ir: RuleIR,
    *,
    base_iri: str,
    task_predicate: str = "task",
) -> str:
    # ── Body: conditions ─────────────────────────────────────────────
    body_atoms: List[str] = []
    for c in ir.conditions:
        pred_iri = _prop_iri(base_iri, c.predicate)
        # empty actor (from annotated gateway) → use predicate IRI as self-referential arg1
        var1 = _prop_iri(base_iri, c.predicate) if not c.actor else _var_iri(base_iri, c.actor)
        body_atoms.append(_swrl_bool_atom(predicate_iri=pred_iri, var_iri=var1, value=c.value))

    # ── Head: actions ────────────────────────────────────────────────
    head_atoms: List[str] = []
    for a in ir.actions:
        var1       = _var_iri(base_iri, a.actor) if a.actor else _prop_iri(base_iri, "unknown")
        pred_local = _deontic_predicate_for_action(a.name)
        if pred_local == "task":
            pred_local = task_predicate
        pred_iri = _prop_iri(base_iri, pred_local)
        head_atoms.append(_swrl_task_atom(task_predicate_iri=pred_iri, var_iri=var1, task_string=a.name))

    # ── Head: RelationAtoms ──────────────────────────────────────────
    for rel in ir.relations:
        head_atoms.append(_swrl_object_atom(
            predicate_iri = _prop_iri(base_iri, rel.predicate),
            subject_iri   = _prop_iri(base_iri, rel.subject),
            object_iri    = _prop_iri(base_iri, rel.object),
        ))

    # ── Head: DataAtoms ──────────────────────────────────────────────
    for dat in ir.data_atoms:
        if not dat.value:
            continue
        head_atoms.append(_swrl_data_atom(
            predicate_iri = _prop_iri(base_iri, dat.predicate),
            subject_iri   = _prop_iri(base_iri, dat.subject),
            value         = dat.value,
            datatype      = dat.datatype,
        ))

    body_list = _atom_list_xml(body_atoms, indent=6)
    head_list = _atom_list_xml(head_atoms, indent=6)

    return (
        f'<swrl:Imp rdf:about="{escape(base_iri)}#{escape(ir.rid)}">\n'
        f"  <swrl:body>\n{body_list}\n  </swrl:body>\n"
        f"  <swrl:head>\n{head_list}\n  </swrl:head>\n"
        f"</swrl:Imp>"
    )


def _collect_vars_and_predicates(
    rules: Iterable[RuleIR], task_predicate: str
) -> Tuple[Set[str], Set[str], Set[str]]:
    actors:     Set[str] = set()
    data_preds: Set[str] = set()
    obj_preds:  Set[str] = set()

    for r in rules:
        for c in r.conditions:
            if c.actor:                                      # ← skip empty actor
                actors.add(c.actor)
            data_preds.add(c.predicate)
        for a in r.actions:
            if a.actor:                                      # ← skip empty actor
                actors.add(a.actor)
            data_preds.add(_deontic_predicate_for_action(a.name))
        for rel in r.relations:
            obj_preds.add(rel.predicate)
        for dat in r.data_atoms:
            data_preds.add(dat.predicate)

    data_preds.add(task_predicate)
    return actors, data_preds, obj_preds


def export_rules_to_owl(
    rules: List[RuleIR],
    *,
    out_file: str,
    base_iri: str = "http://example.org/bpmn2rules",
    task_predicate: str = "task",
) -> None:
    actors, data_preds, obj_preds = _collect_vars_and_predicates(rules, task_predicate)

    data_props_xml = "\n".join(
        f'  <owl:DatatypeProperty rdf:about="{escape(_prop_iri(base_iri, p))}"/>'
        for p in sorted(data_preds)
    )
    obj_props_xml = "\n".join(
        f'  <owl:ObjectProperty rdf:about="{escape(_prop_iri(base_iri, p))}"/>'
        for p in sorted(obj_preds)
    )
    vars_xml = "\n".join(
        f'  <swrl:Variable rdf:about="{escape(_var_iri(base_iri, a))}"/>'
        for a in sorted(actors)
    )
    rules_xml = "\n\n".join(
        rule_ir_to_swrl_xml(r, base_iri=base_iri, task_predicate=task_predicate)
        for r in rules
    )

    owl = f"""<?xml version="1.0"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:owl="http://www.w3.org/2002/07/owl#"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
  xmlns:swrl="http://www.w3.org/2003/11/swrl#"
  xmlns:swrlb="http://www.w3.org/2003/11/swrlb#"
  xml:base="{escape(base_iri)}">

  <owl:Ontology rdf:about="{escape(base_iri)}"/>

  <!-- Datatype Properties -->
{data_props_xml}

  <!-- Object Properties -->
{obj_props_xml}

  <!-- Variables -->
{vars_xml}

  <!-- SWRL Rules -->
{_indent(rules_xml, 2)}

</rdf:RDF>
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(owl)