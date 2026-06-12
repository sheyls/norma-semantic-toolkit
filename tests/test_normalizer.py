"""
Layer 2b — Entity label normalizer tests.

Covers alias resolution, exact canonical merging, fuzzy near-match
warning generation, manual override application, and threshold behaviour.
"""

import pytest
from norma_engine.kg.normalizer import normalize, save_override_template
import json, os, subprocess, sys, tempfile


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


def _make_action_records(*action_labels):
    """Build minimal task records with the given action labels."""
    return [
        {
            "element_type": "task",
            "bpmn_id": f"t{i}",
            "regulation": "EU AI Act",
            "agent": "AI provider",
            "object": "AI system",
            "action": label,
        }
        for i, label in enumerate(action_labels)
    ]


def _make_action_records_with_deontic(*pairs):
    """Build minimal task records from (action_label, deontic_type) pairs."""
    return [
        {
            "element_type": "task",
            "bpmn_id": f"t{i}",
            "regulation": "EU AI Act",
            "agent": "AI provider",
            "object": "AI system",
            "action": label,
            "deontic_type": dtype,
        }
        for i, (label, dtype) in enumerate(pairs)
    ]


class TestDeonticTypeAwareMerge:
    def test_plural_variant_not_merged_across_deontic_types(self):
        """An obligation's "submit the report" must stay distinct from a
        prohibition's "submit the reports" — they are different norms,
        even though they differ only by a plural suffix."""
        records = _make_action_records_with_deontic(
            ("submit the report", "obligation"),
            ("submit the reports", "prohibition"),
        )
        recs, _ = normalize(records, threshold=0.82)
        actions = {r["action"] for r in recs}
        assert actions == {"submit the report", "submit the reports"}

    def test_plural_variant_still_merged_within_same_deontic_type(self):
        records = _make_action_records_with_deontic(
            ("submit the report", "obligation"),
            ("submit the reports", "obligation"),
        )
        recs, _ = normalize(records, threshold=0.82)
        actions = {r["action"] for r in recs}
        assert len(actions) == 1


class TestDeterminism:
    def test_fuzzy_merge_deterministic_across_hash_seeds(self):
        """Same input must produce the same normalization regardless of
        PYTHONHASHSEED.

        Reproduces the EU AI Act corpus case: "comply with marking
        obligations" vs "comply high-risk obligations" have an asymmetric
        SequenceMatcher.ratio() that straddles the fuzzy threshold in one
        direction. The previous set-based dedup of `winners` made the pair
        comparison order (and thus the merge outcome) depend on Python's
        per-process string hash randomization.
        """
        records = _make_action_records(
            "comply with marking obligations",
            "comply high-risk obligations",
        )
        script = (
            "import json\n"
            "from norma_engine.kg.normalizer import normalize\n"
            f"records = {records!r}\n"
            "recs, _ = normalize(records, threshold=0.82)\n"
            "print(json.dumps([r['action'] for r in recs]))\n"
        )
        outputs = set()
        for seed in ("0", "1", "2", "3", "42"):
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            outputs.add(result.stdout.strip())
        assert len(outputs) == 1, f"normalization differs across hash seeds: {outputs}"


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
