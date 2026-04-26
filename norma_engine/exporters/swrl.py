from __future__ import annotations

from typing import Iterable, List, Set, Tuple
from xml.sax.saxutils import escape

from norma_engine.rules.ir import RuleIR, Ref, TriggerAtom
from norma_engine.exporters.common import resolve_ref as _resolve_ref, xsd_iri as _xsd_iri

RDF_NIL = "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"
XSD_BOOL = "http://www.w3.org/2001/XMLSchema#boolean"

DEFAULT_TBOX_NS = "https://w3id.org/def/norma-o#"


def _indent(s: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line.strip() else line for line in s.splitlines())


def _swrl_bool_atom(*, predicate_iri: str, arg1_iri: str, value: bool) -> str:
    return (
        "<swrl:DatavaluedPropertyAtom>\n"
        f'  <swrl:propertyPredicate rdf:resource="{escape(predicate_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(arg1_iri)}"/>\n'
        f'  <swrl:argument2 rdf:datatype="{XSD_BOOL}">{"true" if value else "false"}</swrl:argument2>\n'
        "</swrl:DatavaluedPropertyAtom>"
    )


def _swrl_data_atom(*, predicate_iri: str, subject_iri: str, value: str, datatype: str) -> str:
    return (
        "<swrl:DatavaluedPropertyAtom>\n"
        f'  <swrl:propertyPredicate rdf:resource="{escape(predicate_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(subject_iri)}"/>\n'
        f'  <swrl:argument2 rdf:datatype="{escape(_xsd_iri(datatype))}">{escape(value)}</swrl:argument2>\n'
        "</swrl:DatavaluedPropertyAtom>"
    )


def _swrl_class_atom(*, class_iri: str, subject_iri: str) -> str:
    return (
        "<swrl:ClassAtom>\n"
        f'  <swrl:classPredicate rdf:resource="{escape(class_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(subject_iri)}"/>\n'
        "</swrl:ClassAtom>"
    )


def _swrl_object_atom(*, predicate_iri: str, subject_iri: str, object_iri: str) -> str:
    return (
        "<swrl:IndividualPropertyAtom>\n"
        f'  <swrl:propertyPredicate rdf:resource="{escape(predicate_iri)}"/>\n'
        f'  <swrl:argument1 rdf:resource="{escape(subject_iri)}"/>\n'
        f'  <swrl:argument2 rdf:resource="{escape(object_iri)}"/>\n'
        "</swrl:IndividualPropertyAtom>"
    )


def _atom_list_xml(atoms_xml: List[str], indent: int) -> str:
    pad = " " * indent
    if not atoms_xml:
        return f'{pad}<rdf:Description rdf:about="{RDF_NIL}"/>'

    first = atoms_xml[0]
    rest = atoms_xml[1:]

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


def _validate_condition_ref(ref: Ref, field: str) -> None:
    if field == "predicate" and ref.kind != "rules":
        raise ValueError(f"Condition predicate must be Ref(kind='rules', ...), got {ref}")
    if field == "subject" and ref.kind != "var":
        raise ValueError(f"Condition subject must be Ref(kind='var', ...), got {ref}")


def _validate_head_predicate(ref: Ref, atom_type: str) -> None:
    if ref.kind != "tbox":
        raise ValueError(f"{atom_type} predicate must be Ref(kind='tbox', ...), got {ref}")


def _validate_action_subject(ref: Ref) -> None:
    if ref.kind not in {"abox", "var"}:
        raise ValueError(
            f"Action subject must be Ref(kind='abox'|'var', ...), got {ref}"
        )


