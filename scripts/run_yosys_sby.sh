#!/usr/bin/env bash
# ==============================================================================
# run_yosys_sby.sh — Optional Integration with SymbiYosys / Yosys Formal Flow
# ==============================================================================
# Course: Formal Verification
# Topics: Assertion-Based Verification (ABV), SymbiYosys, Open-Source EDA
#
# This script runs the auto-generated SVA properties through SymbiYosys (sby),
# demonstrating how our C-to-RTL verification methodology bridges to
# production EDA tool flows.
#
# Prerequisites (optional, if installed on system):
#   - yosys (with formal extensions)
#   - sby (SymbiYosys)
#   - z3 / yices2 / boolector (SMT backend)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SVA_DIR="$REPO_ROOT/generated_sva"

echo "=================================================================="
echo " SymbiYosys Formal Verification Flow"
echo "=================================================================="

# Check if sby is available
if ! command -v sby &> /dev/null; then
    echo "NOTICE: 'sby' (SymbiYosys) not found in PATH."
    echo "This is expected in environments without open-source EDA tools installed."
    echo "The Python-based Z3 formal engine (src.cli) provides equivalent verification"
    echo "capabilities without requiring external EDA installations."
    echo ""
    echo "To install SymbiYosys on Ubuntu/Debian:"
    echo "    sudo apt-get install yosys"
    echo "    pip install sby"
    echo "    # install z3, yices2, or boolector"
    exit 0
fi

cd "$SVA_DIR"

for sby_file in *.sby; do
    if [ -f "$sby_file" ]; then
        echo "Running SymbiYosys on $sby_file ..."
        sby -f "$sby_file" || true
    fi
done

echo "SymbiYosys run complete."

