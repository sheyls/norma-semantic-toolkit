from src.transformations.rule_ir import RuleIR, Action
from utils import to_symbol
import re

def _norm_prefix_from_action(a: Action) -> str:
    """
    Determine the deontic operator from Action.name.

    Supported formats:
      1) Canon format: "OBL|..." , "PER|..." , "PRO|..." / "PRH|..."
      2) Key-value format: "dtype=obligation;..." etc.

    Returns one of: "O", "P", "F"
      O = Obligation
      P = Permission
      F = Prohibition (Forbidden)
    """
    name = (a.name or "").strip()

    # 1) Canon pipe format: TYPE|...
    if "|" in name:
        head = name.split("|", 1)[0].strip().upper()
        if head in {"OBL", "OBLIGATION"}:
            return "O"
        if head in {"PER", "PERMISSION"}:
            return "P"
        if head in {"PRH", "PRO", "PROHIBITION"}:
            return "F"

    # 2) key=value format: dtype=obligation;...
    m = re.search(r"(?:^|[;,\s])dtype\s*=\s*([a-zA-Z_]+)", name, flags=re.IGNORECASE)
    if m:
        dt = m.group(1).strip().lower()
        if dt == "obligation":
            return "O"
        if dt == "permission":
            return "P"
        if dt in {"prohibition", "forbidden"}:
            return "F"

    # Default (backward compatible): obligation
    return "O"


def rule_ir_to_ddl(ir: RuleIR) -> str:
    # Antecedent
    if ir.conditions:
        ant = ", ".join(
            f"{to_symbol(c.actor + ' ' + c.predicate)}"
            if c.value
            else f"not {to_symbol(c.actor + ' ' + c.predicate)}"
            for c in ir.conditions
        )
    else:
        ant = "true"

    # Head
    if ir.actions:
        head = " & ".join(
            f"{_norm_prefix_from_action(a)}({to_symbol(a.actor + ' ' + a.name)})"
            for a in ir.actions
        )
    else:
        head = "O(none)"

    return f"{ir.rid}: {ant} => {head}."
