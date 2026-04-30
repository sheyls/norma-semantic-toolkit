from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web-app"))

from backend.sparql_presets import SPARQL_PRESETS


def test_sparql_presets_expose_competency_questions_and_queries():
    assert SPARQL_PRESETS

    ids = [preset["id"] for preset in SPARQL_PRESETS]
    assert len(ids) == len(set(ids))

    for preset in SPARQL_PRESETS:
        assert preset["label"].strip()
        assert preset["question"].strip().endswith("?")
        assert preset["description"].strip()
        assert preset["vocabulary"]
        assert preset["query"].strip().startswith("PREFIX norma:")
