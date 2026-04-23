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
    predicate: Ref   # must usually be Ref("rules", ...)
    subject: Ref     # must usually be Ref("var", ...)
    value: bool


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
    class_atoms: Tuple[ClassAtom, ...] = ()  # norm rdf:type assertions for SWRL head
    source: str = ""                          # source BPMN filename
