from src.transformations.rule_ir import RuleIR, Action
from utils import to_symbol
import re


def _norm_prefix_from_action(a: Action) -> str:
    """
    Returns DDL operator: "O" (obligation), "F" (prohibition), "P" (permission),
    "RS" (recommendation), "RSN" (recommendation_not), "IS" (fact)
    """
    name = (a.name or "").strip()

    if "|" in name:
        head = name.split("|", 1)[0].strip().upper()
        mapping = {
            "OBL":                "O",
            "OBLIGATION":         "O",
            "PRH":                "F",
            "PRO":                "F",
            "PROHIBITION":        "F",
            "PER":                "P",
            "PERMISSION":         "P",
            "REC":                "RS",
            "RECOMMENDATION":     "RS",
            "REC_NOT":            "RSN",
            "RECOMMENDATION_NOT": "RSN",
            "FACT":               "IS",
            "FCT":                "IS",
        }
        if head in mapping:
            return mapping[head]

    m = re.search(r"(?:^|[;,\s])dtype\s*=\s*([a-zA-Z_]+)", name, flags=re.IGNORECASE)
    if m:
        dt = m.group(1).strip().lower()
        mapping = {
            "obligation":         "O",
            "permission":         "P",
            "prohibition":        "F",
            "recommendation":     "RS",
            "recommendation_not": "RSN",
            "fact":               "IS",
        }
        if dt in mapping:
            return mapping[dt]

    return "O"


def _action_to_ddl_atom(a: Action) -> str:
    """
    Builds a readable DDL atom from Action canon format:
      DTYPE|node_id|action|obj|reg|art|par

    Result:  OPERATOR(agent, action, object)
    Example: O(AI_owner, marking_as_synthetic, AI_content)
    """
    prefix = _norm_prefix_from_action(a)
    parts  = a.name.split("|")

    if len(parts) >= 4:
        agent  = to_symbol(a.actor)
        action = parts[2] if parts[2] not in ("NO_ACTION", "") else None
        obj    = parts[3] if parts[3] not in ("NO_OBJECT", "") else None

        if action and obj:
            return f"{prefix}({agent}, {action}, {obj})"
        if action:
            return f"{prefix}({agent}, {action})"

    # fallback: node_id only
    node_id = parts[1] if len(parts) >= 2 and parts[1] else to_symbol(a.actor + "_" + a.name)
    return f"{prefix}({to_symbol(a.actor)}, {to_symbol(node_id)})"


def rule_ir_to_ddl(ir: RuleIR) -> str:
    # Antecedent
    if ir.conditions:
        ant = ", ".join(
            to_symbol(c.predicate) if not c.actor
            else (
                to_symbol(c.predicate)
                if c.value
                else f"not {to_symbol(c.predicate)}"
            )
            if not c.actor
            else (
                to_symbol(c.actor + "_" + c.predicate)
                if c.value
                else f"not {to_symbol(c.actor + '_' + c.predicate)}"
            )
            for c in ir.conditions
        )
    else:
        ant = "true"

    # Head
    head = " & ".join(_action_to_ddl_atom(a) for a in ir.actions) if ir.actions else "O(none)"

    return f"{ir.rid}: {ant} => {head}."