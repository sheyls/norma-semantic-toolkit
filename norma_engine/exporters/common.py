from __future__ import annotations

from norma_engine.rules.ir import Ref

XSD_NS = "http://www.w3.org/2001/XMLSchema#"


def resolve_ref(ref: Ref, *, rules_iri: str, abox_iri: str, tbox_ns: str) -> str:
    if ref.kind == "rules":
        return f"{rules_iri}#{ref.name}"
    if ref.kind == "abox":
        return f"{abox_iri}#{ref.name}"
    if ref.kind == "tbox":
        return f"{tbox_ns}{ref.name}"
    if ref.kind == "var":
        return f"{rules_iri}#var_{ref.name}"
    raise ValueError(f"Unsupported Ref.kind: {ref.kind}")


def xsd_iri(datatype: str) -> str:
    if datatype.startswith(("http://", "https://")):
        return datatype
    return f"{XSD_NS}{datatype.replace('xsd:', '')}"
