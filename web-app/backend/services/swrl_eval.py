from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable


RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
OWL_NS = "http://www.w3.org/2002/07/owl#"
SWRL_NS = "http://www.w3.org/2003/11/swrl#"
XSD_BOOL = "http://www.w3.org/2001/XMLSchema#boolean"
NORMA_ACTIVATES_NORM = "https://w3id.org/def/norma-o#activatesNorm"
RDF_NIL = f"{RDF_NS}nil"

NS = {
    "rdf": RDF_NS,
    "owl": OWL_NS,
    "swrl": SWRL_NS,
}


def _tag(local: str, ns: str) -> str:
    return f"{{{ns}}}{local}"


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


@dataclass(frozen=True)
class BodyBooleanAtom:
    predicate_iri: str
    subject_iri: str
    value: bool


@dataclass(frozen=True)
class HeadActivationAtom:
    trigger_event_iri: str
    norm_iri: str


@dataclass(frozen=True)
class ParsedRule:
    iri: str
    body: tuple[BodyBooleanAtom, ...]
    head: tuple[HeadActivationAtom, ...]


@dataclass(frozen=True)
class ParsedRuleset:
    rules_iri: str
    imports_iri: str | None
    rules: tuple[ParsedRule, ...]
    duplicate_rule_iris: tuple[str, ...]


@dataclass(frozen=True)
class SwrlEvaluationOutcome:
    matched_rule_iris: tuple[str, ...]
    trigger_events: tuple[str, ...]
    norms: tuple[str, ...]


def _parse_bool_literal(atom: ET.Element) -> bool:
    arg2 = atom.find("swrl:argument2", NS)
    if arg2 is None:
        raise ValueError("Boolean body atom is missing swrl:argument2")
    datatype = arg2.attrib.get(_tag("datatype", RDF_NS))
    if datatype != XSD_BOOL:
        raise ValueError(
            f"Unsupported body datatype {datatype!r}; expected {XSD_BOOL!r}"
        )
    text = (arg2.text or "").strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Unsupported boolean literal value: {text!r}")


def _resource_attr(element: ET.Element, attr_local: str = "resource") -> str:
    value = element.attrib.get(_tag(attr_local, RDF_NS))
    if not value:
        raise ValueError(f"Expected rdf:{attr_local} attribute on {element.tag}")
    return value


def _iter_atom_list(node: ET.Element | None) -> list[ET.Element]:
    if node is None:
        return []

    if node.tag == _tag("Description", RDF_NS) and node.attrib.get(
        _tag("about", RDF_NS)
    ) == RDF_NIL:
        return []

    if node.tag != _tag("AtomList", SWRL_NS):
        raise ValueError(f"Expected swrl:AtomList, got {node.tag}")

    first_container = node.find("rdf:first", NS)
    if first_container is None or len(first_container) != 1:
        raise ValueError("Malformed swrl:AtomList rdf:first")
    first_atom = first_container[0]

    rest_container = node.find("rdf:rest", NS)
    if rest_container is None:
        raise ValueError("Malformed swrl:AtomList rdf:rest")

    rest_resource = rest_container.attrib.get(_tag("resource", RDF_NS))
    if rest_resource == RDF_NIL:
        return [first_atom]

    if len(rest_container) != 1:
        raise ValueError("Malformed swrl:AtomList nested rdf:rest")
    return [first_atom, *_iter_atom_list(rest_container[0])]


def _parse_body_atom(atom: ET.Element) -> BodyBooleanAtom:
    if atom.tag != _tag("DatavaluedPropertyAtom", SWRL_NS):
        raise ValueError(
            f"Unsupported SWRL body atom {atom.tag}; "
            "only swrl:DatavaluedPropertyAtom with xsd:boolean is supported"
        )

    predicate = atom.find("swrl:propertyPredicate", NS)
    arg1 = atom.find("swrl:argument1", NS)
    if predicate is None or arg1 is None:
        raise ValueError("Malformed swrl:DatavaluedPropertyAtom in rule body")

    return BodyBooleanAtom(
        predicate_iri=_resource_attr(predicate),
        subject_iri=_resource_attr(arg1),
        value=_parse_bool_literal(atom),
    )


