from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "test" / "run_swrl_cases.py"
SWRL_PATH = ROOT / "regulations" / "eu-ai-act" / "eu-ai-act.swrl.owl"


def _load_runner_module():
    spec = importlib.util.spec_from_file_location("run_swrl_cases", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parser_detects_duplicate_rule_ids():
    module = _load_runner_module()
    ruleset = module.parse_swrl_rules(SWRL_PATH)
    duplicate_names = {module._short(iri) for iri in ruleset.duplicate_rule_iris}
    assert duplicate_names == {"r1", "r2", "r3", "r4"}


def test_high_risk_biometric_not_tested_case():
    module = _load_runner_module()
    ruleset = module.parse_swrl_rules(SWRL_PATH)
    outcome = module.evaluate_case(
        ruleset,
        case_id="high_risk_biometric_not_tested",
        facts={
            "Is_the_AI_system_used_for_biometric_purposes": True,
            "Is_the_AI_system_tested_in_reallife_before_entering_into_the_market": False,
        },
    )
    norm_names = {module._short(iri) for iri in outcome.norms}
    assert norm_names == {"OBL_Respect_high_risk_obligations"}


def test_high_risk_biometric_tested_case():
    module = _load_runner_module()
    ruleset = module.parse_swrl_rules(SWRL_PATH)
    outcome = module.evaluate_case(
        ruleset,
        case_id="high_risk_biometric_tested",
        facts={
            "Is_the_AI_system_used_for_biometric_purposes": True,
            "Is_the_AI_system_tested_in_reallife_before_entering_into_the_market": True,
        },
    )
    norm_names = {module._short(iri) for iri in outcome.norms}
    assert norm_names == {
        "OBL_ADD_testing_obligations",
        "OBL_Respect_high_risk_obligations",
    }
