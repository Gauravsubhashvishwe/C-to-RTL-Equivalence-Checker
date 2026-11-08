"""
test_equivalence.py — Pytest Suite for Formal Equivalence Checking
====================================================================
Course: Formal Verification

Tests both equivalent (valid RTL → UNSAT) and non-equivalent
(buggy RTL → SAT) cases for all 6 benchmarks:
  - 01_alu_combinational
  - 02_gcd_sequential
  - 03_fir_filter_pipelined
  - 04_crc8_controller
  - 05_apb_protocol
  - 06_axi_protocol
"""

import pytest
import os
from pathlib import Path
from src.c_parser_ir import CSpecIR
from src.miter_builder import build_miter_with_rtl_source, get_benchmark_config
from src.smt_checker import check_equivalence

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / 'benchmarks'

BENCHMARKS = [
    '01_alu_combinational',
    '02_gcd_sequential',
    '03_fir_filter_pipelined',
    '04_crc8_controller',
    '05_apb_protocol',
    '06_axi_protocol',
]


@pytest.mark.parametrize('benchmark_name', BENCHMARKS)
def test_valid_rtl_is_equivalent(benchmark_name):
    """
    Test that valid RTL is formally equivalent to C specification.
    Miter should be UNSAT (no counterexample exists).
    """
    bdir = BENCHMARKS_DIR / benchmark_name
    c_spec = bdir / 'spec.c'
    rtl_valid = bdir / 'rtl_valid.v'

    config = get_benchmark_config(benchmark_name)
    c_ir = CSpecIR()
    c_ir.parse(str(c_spec), {'max_unroll': config.get('max_unroll', 16)})

    miter = build_miter_with_rtl_source(c_ir, str(rtl_valid), benchmark_name)
    result = check_equivalence(miter)

    assert result.is_equivalent, (
        f"{benchmark_name} valid RTL failed formal equivalence! "
        f"Miter was SAT: counterexample = {result.counterexample}"
    )
    assert result.status == 'EQUIVALENT'
    assert result.counterexample is None


@pytest.mark.parametrize('benchmark_name', BENCHMARKS)
def test_buggy_rtl_produces_counterexample(benchmark_name):
    """
    Test that buggy RTL is NOT equivalent to C specification.
    Miter should be SAT, producing a concrete counterexample.
    """
    bdir = BENCHMARKS_DIR / benchmark_name
    c_spec = bdir / 'spec.c'
    rtl_buggy = bdir / 'rtl_buggy.v'

    config = get_benchmark_config(benchmark_name)
    c_ir = CSpecIR()
    c_ir.parse(str(c_spec), {'max_unroll': config.get('max_unroll', 16)})

    miter = build_miter_with_rtl_source(c_ir, str(rtl_buggy), benchmark_name)
    result = check_equivalence(miter)

    assert not result.is_equivalent, (
        f"{benchmark_name} buggy RTL was incorrectly proven equivalent! "
        f"Expected SAT counterexample."
    )
    assert result.status == 'NOT_EQUIVALENT'
    assert result.counterexample is not None
    assert len(result.counterexample) > 0

    # Verify that the counterexample actually exposes a discrepancy
    assert result.c_output_val != result.rtl_output_val, (
        f"Counterexample produced identical outputs: "
        f"C={result.c_output_val}, RTL={result.rtl_output_val}"
    )


# ----------------------------------------------------------------------
# Detailed bug validation tests
# ----------------------------------------------------------------------
def test_alu_bug_specifically_shamt_ge_16():
    """Verify that ALU bug occurs when shift amount >= 16."""
    bdir = BENCHMARKS_DIR / '01_alu_combinational'
    c_ir = CSpecIR().parse(str(bdir / 'spec.c'), {})
    miter = build_miter_with_rtl_source(c_ir, str(bdir / 'rtl_buggy.v'), '01_alu_combinational')
    result = check_equivalence(miter)

    assert not result.is_equivalent
    # Counterexample must have op == 5 (SLL) and shift amount >= 16
    assert result.counterexample['op'] == 5
    shamt = result.counterexample['b'] & 31
    assert shamt >= 16, f"Expected shamt >= 16, got {shamt}"