def _parse_head_atom(atom: ET.Element) -> HeadActivationAtom:
    if atom.tag != _tag("IndividualPropertyAtom", SWRL_NS):
        raise ValueError(
            f"Unsupported SWRL head atom {atom.tag}; "
            "only swrl:IndividualPropertyAtom is supported"
        )

    predicate = atom.find("swrl:propertyPredicate", NS)
    arg1 = atom.find("swrl:argument1", NS)
    arg2 = atom.find("swrl:argument2", NS)
    if predicate is None or arg1 is None or arg2 is None:
        raise ValueError("Malformed swrl:IndividualPropertyAtom in rule head")

    predicate_iri = _resource_attr(predicate)
    if predicate_iri != NORMA_ACTIVATES_NORM:
        raise ValueError(
            f"Unsupported SWRL head predicate {predicate_iri!r}; "
            f"expected {NORMA_ACTIVATES_NORM!r}"
        )

    return HeadActivationAtom(
        trigger_event_iri=_resource_attr(arg1),
        norm_iri=_resource_attr(arg2),
    )


def parse_swrl_rules_xml(xml_text: str) -> ParsedRuleset:
    root = ET.fromstring(xml_text)

    ontology = root.find("owl:Ontology", NS)
    if ontology is None:
        raise ValueError("No owl:Ontology found in SWRL RDF/XML")

    rules_iri = ontology.attrib.get(_tag("about", RDF_NS)) or root.attrib.get("base")
    if not rules_iri:
        raise ValueError("Could not determine rules ontology IRI from SWRL RDF/XML")

    import_node = ontology.find("owl:imports", NS)
    imports_iri = _resource_attr(import_node) if import_node is not None else None

    parsed_rules: list[ParsedRule] = []
    rule_iris: list[str] = []

    for rule_node in root.findall("swrl:Imp", NS):
        rule_iri = rule_node.attrib.get(_tag("about", RDF_NS))
        if not rule_iri:
            raise ValueError("Encountered swrl:Imp without rdf:about")

        body_container = rule_node.find("swrl:body", NS)
        head_container = rule_node.find("swrl:head", NS)
        if body_container is None or head_container is None:
            raise ValueError(f"Rule {rule_iri} is missing swrl:body or swrl:head")
        if len(body_container) != 1 or len(head_container) != 1:
            raise ValueError(f"Rule {rule_iri} has malformed body/head atom lists")

        body_atoms = tuple(_parse_body_atom(atom) for atom in _iter_atom_list(body_container[0]))
        head_atoms = tuple(_parse_head_atom(atom) for atom in _iter_atom_list(head_container[0]))
        subjects = {atom.subject_iri for atom in body_atoms}
        if len(subjects) > 1:
            raise ValueError(
                f"Rule {rule_iri} uses multiple body subjects {sorted(subjects)}; "
                "this evaluator only supports one scenario subject variable per rule"
            )

        parsed_rules.append(ParsedRule(iri=rule_iri, body=body_atoms, head=head_atoms))
        rule_iris.append(rule_iri)

    duplicates = sorted({rule_iri for rule_iri in rule_iris if rule_iris.count(rule_iri) > 1})
    return ParsedRuleset(
        rules_iri=rules_iri,
        imports_iri=imports_iri,
        rules=tuple(parsed_rules),
        duplicate_rule_iris=tuple(duplicates),
    )


def _normalize_fact_key(key: str, *, rules_iri: str) -> str:
    if key.startswith("http://") or key.startswith("https://"):
        return key
    return f"{rules_iri}#{key}"


def evaluate_swrl_rules(
    ruleset: ParsedRuleset,
    facts: dict[str, bool],
) -> SwrlEvaluationOutcome:
    normalized_facts = {
        _normalize_fact_key(key, rules_iri=ruleset.rules_iri): bool(value)
        for key, value in facts.items()
    }

    matched_rule_iris: list[str] = []
    trigger_events: list[str] = []
    norms: list[str] = []

    for rule in ruleset.rules:
        if all(normalized_facts.get(atom.predicate_iri) == atom.value for atom in rule.body):
            matched_rule_iris.append(rule.iri)
            trigger_events.extend(atom.trigger_event_iri for atom in rule.head)
            norms.extend(atom.norm_iri for atom in rule.head)

    return SwrlEvaluationOutcome(
        matched_rule_iris=tuple(_unique_preserve_order(matched_rule_iris)),
        trigger_events=tuple(_unique_preserve_order(trigger_events)),
        norms=tuple(_unique_preserve_order(norms)),
    )

