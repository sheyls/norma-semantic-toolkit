"""
human_readable.py
=================
Renders RuleIR objects in the SWRL human-readable syntax:

    antecedent ⇒ consequent

where antecedent and consequent are conjunctions of atoms written with the
standard ?variable notation.  Follows the syntax defined in the SWRL
specification (Section 2.2).

Example output (single-line):
    r2: DoesTheAISystemGenerateSyntheticContent(?x, true) ⇒
        Obligation(:OBL_Mark_synthetic_content) ∧
        hasLegalAgent(:OBL_Mark_synthetic_content, :Agent_AI_provider) ∧
        hasLegalObject(:OBL_Mark_synthetic_content, :Object_audio_image_text_or_video_output) ∧
        fromArticle(:OBL_Mark_synthetic_content, "50")
"""

from __future__ import annotations

from typing import List
from norma_engine.rules.ir import RuleIR, Ref


# ---------------------------------------------------------------------------
# Reference formatting
# ---------------------------------------------------------------------------

def _ref(ref: Ref) -> str:
    """Format a Ref as a human-readable token."""
    if ref.kind == "var":
        return f"?{ref.name}"
    if ref.kind == "abox":
        return f":{ref.name}"
    if ref.kind == "tbox":
        return f"norma:{ref.name}"
    # "rules" — local predicate name used in rule body
    return ref.name


# ---------------------------------------------------------------------------
# Atom formatters
# ---------------------------------------------------------------------------

def _condition_atom(c) -> str:
    subj = _ref(c.subject)
    val  = "true" if c.value else "false"
    return f"{c.predicate.name}({subj}, {val})"


def _class_atom(ca) -> str:
    return f"{ca.class_ref.name}({_ref(ca.subject)})"


def _relation_atom(rel) -> str:
    return f"{rel.predicate.name}({_ref(rel.subject)}, {_ref(rel.object)})"


def _data_atom(dat) -> str:
    return f'{dat.predicate.name}({_ref(dat.subject)}, "{dat.value}")'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rule_ir_to_human_readable(
    ir: RuleIR,
    *,
    multiline: bool = True,
    compact: bool = False,
) -> str:
    """
    Render a RuleIR as a SWRL human-readable string.

    Parameters
    ----------
    ir : RuleIR
        The rule to render.
    multiline : bool
        If True, put each atom on its own indented line.
        If False, emit a single compact line.
    compact : bool
        If True, the head contains only ClassAtoms (deontic-type assertions).
        All relation and data atoms are omitted — they describe properties of
        the norm individual and are more clearly read from the ABox directly.
        Result example::
            syntheticContent(?x, true) ⇒ Obligation(:OBL_Mark_synthetic_content)
        If False (default), all head atoms are included (full SWRL).
    """
    body: List[str] = [_condition_atom(c) for c in ir.conditions]
    body_str = "⊤" if not body else (
        ("\n    ∧ " if multiline else " ∧ ").join(body)
    )

    if compact:
        # Head: only the deontic-type assertions — everything else is on the norm
        head = [_class_atom(ca) for ca in ir.class_atoms] or ["⊤"]
    else:
        head = []
        for ca in ir.class_atoms:
            head.append(_class_atom(ca))
        for rel in ir.relations:
            head.append(_relation_atom(rel))
        for dat in ir.data_atoms:
            head.append(_data_atom(dat))

    head_str = "⊤" if not head else (
        ("\n    ∧ " if multiline else " ∧ ").join(head)
    )

    if multiline:
        return f"{ir.rid}:\n  {body_str}\n  ⇒\n    {head_str}"
    return f"{ir.rid}: {body_str} ⇒ {head_str}"


def rules_to_human_readable(rules: List[RuleIR], *, multiline: bool = True) -> str:
    """Render a list of RuleIR objects separated by blank lines."""
    separator = "\n\n" if multiline else "\n"
    return separator.join(
        rule_ir_to_human_readable(r, multiline=multiline) for r in rules
    )
