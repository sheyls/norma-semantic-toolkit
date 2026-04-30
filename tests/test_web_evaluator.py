from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web-app"))

from backend.services.storage import (
    _evaluate_pack_via_rule_ir,
    _evaluate_pack_via_swrl,
    _coerce_answer_bool,
    evaluate_pack,
    load_regulation_packs,
    require_pack,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_FILE = ROOT / "test" / "eu_ai_act_cases.json"


def _load_cases() -> list[dict]:
    payload = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    return payload["cases"]


def _matched_norm_ids(payload: dict) -> set[str]:
    return {item["norm_id"] for item in payload["matched_rules"]}


def test_norm_determination_uses_swrl_for_high_risk_biometric_case():
    load_regulation_packs()

    result = evaluate_pack(
        "eu-ai-act",
        {
            "Is_the_AI_system_used_for_biometric_purposes": True,
            "Is_the_AI_system_tested_in_reallife_before_entering_into_the_market": False,
        },
    )

    assert result["engine"] == "swrl"
    assert _matched_norm_ids(result) == {"OBL_Respect_high_risk_obligations"}


def test_norm_determination_supports_string_boolean_answers_with_swrl():
    load_regulation_packs()

    result = evaluate_pack(
        "eu-ai-act",
        {
            "Is_the_AI_system_used_for_biometric_purposes": "true",
            "Is_the_AI_system_tested_in_reallife_before_entering_into_the_market": "true",
        },
    )

    assert result["engine"] == "swrl"
    assert _matched_norm_ids(result) == {
        "OBL_Respect_high_risk_obligations",
        "OBL_ADD_testing_obligations",
    }


@pytest.mark.parametrize("case_spec", _load_cases(), ids=lambda case: case["id"])
def test_swrl_and_rule_ir_evaluators_match_for_reference_cases(case_spec: dict):
    load_regulation_packs()
    pack = require_pack("eu-ai-act")
    answers = {str(k): _coerce_answer_bool(v) for k, v in case_spec["facts"].items()}
    swrl_matched, _ = _evaluate_pack_via_swrl(pack, answers)
    rule_ir_matched = _evaluate_pack_via_rule_ir(pack, answers)

    assert {item["norm_id"] for item in swrl_matched} == {
        item["norm_id"] for item in rule_ir_matched
    }


@pytest.mark.parametrize("case_spec", _load_cases(), ids=lambda case: case["id"])
def test_swrI_norm_determination_matches_expected_reference_cases(case_spec: dict):
    load_regulation_packs()

    result = evaluate_pack("eu-ai-act", case_spec["facts"])

    assert result["engine"] == "swrl"
    assert _matched_norm_ids(result) == set(case_spec.get("expect_norms", []))
