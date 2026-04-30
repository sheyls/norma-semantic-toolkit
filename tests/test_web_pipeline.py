"""
Layer 5 — Web-app pipeline tests.

Verifies that backend aggregation for the Norm Review view deduplicates
repeated gateway annotations that represent the same logical condition.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web-app"))

from backend.services.pipeline import all_norms


def test_norm_review_deduplicates_repeated_gateway_conditions():
    pack = {
        "rules_ir": [],
        "task_props": {
            "Gateway_A": {
                "compliance_elementType": "exclusiveGateway",
                "gw_conditionStatement": "Have safeguards on nature of the system and consequence of its use been taken into consideration?",
                "gw_trueBranch": "Yes",
                "gw_falseBranch": "No",
                "_bpmn_source": "diagram Cybersecurity exemption.bpmn",
                "_bpmn_name": "Have safeguards on nature of the system and consequence of its use been taken into consideration?",
            },
            "Gateway_B": {
                "compliance_elementType": "exclusiveGateway",
                "gw_conditionStatement": "Have safeguards on nature of the system and consequence of its use been taken into consideration?",
                "gw_trueBranch": "Yes",
                "gw_falseBranch": "No",
                "_bpmn_source": "diagram Cybersecurity exemption.bpmn",
                "_bpmn_name": "Have safeguards on nature of the system and consequence of its use been taken into consideration?",
            },
            "Task_OBL": {
                "compliance_elementType": "task",
                "compliance_deonticType": "obligation",
                "compliance_deonticId": "OBL_Respect_prescribed_obligations",
                "compliance_action": "comply with obligations",
                "_bpmn_source": "diagram Cybersecurity exemption.bpmn",
                "_bpmn_name": "Respect prescribed obligations",
            },
        },
    }

    norms = all_norms(pack)["norms"]

    gateway_entries = [item for item in norms if not item["deontic_type"]]
    norm_entries = [item for item in norms if item["deontic_type"]]

    assert len(gateway_entries) == 1
    assert gateway_entries[0]["gw_condition_statement"] == (
        "Have safeguards on nature of the system and consequence of its use been taken into consideration?"
    )
    assert len(norm_entries) == 1
    assert norm_entries[0]["norm_id"] == "OBL_Respect_prescribed_obligations"


def test_norm_review_keeps_entries_from_different_files_with_same_bpmn_id():
    pack = {
        "rules_ir": [],
        "task_props": {
            "file-a.bpmn::Gateway_0xwlzaj": {
                "compliance_elementType": "exclusiveGateway",
                "gw_conditionStatement": "Is the AI system used for biometric purposes?",
                "gw_trueBranch": "Yes",
                "gw_falseBranch": "No",
                "_bpmn_source": "file-a.bpmn",
                "_bpmn_name": "Is the AI system used for biometric purposes?",
            },
            "file-b.bpmn::Gateway_0xwlzaj": {
                "compliance_elementType": "exclusiveGateway",
                "gw_conditionStatement": "Has it been certified under the EU cybersecurity scheme?",
                "gw_trueBranch": "Yes",
                "gw_falseBranch": "No",
                "_bpmn_source": "file-b.bpmn",
                "_bpmn_name": "Has it been certified under the EU cybersecurity scheme?",
            },
        },
    }

    norms = all_norms(pack)["norms"]
    gateway_conditions = {item["gw_condition_statement"] for item in norms}

    assert gateway_conditions == {
        "Is the AI system used for biometric purposes?",
        "Has it been certified under the EU cybersecurity scheme?",
    }
