from __future__ import annotations

from typing import List, Tuple
from xml.sax.saxutils import escape
import re

from src.transformations.rule_ir import RuleIR, RelationAtom, DataAtom


def _to_xml_id(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9_\-\.]", "_", s)
    return s or "unnamed"


def _indent(s: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line.strip() else line for line in s.splitlines())


def _parse_superiority_line(line: str) -> Tuple[str, str] | None:
    m = re.match(r"\s*([A-Za-z0-9_]+)\s*>\s*([A-Za-z0-9_]+)\s*\.\s*$", line)
    if not m:
        return None
    return m.group(1), m.group(2)


def _deontic_rel(a_name: str) -> str:
    """Map Action.name pipe prefix to LegalRuleML relation name."""
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
    return "task"


def _rule_atom(rel: str, var: str, data_lex: str, data_type: str) -> str:
    var_block = f"  <ruleml:Var>{escape(var)}</ruleml:Var>\n" if var else ""
    return (
        "<ruleml:Atom>\n"
        f"  <ruleml:Rel>{escape(rel)}</ruleml:Rel>\n"
        f"{var_block}"
        f"  <ruleml:Data xsi:type=\"{escape(data_type)}\">{escape(data_lex)}</ruleml:Data>\n"
        "</ruleml:Atom>"
    )


def _relation_atom(rel: str, subject: str, obj: str) -> str:
    """Object property atom: rel(subject, object)"""
    return (
        "<ruleml:Atom>\n"
        f"  <ruleml:Rel>{escape(rel)}</ruleml:Rel>\n"
        f"  <ruleml:Ind>{escape(subject)}</ruleml:Ind>\n"
        f"  <ruleml:Ind>{escape(obj)}</ruleml:Ind>\n"
        "</ruleml:Atom>"
    )


def _data_atom(rel: str, subject: str, value: str, datatype: str) -> str:
    """Data property atom: rel(subject, literal)"""
    xsd = datatype if datatype.startswith("http") else datatype.replace("xsd:", "xs:")
    return (
        "<ruleml:Atom>\n"
        f"  <ruleml:Rel>{escape(rel)}</ruleml:Rel>\n"
        f"  <ruleml:Ind>{escape(subject)}</ruleml:Ind>\n"
        f"  <ruleml:Data xsi:type=\"{escape(xsd)}\">{escape(value)}</ruleml:Data>\n"
        "</ruleml:Atom>"
    )


def _and_atoms(atoms: List[str]) -> str:
    if not atoms:
        return ""
    if len(atoms) == 1:
        return atoms[0]
    inner = "\n".join(_indent(a, 4) for a in atoms)
    return f"<ruleml:And>\n{inner}\n</ruleml:And>"


def rule_ir_to_legalruleml_rule(ir: RuleIR) -> str:
    rule_key = _to_xml_id(ir.rid)

    # ── IF: conditions ───────────────────────────────────────────────
    if_atoms: List[str] = []
    for c in ir.conditions:
        if_atoms.append(_rule_atom(
            rel       = c.predicate,
            var       = c.actor,           # empty string handled by _rule_atom
            data_lex  = "true" if c.value else "false",
            data_type = "xs:boolean",
        ))

    if_block = _and_atoms(if_atoms) if if_atoms else ""

    # ── THEN: actions (deontic-aware rel) ───────────────────────────
    then_atoms: List[str] = []
    for a in ir.actions:
        then_atoms.append(_rule_atom(
            rel       = _deontic_rel(a.name),
            var       = a.actor,
            data_lex  = a.name,
            data_type = "xs:string",
        ))

    # ── THEN: RelationAtoms ──────────────────────────────────────────
    for rel in ir.relations:
        then_atoms.append(_relation_atom(rel.predicate, rel.subject, rel.object))

    # ── THEN: DataAtoms ─────────────────────────────────────────────
    for dat in ir.data_atoms:
        if not dat.value:
            continue
        then_atoms.append(_data_atom(dat.predicate, dat.subject, dat.value, dat.datatype))

    then_block = _and_atoms(then_atoms) if then_atoms else ""

    if_xml   = f"<ruleml:if>\n{_indent(if_block, 2)}\n</ruleml:if>"   if if_block   else ""
    then_xml = f"<ruleml:then>\n{_indent(then_block, 2)}\n</ruleml:then>" if then_block else ""

    return (
        f'<lrml:PrescriptiveStatement key="{escape(rule_key)}">\n'
        f'  <ruleml:Rule key="{escape(rule_key)}">\n'
        + (_indent(if_xml,   4) + "\n" if if_xml   else "")
        + (_indent(then_xml, 4) + "\n" if then_xml else "")
        + "  </ruleml:Rule>\n"
        + "</lrml:PrescriptiveStatement>"
    )


def export_rules_to_legalruleml(
    rules: List[RuleIR],
    superiority: List[str],
    *,
    out_file: str,
) -> None:
    prescriptive = "\n\n".join(rule_ir_to_legalruleml_rule(r) for r in rules)

    overrides_xml: List[str] = []
    for s in superiority:
        pair = _parse_superiority_line(s)
        if not pair:
            continue
        over, under = pair
        overrides_xml.append(
            f'<lrml:OverrideStatement>\n'
            f'  <lrml:Override over="#{escape(over)}" under="#{escape(under)}"/>\n'
            f'</lrml:OverrideStatement>'
        )

    overrides = "\n\n".join(overrides_xml)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<lrml:LegalRuleML\n'
        '  xmlns:lrml="http://docs.oasis-open.org/legalruleml/ns/v1.0/"\n'
        '  xmlns:ruleml="http://ruleml.org/spec"\n'
        '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n\n'
        '  <lrml:Statements>\n'
        + _indent(prescriptive, 4) + "\n\n"
        + (_indent(overrides, 4) + "\n" if overrides.strip() else "")
        + "  </lrml:Statements>\n\n"
        + "</lrml:LegalRuleML>\n"
    )

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(xml)