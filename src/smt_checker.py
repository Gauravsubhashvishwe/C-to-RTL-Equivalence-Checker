"""
smt_checker.py — Stage 4: SMT/SAT Proof & Counterexample Generation
=====================================================================
Course: Formal Verification
Topics: SAT/SMT Solving, Satisfiability, Counterexample Extraction

Uses the Z3 SMT solver to determine the satisfiability of the miter
output (Out_C ≠ Out_RTL):

  - UNSAT → Designs are formally equivalent (Q.E.D.)
  - SAT   → Counterexample found (input vector that exposes the bug)

This module also collects solver statistics (time, decisions, conflicts)
for academic analysis of formal verification complexity.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from z3 import Solver, sat, unsat, unknown, BitVecVal, simplify


@dataclass
class EquivalenceResult:
    """
    Result of formal equivalence checking.

    Attributes
    ----------
    is_equivalent : bool
        True if designs are formally equivalent (UNSAT).
    status : str
        'EQUIVALENT', 'NOT_EQUIVALENT', or 'UNKNOWN'.
    solver_time_ms : float
        Wall-clock time for SMT solving in milliseconds.
    counterexample : dict[str, int] | None
        If SAT, the input vector that distinguishes C from RTL.
    c_output_val : int | None
        C specification output for the counterexample inputs.
    rtl_output_val : int | None
        RTL implementation output for the counterexample inputs.
    solver_stats : dict
        Z3 solver statistics (decisions, conflicts, propagations, etc.).
    """
    is_equivalent: bool = False
    status: str = 'UNKNOWN'
    solver_time_ms: float = 0.0
    counterexample: Optional[Dict[str, int]] = None
    c_output_val: Optional[int] = None
    rtl_output_val: Optional[int] = None
    solver_stats: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable result summary."""
        lines = []
        if self.is_equivalent:
            lines.append("╔══════════════════════════════════════════════════╗")
            lines.append("║   [FORMALLY EQUIVALENT — Q.E.D.]               ║")
            lines.append("║   Miter UNSAT: No input can distinguish C & RTL║")
            lines.append("╚══════════════════════════════════════════════════╝")
        else:
            lines.append("╔══════════════════════════════════════════════════╗")
            lines.append("║   [NOT EQUIVALENT — COUNTEREXAMPLE FOUND]       ║")
            lines.append("║   Miter SAT: Bug-exposing input discovered     ║")
            lines.append("╚══════════════════════════════════════════════════╝")
            if self.counterexample:
                lines.append("  Counterexample inputs:")
                for name, val in self.counterexample.items():
                    lines.append(f"    {name:>12} = {val} (0x{val & 0xFFFFFFFF:X})")
            if self.c_output_val is not None:
                lines.append(f"  C   output = {self.c_output_val} (0x{self.c_output_val & 0xFFFFFFFF:X})")
            if self.rtl_output_val is not None:
                lines.append(f"  RTL output = {self.rtl_output_val} (0x{self.rtl_output_val & 0xFFFFFFFF:X})")

        lines.append(f"  Solver time: {self.solver_time_ms:.2f} ms")
        return '\n'.join(lines)


def check_equivalence(miter) -> EquivalenceResult:
    """
    Check formal equivalence by querying Z3 for satisfiability of the miter.

    Parameters
    ----------
    miter : MiterCircuit
        The constructed miter with miter_output = (Out_C ≠ Out_RTL).

    Returns
    -------
    EquivalenceResult
        Complete result with status, counterexample (if SAT), and solver stats.
    """
    result = EquivalenceResult()
    solver = Solver()

    # Add miter constraint: we want to find inputs where outputs differ
    solver.add(miter.miter_output)

    # Add input constraints (e.g., a > 0 for GCD)
    for constraint in miter.input_constraints:
        solver.add(constraint)

    # Solve with timing
    t_start = time.perf_counter()
    check_result = solver.check()
    t_end = time.perf_counter()
    result.solver_time_ms = (t_end - t_start) * 1000.0

    # Extract solver statistics
    stats = solver.statistics()
    for key in stats.keys():
        try:
            result.solver_stats[key] = stats.get_key_value(key)
        except Exception:
            pass

    # Process result
    if check_result == unsat:
        result.is_equivalent = True
        result.status = 'EQUIVALENT'

    elif check_result == sat:
        result.is_equivalent = False
        result.status = 'NOT_EQUIVALENT'

        # Extract counterexample
        model = solver.model()
        result.counterexample = {}

        for name, bv in miter.shared_inputs.items():
            val = model.evaluate(bv, model_completion=True)
            try:
                int_val = val.as_long()
            except Exception:
                int_val = 0
            result.counterexample[name] = int_val

        # Evaluate C and RTL outputs on the counterexample
        if miter.c_output is not None:
            c_val = model.evaluate(miter.c_output, model_completion=True)
            try:
                result.c_output_val = c_val.as_long()
            except Exception:
                result.c_output_val = 0

        if miter.rtl_output is not None:
            rtl_val = model.evaluate(miter.rtl_output, model_completion=True)
            try:
                result.rtl_output_val = rtl_val.as_long()
            except Exception:
                result.rtl_output_val = 0

    else:
        result.status = 'UNKNOWN'

    return result


def check_with_timeout(miter, timeout_ms: int = 60000) -> EquivalenceResult:
    """
    Check equivalence with a timeout.

    Parameters
    ----------
    miter : MiterCircuit
    timeout_ms : int
        Timeout in milliseconds.
    """
    result = EquivalenceResult()
    solver = Solver()
    solver.set('timeout', timeout_ms)

    solver.add(miter.miter_output)
    for constraint in miter.input_constraints:
        solver.add(constraint)

    t_start = time.perf_counter()
    check_result = solver.check()
    t_end = time.perf_counter()
    result.solver_time_ms = (t_end - t_start) * 1000.0

    stats = solver.statistics()
    for key in stats.keys():
        try:
            result.solver_stats[key] = stats.get_key_value(key)
        except Exception:
            pass

    if check_result == unsat:
        result.is_equivalent = True
        result.status = 'EQUIVALENT'
    elif check_result == sat:
        result.is_equivalent = False
        result.status = 'NOT_EQUIVALENT'
        model = solver.model()
        result.counterexample = {}
        for name, bv in miter.shared_inputs.items():
            val = model.evaluate(bv, model_completion=True)
            try:
                result.counterexample[name] = val.as_long()
            except Exception:
                result.counterexample[name] = 0
        if miter.c_output is not None:
            c_val = model.evaluate(miter.c_output, model_completion=True)
            try:
                result.c_output_val = c_val.as_long()
            except Exception:
                result.c_output_val = 0
        if miter.rtl_output is not None:
            rtl_val = model.evaluate(miter.rtl_output, model_completion=True)
            try:
                result.rtl_output_val = rtl_val.as_long()
            except Exception:
                result.rtl_output_val = 0
    else:
        result.status = 'UNKNOWN'

    return result

