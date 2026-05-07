"""
kg_normalizer.py
================
Normalization layer for the NORMA knowledge graph pipeline.

Detects and resolves inconsistent entity labels across BPMN annotation
values before ABox generation. Covers:
  - Regulation names  (compliance_regulation)
  - Agent labels      (compliance_agent)
  - Legal objects     (compliance_object)

Normalization strategy
----------------------
1. Canonical form: lowercase, collapse whitespace, remove punctuation
2. Exact canonical match  → silently merge under the most frequent label
3. Fuzzy near-match       → warn + offer resolution (configurable threshold)
4. No match               → keep as separate entities, no action

Output
------
- Normalized records (labels replaced by canonical winners)
- NormalizationReport with all decisions and warnings
- Optionally: a JSON override map the user can edit and re-apply
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Configuration
# =============================================================================

FUZZY_THRESHOLD = 0.82   # similarity ratio above which two labels are flagged
                          # as potential duplicates (0.0–1.0)

KNOWN_ALIASES: Dict[str, str] = {
    # Common regulation name variants → canonical form
    # Extend this dict as needed.
    "ia act":         "EU AI Act",
    "ai act":         "EU AI Act",
    "eu ai act":      "EU AI Act",
    "aiact":          "EU AI Act",
    "gdpr":           "GDPR",
    "general data protection regulation": "GDPR",
    "dsa":            "DSA",
    "digital services act": "DSA",
    "dma":            "DMA",
    "digital markets act":  "DMA",
    "nis2":           "NIS 2",
    "nis 2":          "NIS 2",
    "network and information security directive": "NIS 2",
}


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class NormalizationDecision:
    field:      str          # "regulation" | "agent" | "object"
    raw_labels: List[str]    # all original values found
    winner:     str          # chosen canonical label
    reason:     str          # "exact_canonical" | "alias" | "fuzzy" | "manual" | "frequency"
    confidence: float        # 1.0 = certain, <1.0 = fuzzy


@dataclass
class NormalizationWarning:
    field:   str
    labels:  List[str]
    message: str
    suggestion: Optional[str] = None


@dataclass
class NormalizationReport:
    decisions: List[NormalizationDecision] = field(default_factory=list)
    warnings:  List[NormalizationWarning]  = field(default_factory=list)

    def print(self, file=sys.stdout) -> None:
        print("\n╔══ NORMA Normalization Report ══════════════════════════════════╗", file=file)

        if self.decisions:
            print("║  Decisions                                                     ║", file=file)
            for d in self.decisions:
                flag = "✓" if d.confidence == 1.0 else f"~{d.confidence:.0%}"
                raws = " | ".join(f'"{r}"' for r in d.raw_labels)
                print(f"║  [{flag}] {d.field}: {raws}", file=file)
                print(f"║       → \"{d.winner}\"  ({d.reason})", file=file)

        if self.warnings:
            print("║  Warnings                                                      ║", file=file)
            for w in self.warnings:
                labels = " | ".join(f'"{l}"' for l in w.labels)
                print(f"║  ⚠  {w.field}: {labels}", file=file)
                print(f"║     {w.message}", file=file)
                if w.suggestion:
                    print(f"║     Suggestion: {w.suggestion}", file=file)

        if not self.decisions and not self.warnings:
            print("║  All entity labels are consistent — no action needed.          ║", file=file)

        print("╚════════════════════════════════════════════════════════════════╝\n", file=file)

    def has_issues(self) -> bool:
        return bool(self.warnings)


# =============================================================================
# Core normalization logic
# =============================================================================

def _canonical(label: str) -> str:
    """Produce a canonical comparison key from a label."""
    s = label.lower().strip()
    s = re.sub(r"[_\-\.\,\;\:\/\\?!\(\)]", " ", s)  # punctuation → space (incl. ?)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _singularize(s: str) -> str:
    """Naive singularization of a canonical label for plural detection."""
    if s.endswith("ies"):
        return s[:-3] + "y"
    if s.endswith("ses") or s.endswith("xes") or s.endswith("zes") or s.endswith("ches") or s.endswith("shes"):
        return s[:-2]
    if s.endswith("s") and not s.endswith("ss"):
        return s[:-1]
    return s


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _canonical(a), _canonical(b)).ratio()


def _pick_winner(labels: List[str], first_seen: Dict[str, int]) -> Tuple[str, str]:
    """
    Given a list of labels known to be equivalent, pick the canonical winner.
    Strategy: prefer known alias → then first created / first seen.
    Returns (winner, reason).
    """
    # Check known alias table
    for label in labels:
        canonical_key = _canonical(label)
        if canonical_key in KNOWN_ALIASES:
            return KNOWN_ALIASES[canonical_key], "alias"

    by_order = sorted(labels, key=lambda l: first_seen.get(l, sys.maxsize))
    return by_order[0], "first_seen"


def _normalize_field(
    records:   List[dict],
    field_key: str,
    field_name: str,
    report:    NormalizationReport,
    override:  Dict[str, str],
    threshold: float = FUZZY_THRESHOLD,
) -> Dict[str, str]:
    """
    Normalize all values of a given field across records.
    Returns a mapping: raw_label → canonical_winner.
    """
    # Collect all non-empty values and their frequencies
    counts: Counter = Counter()
    first_seen: Dict[str, int] = {}
    for r in records:
        val = r.get(field_key, "").strip()
        if val:
            if val not in first_seen:
                first_seen[val] = len(first_seen)
            counts[val] += 1

    all_labels = list(counts.keys())
    if not all_labels:
        return {}

    # Apply manual overrides first
    mapping: Dict[str, str] = {}
    for label in all_labels:
        if label in override:
            mapping[label] = override[label]

    remaining = [l for l in all_labels if l not in mapping]

    # Group by canonical form (exact canonical match)
    canonical_groups: Dict[str, List[str]] = defaultdict(list)
    for label in remaining:
        ckey = _canonical(label)
        # Also check alias table
        if ckey in KNOWN_ALIASES:
            ckey = _canonical(KNOWN_ALIASES[ckey])
        canonical_groups[ckey].append(label)

    # For each canonical group, pick a winner
    for ckey, group in canonical_groups.items():
        winner, reason = _pick_winner(group, first_seen)

        if len(group) > 1:
            report.decisions.append(NormalizationDecision(
                field      = field_name,
                raw_labels = group,
                winner     = winner,
                reason     = reason,
                confidence = 1.0,
            ))

        for label in group:
            mapping[label] = winner

    # Plural/singular merge: auto-consolidate winners that differ only by a plural suffix.
    # Groups winners by their singularized canonical form; the shorter (singular) label wins.
    current_winners = list({v for v in mapping.values()})
    singular_groups: Dict[str, List[str]] = defaultdict(list)
    for w in current_winners:
        singular_groups[_singularize(_canonical(w))].append(w)

    for _sing_key, group in singular_groups.items():
        if len(group) < 2:
            continue
        # Prefer the label whose canonical form is already singular (i.e. unchanged by _singularize)
        already_singular = [w for w in group if _singularize(_canonical(w)) == _canonical(w)]
        winner = already_singular[0] if already_singular else sorted(group, key=lambda w: len(_canonical(w)))[0]
        losers = [w for w in group if w != winner]
        report.decisions.append(NormalizationDecision(
            field      = field_name,
            raw_labels = group,
            winner     = winner,
            reason     = "plural_variant",
            confidence = 1.0,
        ))
        for raw, mapped in list(mapping.items()):
            if mapped in losers:
                mapping[raw] = winner

    # Fuzzy merge: auto-consolidate remaining winners with high similarity.
    # Union-find over fuzzy-similar pairs so transitive chains collapse correctly.
    winners = list({v for v in mapping.values()})
    parent: Dict[str, str] = {w: w for w in winners}

    def _find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(winners)):
        for j in range(i + 1, len(winners)):
            if _similarity(winners[i], winners[j]) >= threshold:
                ri, rj = _find(winners[i]), _find(winners[j])
                if ri != rj:
                    # Keep the label that appears first (lower first_seen index)
                    if first_seen.get(ri, 0) <= first_seen.get(rj, 0):
                        parent[rj] = ri
                    else:
                        parent[ri] = rj

    fuzzy_groups: Dict[str, List[str]] = defaultdict(list)
    for w in winners:
        fuzzy_groups[_find(w)].append(w)

    for root, group in fuzzy_groups.items():
        if len(group) < 2:
            continue
        winner, reason = _pick_winner(group, first_seen)
        confidence = round(max(_similarity(winner, l) for l in group if l != winner), 2)
        report.decisions.append(NormalizationDecision(
            field      = field_name,
            raw_labels = group,
            winner     = winner,
            reason     = f"fuzzy ({reason})",
            confidence = confidence,
        ))
        report.warnings.append(NormalizationWarning(
            field      = field_name,
            labels     = group,
            message    = f"Labels merged automatically by similarity ({confidence:.0%}) — verify this is correct.",
            suggestion = f"If they should stay distinct, add a '_confirmed_separate' entry in the override file.",
        ))
        losers = [w for w in group if w != winner]
        for raw, mapped in list(mapping.items()):
            if mapped in losers:
                mapping[raw] = winner

    return mapping


def _canonical_norm_signature(record: dict) -> Tuple[str, ...]:
    return (
        _canonical(record.get("deontic_type", "")),
        _canonical(record.get("regulation", "")),
        _canonical(record.get("article", "")),
        _canonical(record.get("paragraph", "")),
        _canonical(record.get("agent", "")),
        _canonical(record.get("action", "")),
        _canonical(record.get("object", "")),
        _canonical(record.get("trigger_condition", "")),
        _canonical(record.get("norm_statement", "")),
        _canonical(record.get("fact_statement", "")),
    )


def canonical_norm_signature_from_props(props: dict) -> Tuple[str, ...]:
    return _canonical_norm_signature(
        {
            "deontic_type": props.get("compliance_deonticType", ""),
            "regulation": props.get("compliance_regulation", ""),
            "article": props.get("compliance_article", ""),
            "paragraph": props.get("compliance_paragraph", ""),
            "agent": props.get("compliance_agent", ""),
            "action": props.get("compliance_action", ""),
            "object": props.get("compliance_object", ""),
            "trigger_condition": props.get("compliance_triggerCondition", "") or props.get("compliance_condition", ""),
            "norm_statement": props.get("compliance_normStatement", ""),
            "fact_statement": props.get("compliance_factStatement", ""),
        }
    )


def _normalize_norm_instances(
    records: List[dict],
    report: NormalizationReport,
    override: Dict[str, str],
) -> Dict[str, str]:
    """
    Reuse the first created norm instance for semantically identical norms.
    Returns a mapping deontic_id -> canonical deontic_id.
    """
    mapping: Dict[str, str] = {}
    first_norm_for_signature: Dict[Tuple[str, ...], dict] = {}

    for record in records:
        if record.get("element_type") != "task":
            continue
        deontic_id = record.get("deontic_id", "").strip()
        if not deontic_id:
            continue

        if deontic_id in override:
            mapping[deontic_id] = override[deontic_id]
            continue

        signature = _canonical_norm_signature(record)
        if not any(signature):
            mapping.setdefault(deontic_id, deontic_id)
            continue

        first = first_norm_for_signature.get(signature)
        if first is None:
            first_norm_for_signature[signature] = record
            mapping.setdefault(deontic_id, deontic_id)
            continue

        winner = first.get("deontic_id", "").strip() or deontic_id
        mapping[deontic_id] = winner
        if deontic_id != winner:
            report.decisions.append(
                NormalizationDecision(
                    field="deontic_id",
                    raw_labels=[winner, deontic_id],
                    winner=winner,
                    reason="norm_signature",
                    confidence=1.0,
                )
            )

    return mapping


# =============================================================================
# Public API
# =============================================================================

def normalize(
    records:       List[dict],
    override_file: Optional[str] = None,
    threshold:     float = FUZZY_THRESHOLD,
) -> Tuple[List[dict], NormalizationReport]:
    """
    Normalize entity labels across a list of JSON intermediate records.

    Parameters
    ----------
    records       : output of kg_builder.to_json()
    override_file : optional path to a JSON file with manual overrides:
                    {"regulation": {"IA act": "EU AI Act"}, "agent": {}, "object": {}}
    threshold     : fuzzy similarity threshold (0.0–1.0)

    Returns
    -------
    normalized_records : records with labels replaced by canonical winners
    report             : NormalizationReport with all decisions and warnings
    """
    # Load overrides
    override: Dict[str, Dict[str, str]] = {
        "regulation": {}, "agent": {}, "object": {}, "action": {},
        "deontic_id": {}, "condition_statement": {},
    }
    confirmed_separate: List[List[str]] = []
    if override_file and Path(override_file).exists():
        with open(override_file) as f:
            loaded = json.load(f)
        for key in override:
            override[key].update(loaded.get(key, {}))
        confirmed_separate = loaded.get("_confirmed_separate", [])

    report = NormalizationReport()

    # Build normalization maps — all fields that mint distinct KG individuals
    reg_map    = _normalize_field(records, "regulation",         "regulation",         report, override.get("regulation", {}),         threshold)
    ag_map     = _normalize_field(records, "agent",              "agent",              report, override.get("agent", {}),              threshold)
    ob_map     = _normalize_field(records, "object",             "object",             report, override.get("object", {}),             threshold)
    action_map = _normalize_field(records, "action",             "action",             report, override.get("action", {}),             threshold)
    did_map    = _normalize_field(records, "deontic_id",         "deontic_id",         report, override.get("deontic_id", {}),         threshold)
    cond_map   = _normalize_field(records, "condition_statement","condition_statement", report, override.get("condition_statement", {}), threshold)

    # Apply maps to records
    normalized = []
    for r in records:
        nr = dict(r)
        if nr.get("regulation")         in reg_map:    nr["regulation"]         = reg_map[nr["regulation"]]
        if nr.get("agent")              in ag_map:     nr["agent"]              = ag_map[nr["agent"]]
        if nr.get("object")             in ob_map:     nr["object"]             = ob_map[nr["object"]]
        if nr.get("action")             in action_map: nr["action"]             = action_map[nr["action"]]
        if nr.get("deontic_id")         in did_map:    nr["deontic_id"]         = did_map[nr["deontic_id"]]
        if nr.get("condition_statement") in cond_map:  nr["condition_statement"] = cond_map[nr["condition_statement"]]
        normalized.append(nr)

    # Reconcile semantically identical norm instances after field normalization.
    norm_did_map = _normalize_norm_instances(normalized, report, override.get("deontic_id", {}))
    for nr in normalized:
        if nr.get("deontic_id") in norm_did_map:
            nr["deontic_id"] = norm_did_map[nr["deontic_id"]]

    # Suppress warnings for pairs the user has confirmed are intentionally different
    if confirmed_separate:
        sep_sets = [frozenset(p) for p in confirmed_separate]
        report.warnings = [
            w for w in report.warnings
            if frozenset(w.labels) not in sep_sets
        ]

    return normalized, report


def save_override_template(
    records:   List[dict],
    out_file:  str,
) -> None:
    """
    Save a JSON override template pre-populated with all unique values
    found in records. The user can edit the values to force specific
    canonical forms, then pass the file to normalize().
    """
    regs  = sorted({r.get("regulation","")         for r in records if r.get("regulation")})
    ags   = sorted({r.get("agent","")              for r in records if r.get("agent")})
    obs   = sorted({r.get("object","")             for r in records if r.get("object")})
    acts  = sorted({r.get("action","")             for r in records if r.get("action")})
    dids  = sorted({r.get("deontic_id","")         for r in records if r.get("deontic_id")})
    conds = sorted({r.get("condition_statement","") for r in records if r.get("condition_statement")})

    template = {
        "_instructions": (
            "Map each raw label (key) to its canonical form (value). "
            "Leave value empty or equal to key to keep as-is."
        ),
        "regulation":         {r: r for r in regs},
        "agent":              {a: a for a in ags},
        "object":             {o: o for o in obs},
        "action":             {a: a for a in acts},
        "deontic_id":         {d: d for d in dids},
        "condition_statement": {c: c for c in conds},
    }

    Path(out_file).write_text(json.dumps(template, indent=2, ensure_ascii=False))
    print(f"[norma] Override template written: {out_file}")


# =============================================================================
# CLI (standalone usage)
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Normalize entity labels in a NORMA JSON intermediate file."
    )
    parser.add_argument("json_file",   help="Input JSON intermediate (from kg_builder.py)")
    parser.add_argument("--override",  help="JSON override file", default=None)
    parser.add_argument("--threshold", type=float, default=FUZZY_THRESHOLD,
                        help=f"Fuzzy similarity threshold (default: {FUZZY_THRESHOLD})")
    parser.add_argument("--template",  help="Save override template to this file", default=None)
    parser.add_argument("--out",       help="Write normalized JSON to this file", default=None)
    args = parser.parse_args()

    with open(args.json_file) as f:
        records = json.load(f)

    if args.template:
        save_override_template(records, args.template)

    normalized, report = normalize(
        records,
        override_file=args.override,
        threshold=args.threshold,
    )

    report.print()

    if args.out:
        Path(args.out).write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"[norma] Normalized JSON written: {args.out}")
