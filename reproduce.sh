#!/usr/bin/env bash
# reproduce.sh — regenerates every artifact for the EU AI Act knowledge graph
# from the source BPMN corpus, runs the test suite, and verifies the pipeline
# is deterministic.
#
# Usage:
#   pip install -e .          # install the engine once (requires Python >=3.10)
#   bash reproduce.sh         # run from the repo root
#
# Exit codes:
#   0 — all artifacts regenerated and determinism verified
#   1 — build failed or determinism check failed

set -euo pipefail

PACK="regulations/eu-ai-act"
PACK_NAME=$(basename "$PACK")    # "eu-ai-act" — keeps the ABox IRI identical across runs
BPMN_COUNT=$(ls "$PACK/bpmn/"*.bpmn 2>/dev/null | wc -l | tr -d ' ')

# Step 1 rebuilds the artifacts in place, so snapshot the committed copies now —
# comparing against files the script itself has just rewritten proves nothing.
SNAPSHOT=$(mktemp -d)
for EXT in abox.ttl swrl.owl json; do
    cp "$PACK/$PACK_NAME.$EXT" "$SNAPSHOT/" 2>/dev/null || true
done

echo "════════════════════════════════════════════════════════════"
echo "  NORMA Reproducibility Script"
echo "  Corpus: $PACK/bpmn/  ($BPMN_COUNT BPMN diagrams)"
echo "════════════════════════════════════════════════════════════"

# ── Locate Python (prefer the one that already has norma_engine installed) ────
PYTHON=""
for candidate in python3 python python3.10 python3.11 python3.12 python3.13; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import norma_engine" 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "[!] Could not find a Python interpreter with norma_engine installed."
    echo "    Run: pip install -e .  (requires Python >=3.10)"
    exit 1
fi

NORMA_BUILD="$PYTHON -m norma_engine.cli.build"
echo "    Python: $($PYTHON --version)  ($($PYTHON -c 'import sys; print(sys.executable)'))"
echo ""

# ── Step 1: Regenerate ABox + SWRL from the BPMN corpus ─────────────────────
echo "[ 1/4 ]  Building knowledge graph (ABox + SWRL) ..."
$NORMA_BUILD "$PACK/"

# ── Step 2: Run the engine test suite ────────────────────────────────────────
# Web-app tests (test_web_app_storage, test_web_evaluator, test_web_pipeline,
# test_sparql_presets) require the FastAPI stack — run them separately after
# installing web-app/backend/requirements.txt.
echo ""
echo "[ 2/4 ]  Running engine test suite ..."
$PYTHON -m pytest tests/test_kg.py tests/test_rules.py tests/test_normalizer.py \
    tests/test_parsing.py tests/test_exporters.py tests/test_swrl_case_runner.py -q

# ── Steps 3 & 4: Determinism check — build twice on isolated temp copies ─────
echo ""
echo "[ 3/4 ]  Determinism check — first pass ..."
WORK1=$(mktemp -d)
WORK2=$(mktemp -d)
TMP1="$WORK1/$PACK_NAME"
TMP2="$WORK2/$PACK_NAME"
mkdir -p "$TMP1" "$TMP2"

cp -r "$PACK/bpmn"          "$TMP1/"
cp    "$PACK/entities.json"  "$TMP1/" 2>/dev/null || true
cp -r "$PACK/bpmn"          "$TMP2/"
cp    "$PACK/entities.json"  "$TMP2/" 2>/dev/null || true

# Both passes use the same options as step 1 — a check run under different
# build options would not certify the artifacts that are actually shipped.
$NORMA_BUILD "$TMP1/" > /dev/null 2>&1

echo "[ 4/4 ]  Determinism check — second pass ..."
$NORMA_BUILD "$TMP2/" > /dev/null 2>&1

echo ""
echo "── Comparing outputs ────────────────────────────────────────"
PASS=true
for EXT in abox.ttl swrl.owl json; do
    # Address the generated artifact by name: a *.$EXT glob would match the
    # entities.json input that was copied into the work directory.
    FNAME="$PACK_NAME.$EXT"
    F1="$TMP1/$FNAME"
    F2="$TMP2/$FNAME"
    COMMITTED="$SNAPSHOT/$FNAME"
    if [[ ! -f "$F1" || ! -f "$F2" ]]; then
        echo "  [FAIL] $FNAME  not produced by the build"
        PASS=false
        continue
    fi
    H1=$(shasum -a 256 "$F1" | awk '{print $1}')
    H2=$(shasum -a 256 "$F2" | awk '{print $1}')
    if [[ "$H1" != "$H2" ]]; then
        echo "  [FAIL] $FNAME  the two runs differ"
        echo "         run 1: $H1"
        echo "         run 2: $H2"
        PASS=false
        continue
    fi
    if [[ ! -f "$COMMITTED" ]]; then
        echo "  [FAIL] $FNAME  no committed artifact to compare against"
        PASS=false
        continue
    fi
    HC=$(shasum -a 256 "$COMMITTED" | awk '{print $1}')
    if [[ "$H1" != "$HC" ]]; then
        echo "  [FAIL] $FNAME  rebuild differs from the committed artifact"
        echo "         rebuilt:   $H1"
        echo "         committed: $HC"
        PASS=false
        continue
    fi
    echo "  [OK]   $FNAME  sha256=$H1"
done

rm -rf "$WORK1" "$WORK2" "$SNAPSHOT"

echo ""
if [[ "$PASS" == "true" ]]; then
    echo "════════════════════════════════════════════════════════════"
    echo "  Reproducibility: PASSED — pipeline is deterministic and the"
    echo "  committed artifacts match a clean rebuild."
    echo "  Verified artifacts:"
    echo "    $PACK/$PACK_NAME.abox.ttl"
    echo "    $PACK/$PACK_NAME.swrl.owl"
    echo "    $PACK/$PACK_NAME.json"
    echo "════════════════════════════════════════════════════════════"
    exit 0
else
    echo "════════════════════════════════════════════════════════════"
    echo "  Reproducibility: FAILED — see the [FAIL] lines above."
    echo "════════════════════════════════════════════════════════════"
    exit 1
fi
