import re


def to_symbol(text: str) -> str:
    t = (text or "").replace("\n", " ").strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", "_", t)
    return t if t else "unnamed"


def slug(text: str) -> str:
    """Convert an arbitrary label to a valid IRI local name (used for ABox individual names)."""
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_]", "_", (text or "").strip())).strip("_")