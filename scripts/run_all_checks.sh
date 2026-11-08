#!/usr/bin/env bash
# ==============================================================================
# run_all_checks.sh — Run formal equivalence checking across all benchmarks
# ==============================================================================
# Course: Formal Verification
#
# Runs both VALID RTL (should prove EQUIVALENT) and BUGGY RTL (should find
# counterexample) for all four benchmarks.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

echo "=================================================================="
echo " Running Full C-to-RTL Formal Equivalence Checking Suite"
echo " Course: Formal Verification"
echo "=================================================================="
echo ""

# 1. Run Python CLI on both valid and buggy designs
python3 -m src.cli --benchmark all --both

# 2. Run pytest suite
echo ""
echo "=================================================================="
echo " Running Automated Pytest Verification Suite"
echo "=================================================================="
python3 -m pytest tests/test_equivalence.py -v

echo ""
echo "=================================================================="
echo " All Formal Equivalence Checks Completed Successfully!"
echo "=================================================================="