def rule_ir_to_swrl_xml(
    ir: RuleIR,
    *,
    rules_iri: str,
    abox_iri: str,
    tbox_ns: str = DEFAULT_TBOX_NS,
) -> str:
    if not ir.conditions:
        raise ValueError(
            f"Rule {ir.rid} has no body conditions. "
            "Unconditional norms are fully declared in the ABox and do not need a SWRL rule. "
            "Call export_rules_to_owl() which filters these out automatically."
        )
    if not ir.trigger_atoms:
        raise ValueError(
            f"Rule {ir.rid} has no trigger atoms — the gateway branch leads to no applicable norms. "
            "Call export_rules_to_owl() which filters these out automatically."
        )

    body_atoms: List[str] = []
    for c in ir.conditions:
        _validate_condition_ref(c.predicate, "predicate")
        _validate_condition_ref(c.subject, "subject")
        pred_iri = _resolve_ref(c.predicate, rules_iri=rules_iri, abox_iri=abox_iri, tbox_ns=tbox_ns)
        subj_iri = _resolve_ref(c.subject, rules_iri=rules_iri, abox_iri=abox_iri, tbox_ns=tbox_ns)
        body_atoms.append(
            _swrl_bool_atom(predicate_iri=pred_iri, arg1_iri=subj_iri, value=c.value)
        )

    head_atoms: List[str] = []

    # Head: norma:activatesNorm(TriggerEvent, Norm) — conditionally derived by SWRL,
    # keeping the head non-redundant with the ABox (which declares TriggerEvent shells
    # with hasOutcome but without activatesNorm).
    activates_norm_iri = f"{tbox_ns}activatesNorm"
    for ta in ir.trigger_atoms:
        if ta.te_ref.kind != "abox":
            raise ValueError(f"TriggerAtom te_ref must be Ref(kind='abox', ...), got {ta.te_ref}")
        if ta.norm_ref.kind != "abox":
            raise ValueError(f"TriggerAtom norm_ref must be Ref(kind='abox', ...), got {ta.norm_ref}")
        te_iri   = _resolve_ref(ta.te_ref,   rules_iri=rules_iri, abox_iri=abox_iri, tbox_ns=tbox_ns)
        norm_iri = _resolve_ref(ta.norm_ref, rules_iri=rules_iri, abox_iri=abox_iri, tbox_ns=tbox_ns)
        head_atoms.append(
            _swrl_object_atom(
                predicate_iri=activates_norm_iri,
                subject_iri=te_iri,
                object_iri=norm_iri,
            )
        )

    body_list = _atom_list_xml(body_atoms, indent=6)
    head_list = _atom_list_xml(head_atoms, indent=6)

    return (
        f'<swrl:Imp rdf:about="{escape(rules_iri)}#{escape(ir.rid)}">\n'
        f"  <swrl:body>\n{body_list}\n  </swrl:body>\n"
        f"  <swrl:head>\n{head_list}\n  </swrl:head>\n"
        f"</swrl:Imp>"
    )


def _collect_vars_and_predicates(
    rules: Iterable[RuleIR],
) -> Tuple[Set[str], Set[str]]:
    vars_: Set[str] = set()
    body_data_preds: Set[str] = set()

    for r in rules:
        for c in r.conditions:
            if c.subject.kind == "var":
                vars_.add(c.subject.name)
            if c.predicate.kind == "rules":
                body_data_preds.add(c.predicate.name)

    return vars_, body_data_preds


def export_rules_to_owl(
    rules: List[RuleIR],
    *,
    out_file: str,
    rules_iri: str = "https://w3id.org/norma-abox/eu-ai-act/rules",
    abox_iri: str = "https://w3id.org/norma-abox/eu-ai-act",
    tbox_ns: str = DEFAULT_TBOX_NS,
    imports_iri: str | None = None,
) -> None:
    # Unconditional rules (no gateway conditions) are fully declared in the ABox.
    # Rules with no trigger_atoms correspond to gateway branches that lead to no
    # applicable norms — both are vacuous as SWRL rules and are skipped.
    exportable = [r for r in rules if r.conditions and r.trigger_atoms]
    skipped = len(rules) - len(exportable)
    if skipped:
        print(
            f"[norma] SWRL export: skipped {skipped} rule(s) "
            "(unconditional or leading to no applicable norms — already in ABox)."
        )
    rules = exportable

    vars_, body_data_preds = _collect_vars_and_predicates(rules)

    data_props_xml = "\n".join(
        f'  <owl:DatatypeProperty rdf:about="{escape(f"{rules_iri}#{p}")}"/>'
        for p in sorted(body_data_preds)
    )

    vars_xml = "\n".join(
        f'  <swrl:Variable rdf:about="{escape(f"{rules_iri}#var_{v}")}"/>'
        for v in sorted(vars_)
    )

    rules_xml = "\n\n".join(
        rule_ir_to_swrl_xml(r, rules_iri=rules_iri, abox_iri=abox_iri, tbox_ns=tbox_ns)
        for r in rules
    )

    imports_target = imports_iri or abox_iri
    imports_xml = f'    <owl:imports rdf:resource="{escape(imports_target)}"/>\n'

    owl = f"""<?xml version="1.0"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:owl="http://www.w3.org/2002/07/owl#"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
  xmlns:swrl="http://www.w3.org/2003/11/swrl#"
  xmlns:swrlb="http://www.w3.org/2003/11/swrlb#"
  xml:base="{escape(rules_iri)}">

  <owl:Ontology rdf:about="{escape(rules_iri)}">
{imports_xml}  </owl:Ontology>

  <!-- Rules-local datatype properties used in SWRL bodies -->
{data_props_xml}

  <!-- SWRL Variables -->
{vars_xml}

  <!-- SWRL Rules -->
{_indent(rules_xml, 2)}

</rdf:RDF>
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(owl)