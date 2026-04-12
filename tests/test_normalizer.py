"""
Layer 2b — Entity label normalizer tests.

Covers alias resolution, exact canonical merging, fuzzy near-match
warning generation, manual override application, and threshold behaviour.
"""

import pytest
from norma.kg.normalizer import normalize, save_override_template
import json, tempfile, os


def _make_records(*regulation_labels):
    """Build minimal task records with the given regulation labels."""
    return [
        {
            "element_type": "task",
            "bpmn_id": f"t{i}",
            "regulation": label,
            "agent": "AI owner",
            "object": "AI system",
        }
        for i, label in enumerate(regulation_labels)
    ]


class TestAliasResolution:
    def test_ia_act_resolves_to_eu_ai_act(self):
        recs, report = normalize(_make_records("ia act"), threshold=0.82)
        assert recs[0]["regulation"] == "EU AI Act"

    def test_ai_act_resolves_to_eu_ai_act(self):
        recs, report = normalize(_make_records("ai act"), threshold=0.82)
        assert recs[0]["regulation"] == "EU AI Act"

    def test_gdpr_variant_resolves(self):
        recs, report = normalize(
            _make_records("General Data Protection Regulation"), threshold=0.82
        )
        assert recs[0]["regulation"] == "GDPR"


class TestExactCanonicalMerge:
    def test_case_variants_merged(self):
        recs, report = normalize(
            _make_records("EU AI Act", "eu ai act", "EU ai act"), threshold=0.82
        )
        values = {r["regulation"] for r in recs}
        assert len(values) == 1

    def test_decision_recorded_for_merge(self):
        _, report = normalize(
            _make_records("EU AI Act", "eu ai act"), threshold=0.82
        )
        # At least one decision should be recorded (canonical or alias merge)
        assert len(report.decisions) >= 1


class TestFuzzyWarnings:
    def test_near_match_generates_warning(self):
        # "EU AI Act" vs "EU IA Act" — high similarity but not canonical-equal
        _, report = normalize(
            _make_records("EU AI Act", "EU IA Act"), threshold=0.70
        )
        assert report.has_issues()
        labels_in_warnings = [
            l for w in report.warnings for l in w.labels
        ]
        assert any("EU AI Act" in l or "EU IA Act" in l for l in labels_in_warnings)

    def test_high_threshold_suppresses_warning(self):
        # At threshold=1.0 only identical strings match → no fuzzy warning
        _, report = normalize(
            _make_records("EU AI Act", "EU IA Act"), threshold=1.0
        )
        assert not report.has_issues()


class TestManualOverride:
    def test_override_applied(self):
        override = {"regulation": {"IA act": "EU AI Act"}, "agent": {}, "object": {}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(override, f)
            tmp = f.name
        try:
            recs, _ = normalize(_make_records("IA act"), override_file=tmp)
        finally:
            os.unlink(tmp)
        assert recs[0]["regulation"] == "EU AI Act"


class TestOverrideTemplate:
    def test_template_contains_all_unique_values(self):
        recs = _make_records("EU AI Act", "GDPR", "EU AI Act")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            tmp = f.name
        try:
            save_override_template(recs, tmp)
            with open(tmp) as f:
                tmpl = json.load(f)
        finally:
            os.unlink(tmp)
        assert "EU AI Act" in tmpl["regulation"]
        assert "GDPR"      in tmpl["regulation"]
        # Duplicate "EU AI Act" must appear only once as a key
        assert len(tmpl["regulation"]) == 2
