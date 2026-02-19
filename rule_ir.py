# rule_ir.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class Condition:
    actor: str
    predicate: str
    value: bool

@dataclass(frozen=True)
class Action:
    actor: str
    name: str

@dataclass(frozen=True)
class RelationAtom:
    """
    Object property atom:
      predicate(subject, object)
    Example:
      providesAISystem(AIprovider, AIsystem)
    """
    predicate: str
    subject: str
    object: str

@dataclass(frozen=True)
class DataAtom:
    """
    Data property atom:
      predicate(subject, literal)
    Example:
      hasDeonticId(obl1, "OBL_001")
    """
    predicate: str
    subject: str
    value: str
    datatype: str = "xsd:string"  # allow xsd:boolean, xsd:decimal, xsd:anyURI, etc.

@dataclass(frozen=True)
class RuleIR:
    rid: str
    conditions: Tuple[Condition, ...]
    actions: Tuple[Action, ...]
    relations: Tuple[RelationAtom, ...] = ()
    data_atoms: Tuple[DataAtom, ...] = ()