def test_gcd_bug_inverted_comparator():
    """Verify that GCD buggy RTL fails due to inverted condition in datapath mux."""
    bdir = BENCHMARKS_DIR / '02_gcd_sequential'
    config = get_benchmark_config('02_gcd_sequential')
    c_ir = CSpecIR().parse(str(bdir / 'spec.c'), {'max_unroll': 16})
    miter = build_miter_with_rtl_source(c_ir, str(bdir / 'rtl_buggy.v'), '02_gcd_sequential')
    result = check_equivalence(miter)

    assert not result.is_equivalent
    assert result.counterexample is not None
    assert result.c_output_val != result.rtl_output_val


def test_fir_bug_overflows_16bit():
    """Verify that FIR filter bug produces discrepancy due to 16-bit intermediate truncation."""
    bdir = BENCHMARKS_DIR / '03_fir_filter_pipelined'
    c_ir = CSpecIR().parse(str(bdir / 'spec.c'), {})
    miter = build_miter_with_rtl_source(c_ir, str(bdir / 'rtl_buggy.v'), '03_fir_filter_pipelined')
    result = check_equivalence(miter)

    assert not result.is_equivalent
    assert result.c_output_val != result.rtl_output_val

    # Convert unsigned 16-bit model values to signed
    def to_signed16(val):
        return val - 65536 if val >= 32768 else val

    cex = result.counterexample
    prods = [
        3 * to_signed16(cex['x0']),
        5 * to_signed16(cex['x1']),
        5 * to_signed16(cex['x2']),
        3 * to_signed16(cex['x3'])
    ]
    overflows = any(p < -32768 or p > 32767 for p in prods)
    assert overflows, f"Buggy FIR should trigger on product overflow: prods={prods}"


def test_crc8_bug_wrong_polynomial():
    """Verify that CRC-8 bug triggers due to polynomial mismatch (0x05 vs 0x07)."""
    bdir = BENCHMARKS_DIR / '04_crc8_controller'
    config = get_benchmark_config('04_crc8_controller')
    c_ir = CSpecIR().parse(str(bdir / 'spec.c'), {'max_unroll': 8})
    miter = build_miter_with_rtl_source(c_ir, str(bdir / 'rtl_buggy.v'), '04_crc8_controller')
    result = check_equivalence(miter)

    assert not result.is_equivalent
    assert result.c_output_val != result.rtl_output_val


def test_apb_bug_setup_phase_write():
    """Verify that APB bug triggers on SETUP phase write (penable == 0, psel == 1, pwrite == 1)."""
    bdir = BENCHMARKS_DIR / '05_apb_protocol'
    c_ir = CSpecIR().parse(str(bdir / 'spec.c'), {})
    miter = build_miter_with_rtl_source(c_ir, str(bdir / 'rtl_buggy.v'), '05_apb_protocol')
    result = check_equivalence(miter)

    assert not result.is_equivalent
    cex = result.counterexample
    # Counterexample must expose premature write when penable == 0
    assert cex['psel'] == 1
    assert cex['penable'] == 0
    assert cex['pwrite'] == 1
    assert cex['pwdata'] != cex['current_val']


def test_axi_bug_missing_awvalid_handshake():
    """Verify that AXI bug triggers on missing AWVALID (awvalid == 0, wvalid == 1, wstrb == 1)."""
    bdir = BENCHMARKS_DIR / '06_axi_protocol'
    c_ir = CSpecIR().parse(str(bdir / 'spec.c'), {})
    miter = build_miter_with_rtl_source(c_ir, str(bdir / 'rtl_buggy.v'), '06_axi_protocol')
    result = check_equivalence(miter)

    assert not result.is_equivalent
    cex = result.counterexample
    # Counterexample must expose write without address validity
    assert cex['awvalid'] == 0
    assert cex['wvalid'] == 1
    assert cex['wstrb'] == 1
    assert cex['wdata'] != cex['current_val']
