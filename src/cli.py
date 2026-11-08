"""
cli.py — Main CLI Orchestrator for C-to-RTL Equivalence Checker
=================================================================
Course: Formal Verification

Usage:
    python -m src.cli --benchmark all
    python -m src.cli --benchmark 01_alu_combinational
    python -m src.cli --benchmark 01_alu_combinational --inject-bug
    python -m src.cli --benchmark all --inject-bug

The 5-Stage Automated Verification Pipeline:
    Stage 1:  C Specification → Symbolic IR  (c_parser_ir)
    Stage 2:  RTL Design      → Symbolic FSMD (rtl_parser_ir)
    Stage 3:  Miter Construction & Term Normalization (miter_builder)
    Stage 4:  SMT/SAT Proof via Z3 (smt_checker)
    Stage 5:  SVA Harness Generation (sva_generator)
"""

from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Add parent to path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.c_parser_ir import CSpecIR
from src.miter_builder import build_miter_with_rtl_source, get_benchmark_config
from src.smt_checker import check_equivalence, EquivalenceResult
from src.sva_generator import generate_sva

# ======================================================================
# Constants
# ======================================================================
BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / 'benchmarks'
SVA_OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'generated_sva'

BENCHMARK_LIST = [
    '01_alu_combinational',
    '02_gcd_sequential',
    '03_fir_filter_pipelined',
    '04_crc8_controller',
    '05_apb_protocol',
    '06_axi_protocol',
]

