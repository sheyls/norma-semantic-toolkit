import re

def to_symbol(text: str) -> str:
    t = (text or "").replace("\n", " ").strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", "_", t)
    return t if t else "unnamed"