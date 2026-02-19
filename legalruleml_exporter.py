# legalruleml_exporter.py
from __future__ import annotations

from typing import List, Tuple
from xml.sax.saxutils import escape
import re

from rule_ir import RuleIR

# -----------------------------
# Helpers
# -----------------------------

def _to_xml_id(s: str) -> str:
    """
    Turn 'r1' or 'rule_1' into a safe XML-ish id fragment.
    """
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9_\-\.]", "_", s)
    return s or "unnamed"

def _rule_atom(rel: str, var: str, data_lex: str, data_type: str) -> str:
    """
    <ruleml:Atom>
      <ruleml:Rel>rel</ruleml:Rel>
      <ruleml:Var>x</ruleml:Var>
      <ruleml:Data xsi:type="...">...</ruleml:Data>
    </ruleml:Atom>
    """
    return f"""
<ruleml:Atom>
  <ruleml:Rel>{escape(rel)}</ruleml:Rel>
  <ruleml:Var>{escape(var)}</ruleml:Var>
  <ruleml:Data xsi:type="{escape(data_type)}">{escape(data_lex)}</ruleml:Data>
</ruleml:Atom>
""".strip()

def _and_atoms(atoms: List[str]) -> str:
    """
    If more than one atom: wrap in <ruleml:And> ... </ruleml:And>
    If one atom: return atom directly
    If empty: return empty (caller decides)
    """
    if not atoms:
        return ""
    if len(atoms) == 1:
        return atoms[0]
    inner = "\n".join(_indent(a, 4) for a in atoms)
    return f"""
<ruleml:And>
{inner}
</ruleml:And>
""".strip()

def _indent(s: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line.strip() else line for line in s.splitlines())

def _parse_superiority_line(line: str) -> Tuple[str, str] | None:
    """
    Parse "r1 > r2." -> ("r1","r2")
    """
    m = re.match(r"\s*([A-Za-z0-9_]+)\s*>\s*([A-Za-z0-9_]+)\s*\.\s*$", line)
    if not m:
        return None
    return m.group(1), m.group(2)

# -----------------------------
# Public API
# -----------------------------

def rule_ir_to_legalruleml_rule(ir: RuleIR) -> str:
    """
    Map RuleIR to a LegalRuleML PrescriptiveStatement + RuleML rule.
    - Conditions: Rel = predicate, Var = actor, Data = true/false (xsd:boolean)
    - Actions: Rel = "task", Var = actor, Data = action_name (xsd:string)

    NOTE: This keeps a generic 'task' predicate (same as your SWRL approach).
    """
    rule_key = _to_xml_id(ir.rid)

    # IF: conditions
    if_atoms: List[str] = []
    for c in ir.conditions:
        # Here we represent the boolean value explicitly as Data(true/false)
        if_atoms.append(_rule_atom(
            rel=c.predicate,
            var=c.actor,
            data_lex="true" if c.value else "false",
            data_type="xs:boolean",
        ))

    if_block = _and_atoms(if_atoms) if if_atoms else ""

    # THEN: actions
    then_atoms: List[str] = []
    for a in ir.actions:
        then_atoms.append(_rule_atom(
            rel="task",
            var=a.actor,
            data_lex=a.name,
            data_type="xs:string",
        ))

    then_block = _and_atoms(then_atoms) if then_atoms else ""

    # Build RuleML Rule
    # If you need a "true" antecedent, you can omit <ruleml:if> entirely, or insert a tautology.
    if_xml = f"<ruleml:if>\n{_indent(if_block, 2)}\n</ruleml:if>" if if_block else ""
    then_xml = f"<ruleml:then>\n{_indent(then_block, 2)}\n</ruleml:then>" if then_block else ""

    return f"""
<lrml:PrescriptiveStatement key="{escape(rule_key)}">
  <ruleml:Rule key="{escape(rule_key)}">
{_indent(if_xml, 4) if if_xml else ""}
{_indent(then_xml, 4) if then_xml else ""}
  </ruleml:Rule>
</lrml:PrescriptiveStatement>
""".strip()

def export_rules_to_legalruleml(
    rules: List[RuleIR],
    superiority: List[str],
    *,
    out_file: str,
) -> None:
    """
    Write a LegalRuleML XML file with:
      - PrescriptiveStatement per rule
      - OverrideStatement per superiority relation

    Mapping:
      "r1 > r2."  =>  <lrml:OverrideStatement><lrml:Override over="#r1" under="#r2"/></lrml:OverrideStatement>

    In LegalRuleML examples, 'over' is the rule that takes precedence. :contentReference[oaicite:2]{index=2}
    """
    # 1) rules
    prescriptive = "\n\n".join(rule_ir_to_legalruleml_rule(r) for r in rules)

    # 2) overrides
    overrides_xml: List[str] = []
    for s in superiority:
        pair = _parse_superiority_line(s)
        if not pair:
            continue
        over, under = pair
        overrides_xml.append(f"""
<lrml:OverrideStatement>
  <lrml:Override over="#{escape(over)}" under="#{escape(under)}"/>
</lrml:OverrideStatement>
""".strip())

    overrides = "\n\n".join(overrides_xml)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<lrml:LegalRuleML
  xmlns:lrml="http://docs.oasis-open.org/legalruleml/ns/v1.0/"
  xmlns:ruleml="http://ruleml.org/spec"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

  <lrml:Statements>
{_indent(prescriptive, 4)}

{_indent(overrides, 4) if overrides.strip() else ""}
  </lrml:Statements>

</lrml:LegalRuleML>
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(xml)
