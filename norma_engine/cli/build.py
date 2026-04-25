#!/usr/bin/env python3
"""
norma_engine.cli.build
======================
NORMA pipeline orchestrator.

Given a regulation pack folder (or an organization folder), runs the
full pipeline:
  1. Parse all BPMN files
  2. Normalize entity labels
  3. Generate ABox Turtle (knowledge graph)
  4. Generate SWRL rules OWL file

Expected folder structure
-------------------------
regulations/
    eu-ai-act/
        bpmn/               ← *.bpmn files go here
        eu_ai_act.abox.ttl  ← generated
        eu_ai_act.swrl.owl  ← generated (if SWRL exporter available)

organizations/
    acme-corp/
        internal/
            bpmn/
            acme_internal.abox.ttl
            acme_internal.swrl.owl
        active_regulations.json

Usage
-----
# Build a regulation pack
python -m norma_engine.cli.build regulations/eu-ai-act/

# Build an organization's internal policies
python -m norma_engine.cli.build organizations/acme-corp/internal/

# Build with manual normalization override
python -m norma_engine.cli.build regulations/eu-ai-act/ --override overrides.json

# Generate normalization override template first
python -m norma_engine.cli.build regulations/eu-ai-act/ --template overrides.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Pipeline imports ──────────────────────────────────────────────────────────
try:
    from norma_engine.kg.builder import parse_bpmn_folder, to_json, to_turtle
    _KG_AVAILABLE = True
except ImportError:
    _KG_AVAILABLE = False
    print("[!] norma_engine.kg.builder not found — KG generation disabled.")

try:
    from norma_engine.kg.normalizer import normalize, save_override_template
    _NORMALIZER_AVAILABLE = True
except ImportError:
    _NORMALIZER_AVAILABLE = False

# Rule extraction pipeline (parsing → DFS → RuleIR)
try:
    from norma_engine.parsing.bpmn_parser import parse_bpmn_to_reduced_graph
    from norma_engine.rules.extractor import enumerate_paths_and_build_ir
    from norma_engine.exporters.swrl import export_rules_to_owl
    _RULES_AVAILABLE = True
except Exception as e:
    _RULES_AVAILABLE = False
    print(f"[!] rule extraction imports failed: {type(e).__name__}: {e}")

NORMA_ONT = "https://w3id.org/def/norma-o"
ABOX_BASE  = "https://w3id.org/norma-abox"


# =============================================================================
# Helpers
# =============================================================================

def _resolve_pack(folder: Path) -> tuple[Path, str]:
    """
    Given a pack folder, return (bpmn_dir, pack_name).
    Looks for a 'bpmn/' subfolder; if not found, uses the folder itself.
    """
    bpmn_dir = folder / "bpmn"
    if bpmn_dir.is_dir():
        return bpmn_dir, folder.name
    # Fallback: treat folder itself as bpmn dir
    return folder, folder.name


def _abox_iri(pack_name: str) -> str:
    slug = pack_name.lower().replace(" ", "-").replace("_", "-")
    return f"{ABOX_BASE}/{slug}"

def _apply_normalized_labels_to_task_props(
    task_props: dict[str, dict[str, str]],
    normalized_records: list[dict] | None,
) -> dict[str, dict[str, str]]:
    """
    Rewrite raw BPMN task/gateway props using normalized labels from KG build,
    keyed by bpmn_id.
    """
    if not normalized_records:
        return task_props

    by_id = {r.get("bpmn_id"): r for r in normalized_records if r.get("bpmn_id")}

    patched: dict[str, dict[str, str]] = {}

    for el_id, props in task_props.items():
        p = dict(props)
        rec = by_id.get(el_id)

        if rec:
            if "regulation" in rec and rec["regulation"]:
                p["compliance_regulation"] = rec["regulation"]
            if "agent" in rec and rec["agent"]:
                p["compliance_agent"] = rec["agent"]
            if "object" in rec and rec["object"]:
                p["compliance_object"] = rec["object"]

        patched[el_id] = p

    return patched

# =============================================================================
# Build steps
# =============================================================================

def build_kg(
    bpmn_dir:      Path,
    out_dir:       Path,
    pack_name:     str,
    normalize_labels: bool = True,
    override_file: str | None = None,
    threshold:     float = 0.82,
) -> list[dict] | None:
    """
    Step 1+2: Parse BPMNs → normalize → generate ABox Turtle.
    Returns the normalized records (for further processing).
    """
    if not _KG_AVAILABLE:
        print("[!] kg_builder not available — skipping KG build.")
        return None

    print(f"\n── KG Build: {pack_name} ──────────────────────────────────────────")
    print(f"   BPMN source: {bpmn_dir}")

    # Step 1: Parse
    elements, bpmn_files = parse_bpmn_folder(bpmn_dir)
    print(f"   Total: {len(elements)} elements from {len(bpmn_files)} file(s)")
    records = to_json(elements)

    # Step 2: Normalize
    if (normalize_labels or override_file) and _NORMALIZER_AVAILABLE:
        print(f"\n[norma] Normalizing entity labels ...")
        records, report = normalize(records, override_file=override_file, threshold=threshold)
        report.print()
        if report.has_issues():
            print(f"[norma] ⚠ Warnings above require attention.")
            print(f"         Run with --template {out_dir/pack_name}_overrides.json to inspect.")
    elif normalize_labels and not _NORMALIZER_AVAILABLE:
        print("[!] kg_normalizer not available — skipping normalization.")

    # Step 3: Write JSON intermediate
    json_path = out_dir / f"{pack_name}.json"
    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    print(f"[✓] JSON:  {json_path}")

    # Step 4: Write ABox Turtle
    abox_iri  = _abox_iri(pack_name)
    turtle    = to_turtle(records, str(bpmn_dir), abox_iri)
    ttl_path  = out_dir / f"{pack_name}.abox.ttl"
    ttl_path.write_text(turtle, encoding="utf-8")
    print(f"[✓] ABox:  {ttl_path}")

    return records


def build_rules(
    bpmn_dir: Path,
    out_dir: Path,
    pack_name: str,
    normalized_records: list[dict] | None = None,
) -> None:
    """
    Step 3: Run DFS rule extraction on every BPMN file in bpmn_dir and write:
      - <pack_name>.swrl.owl      (SWRL/OWL, imports the ABox)
    """
    if not _RULES_AVAILABLE:
        print("[!] norma.rules not available — skipping rule extraction.")
        return

    print(f"\n── Rule Extraction: {pack_name} ──────────────────────────────────────")

    all_rules:       list = []
    all_superiority: list = []

    for bpmn_file in sorted(bpmn_dir.glob("*.bpmn")):
        xml = bpmn_file.read_text(encoding="utf-8")
        nodes, edges, _, gw_index, task_props = parse_bpmn_to_reduced_graph(xml)
        task_props = _apply_normalized_labels_to_task_props(task_props, normalized_records)

        _, rules_ir, superiority = enumerate_paths_and_build_ir(
            nodes=nodes,
            edges=edges,
            gateway_outgoing_index=gw_index,
            task_props=task_props,
        )
        all_rules.extend(rules_ir)
        all_superiority.extend(superiority)
        print(f"   {bpmn_file.name}: {len(rules_ir)} rule(s)")

    if not all_rules:
        print("[!] No rules extracted — check that BPMN tasks carry deontic annotations.")
        return

    # SWRL — ontology IRI is <abox_iri>/rules; imports the ABox so it gets TBox too
    abox_iri  = _abox_iri(pack_name)
    swrl_iri  = f"{abox_iri}/rules"
    swrl_path = out_dir / f"{pack_name}.swrl.owl"
    export_rules_to_owl(
    all_rules,
    out_file=str(swrl_path),
    rules_iri=swrl_iri,
    abox_iri=abox_iri,
    imports_iri=abox_iri,
    )
    print(f"[✓] SWRL:        {swrl_path}")


# =============================================================================
# Organization: active_regulations.json
# =============================================================================

def build_organization(
    org_dir:       Path,
    reg_base_dir:  Path | None = None,
    normalize_labels: bool = True,
    override_file: str | None = None,
) -> None:
    """
    Build an organization's view:
      - Builds internal policies KG
      - Reports which regulation packs are active
    """
    active_file = org_dir / "active_regulations.json"
    if not active_file.exists():
        print(f"[!] No active_regulations.json found in {org_dir}")
        print(f"    Create one with format: {{\"regulations\": [\"eu-ai-act\", \"gdpr\"]}}")
    else:
        active = json.loads(active_file.read_text())
        regs   = active.get("regulations", [])
        print(f"\n── Organization: {org_dir.name} ──────────────────────────────────")
        print(f"   Active regulations: {', '.join(regs) if regs else 'none'}")
        if reg_base_dir:
            for reg in regs:
                reg_path = reg_base_dir / reg
                if reg_path.exists():
                    print(f"   ✓ {reg}: {reg_path}")
                else:
                    print(f"   ✗ {reg}: not found at {reg_path}")

    # Build internal policies if present
    internal_dir = org_dir / "internal"
    if internal_dir.is_dir():
        out_dir = internal_dir
        out_dir.mkdir(exist_ok=True)
        bpmn_dir, _ = _resolve_pack(internal_dir)
        if (bpmn_dir).glob("*.bpmn"):
            build_kg(bpmn_dir, out_dir, f"{org_dir.name}_internal",
                     normalize_labels=normalize_labels,
                     override_file=override_file)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="NORMA Build — orchestrates the full pipeline for a regulation pack or organization."
    )
    parser.add_argument(
        "folder",
        help="Regulation pack folder (e.g. regulations/eu-ai-act/) or organization folder"
    )
    parser.add_argument(
        "--no-normalize", action="store_true",
        help="Skip entity label normalization"
    )
    parser.add_argument(
        "--override", default=None,
        help="JSON normalization override file"
    )
    parser.add_argument(
        "--template", default=None,
        help="Save normalization override template to this file and exit"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.82,
        help="Fuzzy similarity threshold (default: 0.82)"
    )
    parser.add_argument(
        "--org", action="store_true",
        help="Treat folder as an organization directory"
    )
    parser.add_argument(
        "--reg-base", default=None,
        help="Base folder for regulations (used with --org to resolve active_regulations.json)"
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"[!] Folder not found: {folder}")
        sys.exit(1)

    normalize_labels = not args.no_normalize

    # ── Organization mode ────────────────────────────────────────────
    if args.org:
        reg_base = Path(args.reg_base) if args.reg_base else None
        build_organization(folder, reg_base_dir=reg_base,
                           normalize_labels=normalize_labels,
                           override_file=args.override)
        return

    # ── Regulation pack mode ─────────────────────────────────────────
    bpmn_dir, pack_name = _resolve_pack(folder)

    if not any(bpmn_dir.glob("*.bpmn")):
        print(f"[!] No .bpmn files found in {bpmn_dir}")
        sys.exit(1)

    out_dir = folder
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate override template and exit
    if args.template:
        if not _NORMALIZER_AVAILABLE or not _KG_AVAILABLE:
            print("[!] kg_normalizer or kg_builder not available.")
            sys.exit(1)
        elements, _ = parse_bpmn_folder(bpmn_dir)
        records = to_json(elements)
        save_override_template(records, args.template)
        print(f"[norma] Template written: {args.template}")
        print(f"[norma] Edit then re-run with --override {args.template}")
        return

    # Full build
    print(f"\n╔══ NORMA Build: {pack_name} {'═' * max(0, 50 - len(pack_name))}╗")
    records = build_kg(
        bpmn_dir, out_dir, pack_name,
        normalize_labels=normalize_labels,
        override_file=args.override,
        threshold=args.threshold,
    )

    build_rules(bpmn_dir, out_dir, pack_name, normalized_records=records)

    print(f"\n╚══ Done: {pack_name} {'═' * max(0, 53 - len(pack_name))}╝\n")


if __name__ == "__main__":
    main()