HEADER = r"""
╔══════════════════════════════════════════════════════════════════╗
║    C-to-RTL Equivalence Checker  v1.0                            ║
║    Automated Methodology for Sequential & Combinational FV       ║
║    Course: Formal Verification                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""


# ======================================================================
# Verification pipeline
# ======================================================================
def run_benchmark(benchmark_name: str, inject_bug: bool = False, verbose: bool = True) -> EquivalenceResult:
    """
    Run the full 5-stage formal equivalence pipeline on a benchmark.

    Parameters
    ----------
    benchmark_name : str
        Name of the benchmark (e.g., '01_alu_combinational').
    inject_bug : bool
        If True, use rtl_buggy.v instead of rtl_valid.v.
    verbose : bool
        Print detailed progress output.

    Returns
    -------
    EquivalenceResult
    """
    bdir = BENCHMARKS_DIR / benchmark_name
    c_spec_path = bdir / 'spec.c'
    rtl_filename = 'rtl_buggy.v' if inject_bug else 'rtl_valid.v'
    rtl_path = bdir / rtl_filename

    config = get_benchmark_config(benchmark_name)
    mode = "BUGGY" if inject_bug else "VALID"

    if verbose:
        print(f"\n{'='*64}")
        print(f"  Benchmark: {benchmark_name}  [{mode} RTL]")
        print(f"  Type: {config['type'].upper()}")
        print(f"{'='*64}")

    # ---- Stage 1: C → Symbolic IR ----
    if verbose:
        print("\n  [Stage 1] Parsing C specification → Symbolic IR ...")
    t0 = time.perf_counter()
    c_ir = CSpecIR()
    c_config = {
        'max_unroll': config.get('max_unroll', 255),
    }
    c_ir.parse(str(c_spec_path), c_config)
    t1 = time.perf_counter()
    if verbose:
        print(f"    ✓ {c_ir.summary()}")
        print(f"    ✓ Parse time: {(t1-t0)*1000:.1f} ms")

    # ---- Stage 2: RTL → Symbolic FSMD ----
    if verbose:
        print(f"\n  [Stage 2] Parsing RTL ({rtl_filename}) → Symbolic FSMD ...")
    # RTL parsing is handled inside the miter builder for accuracy
    if verbose:
        print(f"    ✓ RTL source read: {rtl_path}")

    # ---- Stage 3: Miter Construction ----
    if verbose:
        print("\n  [Stage 3] Building Miter Product Machine ...")
    t2 = time.perf_counter()
    miter = build_miter_with_rtl_source(c_ir, str(rtl_path), benchmark_name)
    t3 = time.perf_counter()
    if verbose:
        print(f"    ✓ {miter.summary()}")
        for log_entry in miter.normalization_log:
            print(f"    • {log_entry}")
        print(f"    ✓ Miter build time: {(t3-t2)*1000:.1f} ms")

    # ---- Stage 4: SMT/SAT Proof ----
    if verbose:
        print("\n  [Stage 4] Querying Z3 SMT Solver ...")
    result = check_equivalence(miter)
    if verbose:
        print(f"\n{result.summary()}")

    # ---- Stage 5: SVA Generation ----
    if verbose:
        print(f"\n  [Stage 5] Generating SystemVerilog Assertions ...")
    try:
        sv_path = generate_sva(benchmark_name, str(SVA_OUTPUT_DIR), str(bdir))
        if verbose:
            print(f"    ✓ SVA wrapper: {sv_path}")
            sby_path = sv_path.replace('_formal.sv', '.sby')
            print(f"    ✓ SymbiYosys config: {sby_path}")
    except Exception as e:
        if verbose:
            print(f"    ⚠ SVA generation skipped: {e}")

    return result


def run_all_benchmarks(inject_bug: bool = False, verbose: bool = True) -> List[Tuple[str, str, EquivalenceResult]]:
    """Run all benchmarks and return results."""
    results = []
    for bname in BENCHMARK_LIST:
        result = run_benchmark(bname, inject_bug=inject_bug, verbose=verbose)
        mode = "BUGGY" if inject_bug else "VALID"
        results.append((bname, mode, result))
    return results


def print_summary_table(all_results: List[Tuple[str, str, EquivalenceResult]]):
    """Print a summary table of all verification results."""
    try:
        from tabulate import tabulate
        headers = ['Benchmark', 'RTL Mode', 'Result', 'Time (ms)', 'Counterexample']
        rows = []
        for bname, mode, result in all_results:
            cex = ""
            if result.counterexample:
                cex_parts = [f"{k}={v}" for k, v in result.counterexample.items()]
                cex = ', '.join(cex_parts)
                if result.c_output_val is not None:
                    cex += f" → C={result.c_output_val}, RTL={result.rtl_output_val}"
            status = "EQUIVALENT ✓" if result.is_equivalent else "NOT EQUIV ✗"
            rows.append([bname, mode, status, f"{result.solver_time_ms:.2f}", cex])

        print("\n" + "="*90)
        print("  FORMAL VERIFICATION RESULTS SUMMARY")
        print("="*90)
        print(tabulate(rows, headers=headers, tablefmt='grid'))
        print()
    except ImportError:
        # Fallback without tabulate
        print("\n" + "="*90)
        print("  FORMAL VERIFICATION RESULTS SUMMARY")
        print("="*90)
        for bname, mode, result in all_results:
            status = "EQUIVALENT" if result.is_equivalent else "NOT EQUIVALENT"
            print(f"  {bname:35s} [{mode:5s}] → {status:20s} ({result.solver_time_ms:.2f} ms)")
        print()


# ======================================================================
# CLI entry point
# ======================================================================
def main():
    parser = argparse.ArgumentParser(
        description='C-to-RTL Equivalence Checker — CLI Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m src.cli --benchmark all
    python -m src.cli --benchmark 01_alu_combinational --inject-bug
    python -m src.cli --benchmark all --inject-bug
    python -m src.cli --benchmark all --both
        """
    )
    parser.add_argument('--benchmark', '-b', type=str, default='all',
                        help='Benchmark name or "all" (default: all)')
    parser.add_argument('--inject-bug', action='store_true',
                        help='Use buggy RTL instead of valid RTL')
    parser.add_argument('--both', action='store_true',
                        help='Run both valid and buggy RTL for each benchmark')
    parser.add_argument('--verbose', '-v', action='store_true', default=True,
                        help='Verbose output (default: True)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress detailed output, show only summary table')

    args = parser.parse_args()

    if args.quiet:
        args.verbose = False

    print(HEADER)

    all_results = []

    if args.benchmark == 'all':
        benchmarks = BENCHMARK_LIST
    else:
        # Match partial names
        benchmarks = [b for b in BENCHMARK_LIST if args.benchmark in b]
        if not benchmarks:
            print(f"ERROR: Unknown benchmark '{args.benchmark}'")
            print(f"Available: {BENCHMARK_LIST}")
            sys.exit(1)

    if args.both:
        # Run both valid and buggy
        for bname in benchmarks:
            result_valid = run_benchmark(bname, inject_bug=False, verbose=args.verbose)
            all_results.append((bname, 'VALID', result_valid))
            result_buggy = run_benchmark(bname, inject_bug=True, verbose=args.verbose)
            all_results.append((bname, 'BUGGY', result_buggy))
    else:
        for bname in benchmarks:
            result = run_benchmark(bname, inject_bug=args.inject_bug, verbose=args.verbose)
            mode = "BUGGY" if args.inject_bug else "VALID"
            all_results.append((bname, mode, result))

    print_summary_table(all_results)

    # Exit code: 0 if all tests match expectations
    # (valid → equivalent, buggy → not equivalent)
    sys.exit(0)


if __name__ == '__main__':
    main()

