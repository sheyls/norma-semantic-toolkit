from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Tuple


RefKind = Literal["var", "abox", "tbox", "rules"]


@dataclass(frozen=True)
class Ref:
    kind: RefKind
    name: str


@dataclass(frozen=True)
class Condition:
    """
    SWRL body condition, derived from gateway annotations.

    Example:
      rules:Generation_of_synthetic_content(?x, true)
    """
    predicate: Ref        # must usually be Ref("rules", ...)
    subject: Ref          # must usually be Ref("var", ...)
    value: bool
    condition_local: str = ""  # ABox LegalCondition local name (slug-based), e.g. "Condition_IsHighRisk"
    condition_label: str = ""  # Human-readable gateway condition text from BPMN


@dataclass(frozen=True)
class Action:
    """
    Optional summary literal. Auxiliary only.

    Example:
      norma:obligation(:Agent_AI_provider, "OBLIGATION|OBL_1|mark|generated_content")
    """
    subject: Ref     # usually Ref("abox", ...) or Ref("var", ...)
    name: str
    predicate: Ref | None = None
    datatype: str = "xsd:string"


@dataclass(frozen=True)
class ClassAtom:
    """
    SWRL head class-membership atom.

    Asserts the OWL class of the norm individual so that a SWRL reasoner
    can infer the deontic modality from the rule alone (without the ABox).

    Example:
      norma:Obligation(:OBL_1)
    """
    class_ref: Ref   # must be Ref("tbox", ...)
    subject: Ref     # must be Ref("abox", ...) or Ref("var", ...)


@dataclass(frozen=True)
class TriggerAtom:
    """
    SWRL head activation atom.

    Asserts norma:activatesNorm(triggerEvent, norm) so that a SWRL reasoner
    derives the activation link conditionally, keeping it non-redundant with
    the structural ABox (which declares TriggerEvent shells without activatesNorm).

    Example:
      norma:activatesNorm(:TriggerEvent_Condition_IsHighRisk_True_OBL_1, :OBL_1)
    """
    te_ref: Ref             # Ref("abox", "TriggerEvent_{condition_local}_{True|False}_{norm_local}")
    norm_ref: Ref           # Ref("abox", norm_local)
    condition_local: str    # ABox local name of the decisive atomic LegalCondition individual
    condition_label: str = ""  # Human-readable gateway condition text from BPMN
    outcome: bool = True       # branch outcome that activates the norm


@dataclass(frozen=True)
class RelationAtom:
    """
    SWRL head object-property atom.

    Example:
      norma:hasLegalAgent(:OBL_1, :Agent_AI_provider)
    """
    predicate: Ref   # usually Ref("tbox", ...)
    subject: Ref
    object: Ref


@dataclass(frozen=True)
class DataAtom:
    """
    SWRL head data-property atom.

    Example:
      norma:fromArticle(:OBL_1, "4")
    """
    predicate: Ref   # usually Ref("tbox", ...)
    subject: Ref
    value: str
    datatype: str = "xsd:string"


@dataclass(frozen=True)
class RuleIR:
    rid: str
    conditions: Tuple[Condition, ...]
    actions: Tuple[Action, ...] = ()
    relations: Tuple[RelationAtom, ...] = ()
    data_atoms: Tuple[DataAtom, ...] = ()
    class_atoms: Tuple[ClassAtom, ...] = ()    # rdf:type assertions — used by SHACL exporter
    trigger_atoms: Tuple[TriggerAtom, ...] = ()  # norma:activatesNorm assertions — used by SWRL exporter
    source: str = ""                             # source BPMN filename
