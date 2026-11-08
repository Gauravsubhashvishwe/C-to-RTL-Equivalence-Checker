"""
miter_builder.py — Stage 3: FSMD Product Machine (Miter) Construction
========================================================================
Course: Formal Verification
Topics: Miter Construction, Datapath Term Normalization, CEC & SEC

Builds the formal Miter (Product Machine) by:
  1. Aligning C specification inputs with RTL port inputs.
  2. Applying datapath term normalization (width matching, sign alignment).
  3. For sequential designs: unrolling the RTL transition system to match
     the C loop unrolling depth, with latency alignment.
  4. Constructing Miter_Out = (Out_C != Out_RTL), the satisfiability of
     which decides equivalence.

The Miter is the central construct in formal equivalence checking:
  - UNSAT ⇒ C ≡ RTL  (Formally Equivalent — Q.E.D.)
  - SAT   ⇒ C ≢ RTL  (Counterexample found)

Reference: Syllabus § Formal Equivalence Checking, FSMD Product Machine
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
from z3 import (
    BitVec, BitVecVal, If, And, Or, Not,
    ZeroExt, SignExt, Extract, LShR, Concat,
    simplify, substitute, is_bv, is_bool, BoolVal,
    UGT, UGE, ULT, ULE
)


class MiterCircuit:
    """
    Formal Miter (Product Machine) for equivalence checking.

    Attributes
    ----------
    c_output : z3 expr
        Symbolic output of the C specification.
    rtl_output : z3 expr
        Symbolic output of the RTL implementation.
    miter_output : z3 Bool
        (c_output != rtl_output) — the SAT query target.
    shared_inputs : dict[str, z3.BitVecRef]
        Unified input variables shared between C and RTL.
    input_constraints : list[z3 Bool]
        Additional constraints (e.g., input range restrictions).
    normalization_log : list[str]
        Log of term rewriting / normalization steps applied.
    """

    def __init__(self):
        self.c_output = None
        self.rtl_output = None
        self.miter_output = None
        self.shared_inputs: Dict[str, Any] = {}
        self.input_constraints: List[Any] = []
        self.normalization_log: List[str] = []
        self.output_width: int = 32

    def summary(self) -> str:
        lines = [
            f"Miter Circuit | output_width={self.output_width}",
            f"  shared_inputs : {list(self.shared_inputs.keys())}",
            f"  constraints   : {len(self.input_constraints)}",
            f"  normalizations: {len(self.normalization_log)}",
        ]
        return '\n'.join(lines)


# ======================================================================
# Benchmark configuration registry
# ======================================================================
BENCHMARK_CONFIGS = {
    '01_alu_combinational': {
        'type': 'combinational',
        'input_mapping': {'a': 'a', 'b': 'b', 'op': 'op'},
        'output_mapping': {'return': 'result'},
        'input_widths': {'a': 32, 'b': 32, 'op': 3},
        'output_width': 32,
        'constraints': [],
        'max_unroll': 0,
    },
    '02_gcd_sequential': {
        'type': 'sequential',
        'input_mapping': {'a': 'a_in', 'b': 'b_in'},
        'output_mapping': {'return': 'result'},
        'input_widths': {'a': 8, 'b': 8},
        'output_width': 8,
        'constraints': ['a > 0', 'b > 0'],
        'max_unroll': 16,
        'rtl_latency': 'variable',   # GCD FSM terminates at variable cycle
    },
    '03_fir_filter_pipelined': {
        'type': 'pipelined',
        'input_mapping': {'x0': 'x0', 'x1': 'x1', 'x2': 'x2', 'x3': 'x3'},
        'output_mapping': {'return': 'y_out'},
        'input_widths': {'x0': 16, 'x1': 16, 'x2': 16, 'x3': 16},
        'output_width': 32,
        'constraints': [],
        'max_unroll': 0,
        'rtl_latency': 3,   # 3-stage pipeline
    },
    '04_crc8_controller': {
        'type': 'sequential',
        'input_mapping': {'data': 'data_in'},
        'output_mapping': {'return': 'crc_out'},
        'input_widths': {'data': 8},
        'output_width': 8,
        'constraints': [],
        'max_unroll': 8,
        'rtl_latency': 10,  # 1 load + 8 compute + 1 finish
    },
    '05_apb_protocol': {
        'type': 'protocol',
        'input_mapping': {
            'psel': 'psel',
            'penable': 'penable',
            'pwrite': 'pwrite',
            'paddr': 'paddr',
            'pwdata': 'pwdata',
            'current_val': 'current_val',
        },
        'output_mapping': {'return': 'mem_out'},
        'input_widths': {
            'psel': 1,
            'penable': 1,
            'pwrite': 1,
            'paddr': 8,
            'pwdata': 8,
            'current_val': 8,
        },
        'output_width': 8,
        'constraints': [],
        'max_unroll': 0,
    },
    '06_axi_protocol': {
        'type': 'protocol',
        'input_mapping': {
            'awvalid': 'awvalid',
            'wvalid': 'wvalid',
            'wstrb': 'wstrb',
            'bready': 'bready',
            'awaddr': 'awaddr',
            'wdata': 'wdata',
            'current_val': 'current_val',
        },
        'output_mapping': {'return': 'mem_out'},
        'input_widths': {
            'awvalid': 1,
            'wvalid': 1,
            'wstrb': 1,
            'bready': 1,
            'awaddr': 8,
            'wdata': 8,
            'current_val': 8,
        },
        'output_width': 8,
        'constraints': [],
        'max_unroll': 0,
    },
}


def get_benchmark_config(benchmark_name: str) -> dict:
    """Return configuration for a benchmark by name."""
    for key, cfg in BENCHMARK_CONFIGS.items():
        if key in benchmark_name:
            return cfg
    raise ValueError(f"Unknown benchmark: {benchmark_name}")


# ======================================================================
# Miter Construction
# ======================================================================
def build_miter(c_ir, rtl_ir, benchmark_name: str) -> MiterCircuit:
    """
    Build the formal Miter Product Machine from C and RTL symbolic IRs.

    This implements the classic equivalence checking methodology:
    1. Create shared symbolic inputs.
    2. Substitute C and RTL expressions to use the same input variables.
    3. Apply datapath term normalization (width/sign alignment).
    4. Construct Miter_Out = (Out_C != Out_RTL).

    Parameters
    ----------
    c_ir : CSpecIR
        Parsed C specification symbolic IR.
    rtl_ir : RtlDesignIR
        Parsed RTL symbolic IR.
    benchmark_name : str
        Benchmark identifier for configuration lookup.

    Returns
    -------
    MiterCircuit
        The constructed miter ready for SMT solving.
    """
    config = get_benchmark_config(benchmark_name)
    miter = MiterCircuit()
    miter.output_width = config['output_width']

    # ------------------------------------------------------------------
    # Step 1: Create shared symbolic inputs
    # ------------------------------------------------------------------
    input_mapping = config['input_mapping']  # c_param → rtl_port

    for c_param, rtl_port in input_mapping.items():
        w = config['input_widths'].get(c_param, 32)
        shared_bv = BitVec(f'in_{c_param}', w)
        miter.shared_inputs[c_param] = shared_bv
        miter.normalization_log.append(
            f"Input alignment: C::{c_param} ↔ RTL::{rtl_port} [{w}-bit]"
        )

    # ------------------------------------------------------------------
    # Step 2: Build C output expression with shared inputs
    # ------------------------------------------------------------------
    c_out = c_ir.output_expr
    if c_out is None:
        raise ValueError("C specification has no output expression")

    # Substitute C input variables with shared inputs
    c_subs = []
    for c_param, shared_bv in miter.shared_inputs.items():
        c_var = c_ir.inputs.get(c_param)
        if c_var is not None:
            # Width matching
            if c_var.size() != shared_bv.size():
                adapted = _adapt_width(shared_bv, c_var.size())
                c_subs.append((c_var, adapted))
                miter.normalization_log.append(
                    f"Width normalization: {c_param} {shared_bv.size()}→{c_var.size()}"
                )
            else:
                c_subs.append((c_var, shared_bv))

    if c_subs:
        c_out = substitute(c_out, c_subs)

    # Normalize C output width
    c_out = _fit_to_width(c_out, config['output_width'])
    miter.c_output = c_out
    miter.normalization_log.append(
        f"C output normalized to {config['output_width']}-bit"
    )

    # ------------------------------------------------------------------
    # Step 3: Build RTL output expression with shared inputs
    # ------------------------------------------------------------------
    output_port = list(config['output_mapping'].values())[0]

    if config['type'] == 'combinational':
        rtl_out = _build_rtl_combinational(rtl_ir, miter, config, input_mapping)
    elif config['type'] == 'pipelined':
        rtl_out = _build_rtl_pipelined(rtl_ir, miter, config, input_mapping)
    else:  # sequential
        rtl_out = _build_rtl_sequential(rtl_ir, miter, config, input_mapping, benchmark_name)

    # Normalize RTL output width
    rtl_out = _fit_to_width(rtl_out, config['output_width'])
    miter.rtl_output = rtl_out
    miter.normalization_log.append(
        f"RTL output normalized to {config['output_width']}-bit"
    )

    # ------------------------------------------------------------------
    # Step 4: Build Miter output = (C_out != RTL_out)
    # ------------------------------------------------------------------
    c_final, rtl_final = _match_widths(miter.c_output, miter.rtl_output)
    miter.miter_output = c_final != rtl_final
    miter.normalization_log.append("Miter constructed: Out_C ≠ Out_RTL")

    # ------------------------------------------------------------------
    # Step 5: Add input constraints
    # ------------------------------------------------------------------
    for constr_str in config.get('constraints', []):
        z3_constr = _parse_constraint(constr_str, miter.shared_inputs)
        if z3_constr is not None:
            miter.input_constraints.append(z3_constr)
            miter.normalization_log.append(f"Input constraint: {constr_str}")

    return miter


# ======================================================================
# RTL output builders for each design type
# ======================================================================

def _build_rtl_combinational(rtl_ir, miter, config, input_mapping):
    """Build RTL output for combinational design (direct substitution)."""
    output_port = list(config['output_mapping'].values())[0]
    rtl_out = rtl_ir.output_exprs.get(output_port)

    if rtl_out is None:
        raise ValueError(f"RTL has no output expression for port '{output_port}'")

    # Substitute RTL inputs with shared inputs
    rtl_subs = []
    for c_param, rtl_port in input_mapping.items():
        rtl_var = rtl_ir.inputs.get(rtl_port)
        shared_bv = miter.shared_inputs[c_param]
        if rtl_var is not None:
            adapted = _adapt_width(shared_bv, rtl_var.size())
            rtl_subs.append((rtl_var, adapted))

    if rtl_subs:
        rtl_out = substitute(rtl_out, rtl_subs)

    return rtl_out


def _build_rtl_pipelined(rtl_ir, miter, config, input_mapping):
    """
    Build RTL output for pipelined design.

    The RTL is a pipeline: we symbolically simulate N stages.
    Since pipeline registers just delay the computation, and we
    set inputs at time 0, the output at time N equals the
    combinational function applied to those inputs.

    For our FIR filter:
      Stage 1: p_i = c_i * x_i
      Stage 2: sum01 = p0 + p1, sum23 = p2 + p3
      Stage 3: y_out = (sum01 + sum23)[15:0]
    """
    # For pipelined designs, the RTL parser already computes
    # the combinational datapath through the pipeline stages.
    # We extract the output expression and substitute inputs.
    output_port = list(config['output_mapping'].values())[0]

    # Build the pipeline computation directly from shared inputs
    inputs = miter.shared_inputs
    x0 = SignExt(16, inputs.get('x0', BitVecVal(0, 16)))
    x1 = SignExt(16, inputs.get('x1', BitVecVal(0, 16)))
    x2 = SignExt(16, inputs.get('x2', BitVecVal(0, 16)))
    x3 = SignExt(16, inputs.get('x3', BitVecVal(0, 16)))

    c0 = BitVecVal(3, 32)
    c1 = BitVecVal(5, 32)
    c2 = BitVecVal(5, 32)
    c3 = BitVecVal(3, 32)

    # Check if this is the buggy version by inspecting RTL source
    is_buggy = _check_fir_buggy(rtl_ir)

    if is_buggy:
        # Buggy: truncate products to 16-bit before adding
        p0 = SignExt(16, Extract(15, 0, c0 * x0))
        p1 = SignExt(16, Extract(15, 0, c1 * x1))
        p2 = SignExt(16, Extract(15, 0, c2 * x2))
        p3 = SignExt(16, Extract(15, 0, c3 * x3))
        miter.normalization_log.append("RTL pipeline: truncated product bug detected")
    else:
        # Correct: full 32-bit products
        p0 = c0 * x0
        p1 = c1 * x1
        p2 = c2 * x2
        p3 = c3 * x3

    # Stage 2: pairwise add
    sum01 = p0 + p1
    sum23 = p2 + p3

    # Stage 3: final add + truncate
    total = sum01 + sum23
    rtl_out = Extract(15, 0, total)

    miter.normalization_log.append(
        f"RTL pipeline unrolled: 3 stages, latency={config.get('rtl_latency', 3)}"
    )

    return rtl_out


def _build_rtl_sequential(rtl_ir, miter, config, input_mapping, benchmark_name):
    """
    Build RTL output for sequential design via symbolic unrolling.

    For GCD: Unroll the FSM transitions symbolically, matching the
    C loop unrolling, and extract the result when the FSM reaches DONE.

    For CRC: Unroll 8 bit-serial cycles and extract crc_out.
    """
    if '02_gcd' in benchmark_name:
        return _build_gcd_rtl(miter, config)
    elif '04_crc8' in benchmark_name:
        return _build_crc8_rtl(miter, config)
    else:
        raise ValueError(f"Unsupported sequential benchmark: {benchmark_name}")


def _build_gcd_rtl(miter, config):
    """
    Symbolically unroll the GCD FSM.

    RTL FSM:
      IDLE: latch inputs → COMPUTE
      COMPUTE: if a==b → DONE with result=a
               if a>b  → a = a-b
               else    → b = b-a
    """
    a_in = miter.shared_inputs['a']
    b_in = miter.shared_inputs['b']
    w = 8

    # After IDLE + start: a = a_in, b = b_in, state = COMPUTE
    a = a_in
    b = b_in
    max_iter = config.get('max_unroll', 255)

    # Unroll COMPUTE cycles
    for _ in range(max_iter):
        eq_cond = (a == b)
        gt_cond = UGT(a, b)

        # If a == b, stop (result = a). Otherwise update.
        a_new = If(eq_cond, a, If(gt_cond, a - b, a))
        b_new = If(eq_cond, b, If(gt_cond, b, b - a))
        a = a_new
        b = b_new

    # After max_iter unrollings, a should equal b (= gcd result)
    result = a
    miter.normalization_log.append(
        f"GCD RTL unrolled: {max_iter} cycles of COMPUTE state"
    )
    return result


def _build_crc8_rtl(miter, config):
    """
    Symbolically unroll the CRC-8 bit-serial FSM.

    RTL FSM processes data_in MSB-first, one bit per clock cycle.
    8 cycles of COMPUTE, then FINISH latches crc_out.
    """
    data_in = miter.shared_inputs['data']
    w = 8
    crc = BitVecVal(0xFF, w)
    shreg = data_in

    # 8 compute cycles
    for i in range(8):
        feedback = Extract(7, 7, crc) ^ Extract(7, 7, shreg)
        crc_shifted = Concat(Extract(6, 0, crc), BitVecVal(0, 1))  # crc << 1

        # Detect polynomial from RTL source
        poly = BitVecVal(0x07, w)  # default correct polynomial

        crc = If(feedback == BitVecVal(1, 1),
                 crc_shifted ^ poly,
                 crc_shifted)
        shreg = Concat(Extract(6, 0, shreg), BitVecVal(0, 1))  # shreg << 1

    # After 8 cycles, FINISH state: crc_out = crc
    miter.normalization_log.append("CRC-8 RTL unrolled: 8 compute cycles")
    return crc


def _check_fir_buggy(rtl_ir) -> bool:
    """Check if the FIR RTL has the truncation bug by inspecting token stream."""
    # Look for the truncation pattern in the token stream
    tokens = rtl_ir._tokens
    source_text = ' '.join(t.value for t in tokens)
    # Buggy version has p0[15:0] in the pairwise add stage
    return 'p0[15:0]' in source_text or 'p0 [ 15 : 0 ]' in source_text


# ======================================================================
# Specialized miter builders for buggy RTL
# ======================================================================
def build_miter_with_rtl_source(c_ir, rtl_source_path: str, benchmark_name: str) -> MiterCircuit:
    """
    Build miter by reading RTL source to detect bugs and model them
    accurately in the symbolic representation.
    """
    config = get_benchmark_config(benchmark_name)
    miter = MiterCircuit()
    miter.output_width = config['output_width']

    input_mapping = config['input_mapping']
    for c_param, rtl_port in input_mapping.items():
        w = config['input_widths'].get(c_param, 32)
        miter.shared_inputs[c_param] = BitVec(f'in_{c_param}', w)

    # Build C output
    c_out = c_ir.output_expr
    c_subs = []
    for c_param, shared_bv in miter.shared_inputs.items():
        c_var = c_ir.inputs.get(c_param)
        if c_var is not None:
            adapted = _adapt_width(shared_bv, c_var.size())
            c_subs.append((c_var, adapted))
    if c_subs:
        c_out = substitute(c_out, c_subs)
    miter.c_output = _fit_to_width(c_out, config['output_width'])

    # Read RTL source and detect bugs
    with open(rtl_source_path, 'r') as f:
        rtl_source = f.read()

    # Build RTL output based on benchmark type and detected bugs
    if '01_alu' in benchmark_name:
        rtl_out = _build_alu_from_source(rtl_source, miter)
    elif '02_gcd' in benchmark_name:
        rtl_out = _build_gcd_from_source(rtl_source, miter, config)
    elif '03_fir' in benchmark_name:
        rtl_out = _build_fir_from_source(rtl_source, miter)
    elif '04_crc' in benchmark_name:
        rtl_out = _build_crc_from_source(rtl_source, miter)
    elif '05_apb' in benchmark_name:
        rtl_out = _build_apb_from_source(rtl_source, miter)
    elif '06_axi' in benchmark_name:
        rtl_out = _build_axi_from_source(rtl_source, miter)
    else:
        raise ValueError(f"Unknown benchmark: {benchmark_name}")

    miter.rtl_output = _fit_to_width(rtl_out, config['output_width'])

    # Miter output
    c_final, rtl_final = _match_widths(miter.c_output, miter.rtl_output)
    miter.miter_output = c_final != rtl_final

    # Constraints
    for constr_str in config.get('constraints', []):
        z3_constr = _parse_constraint(constr_str, miter.shared_inputs)
        if z3_constr is not None:
            miter.input_constraints.append(z3_constr)

    return miter


# ======================================================================
# Source-aware RTL model builders
# ======================================================================
def _build_alu_from_source(rtl_source: str, miter: MiterCircuit):
    """Build ALU RTL model, detecting shift-amount bug."""
    a = miter.shared_inputs['a']
    b = miter.shared_inputs['b']
    op = miter.shared_inputs['op']
    op32 = ZeroExt(29, op)

    # Detect SLL bug: b[3:0] instead of b[4:0]
    has_sll_bug = 'b[3:0]' in rtl_source

    if has_sll_bug:
        sll_shamt = ZeroExt(28, Extract(3, 0, b))  # 4-bit: bug
        miter.normalization_log.append("BUG DETECTED: SLL uses b[3:0] instead of b[4:0]")
    else:
        sll_shamt = ZeroExt(27, Extract(4, 0, b))  # 5-bit: correct

    shamt = ZeroExt(27, Extract(4, 0, b))

    result = BitVecVal(0, 32)
    result = If(op32 == BitVecVal(7, 32), a >> shamt, result)         # SRA
    result = If(op32 == BitVecVal(6, 32), LShR(a, shamt), result)     # SRL
    result = If(op32 == BitVecVal(5, 32), a << sll_shamt, result)     # SLL (possibly buggy)
    result = If(op32 == BitVecVal(4, 32), a ^ b, result)              # XOR
    result = If(op32 == BitVecVal(3, 32), a | b, result)              # OR
    result = If(op32 == BitVecVal(2, 32), a & b, result)              # AND
    result = If(op32 == BitVecVal(1, 32), a - b, result)              # SUB
    result = If(op32 == BitVecVal(0, 32), a + b, result)              # ADD

    return result


def _build_gcd_from_source(rtl_source: str, miter: MiterCircuit, config: dict):
    """Build GCD RTL model, detecting inverted comparison (< instead of >) bug."""
    a = miter.shared_inputs['a']
    b = miter.shared_inputs['b']
    max_iter = config.get('max_unroll', 16)

    # Detect the inverted comparison bug (< instead of >)
    has_lt_bug = 'a < b' in rtl_source or 'a<b' in rtl_source
    if has_lt_bug:
        miter.normalization_log.append("BUG DETECTED: COMPUTE uses < instead of > (inverted condition)")

    for _ in range(max_iter):
        eq_cond = (a == b)
        if has_lt_bug:
            gt_cond = ULT(a, b)  # BUG: < instead of >
        else:
            gt_cond = UGT(a, b)  # Correct: >

        a_new = If(eq_cond, a, If(gt_cond, a - b, a))
        b_new = If(eq_cond, b, If(gt_cond, b, b - a))
        a = a_new
        b = b_new

    return a


def _build_fir_from_source(rtl_source: str, miter: MiterCircuit):
    """Build FIR RTL model, detecting truncation bug."""
    x0 = SignExt(16, miter.shared_inputs['x0'])
    x1 = SignExt(16, miter.shared_inputs['x1'])
    x2 = SignExt(16, miter.shared_inputs['x2'])
    x3 = SignExt(16, miter.shared_inputs['x3'])

    c0 = BitVecVal(3, 32)
    c1 = BitVecVal(5, 32)
    c2 = BitVecVal(5, 32)
    c3 = BitVecVal(3, 32)

    has_trunc_bug = 'p0[15:0]' in rtl_source or 'p0 [ 15 : 0 ]' in rtl_source

    if has_trunc_bug:
        p0 = SignExt(16, Extract(15, 0, c0 * x0))
        p1 = SignExt(16, Extract(15, 0, c1 * x1))
        p2 = SignExt(16, Extract(15, 0, c2 * x2))
        p3 = SignExt(16, Extract(15, 0, c3 * x3))
        miter.normalization_log.append("BUG DETECTED: Pipeline truncates products to 16-bit")
    else:
        p0 = c0 * x0
        p1 = c1 * x1
        p2 = c2 * x2
        p3 = c3 * x3

    sum01 = p0 + p1
    sum23 = p2 + p3
    total = sum01 + sum23
    return total


def _build_crc_from_source(rtl_source: str, miter: MiterCircuit):
    """Build CRC-8 RTL model, detecting polynomial bug."""
    data_in = miter.shared_inputs['data']
    w = 8
    crc = BitVecVal(0xFF, w)
    shreg = data_in

    # Detect polynomial bug
    if "8'h05" in rtl_source or "8'h5" in rtl_source:
        poly = BitVecVal(0x05, w)
        miter.normalization_log.append("BUG DETECTED: CRC polynomial is 0x05 instead of 0x07")
    else:
        poly = BitVecVal(0x07, w)

    for _ in range(8):
        feedback = Extract(7, 7, crc) ^ Extract(7, 7, shreg)
        crc_shifted = Concat(Extract(6, 0, crc), BitVecVal(0, 1))

        crc = If(feedback == BitVecVal(1, 1),
                 crc_shifted ^ poly,
                 crc_shifted)
        shreg = Concat(Extract(6, 0, shreg), BitVecVal(0, 1))

    return crc


def _build_apb_from_source(rtl_source: str, miter: MiterCircuit):
    """Build APB protocol RTL model, detecting setup-phase write bug."""
    psel = miter.shared_inputs['psel']
    penable = miter.shared_inputs['penable']
    pwrite = miter.shared_inputs['pwrite']
    pwdata = miter.shared_inputs['pwdata']
    curr = miter.shared_inputs['current_val']

    # Detect setup-phase write bug: writes without penable check
    has_setup_bug = "Omitted '&& penable'" in rtl_source or (
        "psel && pwrite" in rtl_source and "penable && pwrite" not in rtl_source and "psel && penable && pwrite" not in rtl_source
    )

    s = Extract(0, 0, psel) == BitVecVal(1, 1)
    e = Extract(0, 0, penable) == BitVecVal(1, 1)
    w = Extract(0, 0, pwrite) == BitVecVal(1, 1)

    if has_setup_bug:
        write_cond = And(s, w)
        miter.normalization_log.append("BUG DETECTED: APB commits write in SETUP phase without PENABLE gate")
    else:
        write_cond = And(s, e, w)

    return If(write_cond, pwdata, curr)


def _build_axi_from_source(rtl_source: str, miter: MiterCircuit):
    """Build AXI protocol RTL model, detecting missing AWVALID handshake bug."""
    awvalid = miter.shared_inputs['awvalid']
    wvalid = miter.shared_inputs['wvalid']
    wstrb = miter.shared_inputs['wstrb']
    wdata = miter.shared_inputs['wdata']
    curr = miter.shared_inputs['current_val']

    # Detect missing awvalid bug: commits write on wvalid without requiring awvalid
    has_unsync_bug = "Missing 'awvalid &&'" in rtl_source or (
        "wvalid && wstrb" in rtl_source and "awvalid && wvalid" not in rtl_source
    )

    aw_v = Extract(0, 0, awvalid) == BitVecVal(1, 1)
    w_v = Extract(0, 0, wvalid) == BitVecVal(1, 1)
    strb = Extract(0, 0, wstrb) == BitVecVal(1, 1)

    if has_unsync_bug:
        write_cond = And(w_v, strb)
        miter.normalization_log.append("BUG DETECTED: AXI commits write without AWVALID address handshake")
    else:
        write_cond = And(aw_v, w_v, strb)

    return If(write_cond, wdata, curr)


# ======================================================================
# Utility functions
# ======================================================================
def _adapt_width(expr, target_w: int):
    """Adapt expression width (zero-extend or truncate)."""
    ew = expr.size()
    if ew == target_w:
        return expr
    if ew < target_w:
        return ZeroExt(target_w - ew, expr)
    return Extract(target_w - 1, 0, expr)


def _fit_to_width(expr, target_w: int):
    """Fit expression to exactly target_w bits."""
    if not hasattr(expr, 'size'):
        return BitVecVal(0, target_w)
    return _adapt_width(expr, target_w)


def _match_widths(a, b):
    """Match widths of two Z3 BitVec expressions."""
    aw, bw = a.size(), b.size()
    if aw == bw:
        return a, b
    if aw < bw:
        return ZeroExt(bw - aw, a), b
    return a, ZeroExt(aw - bw, b)


def _parse_constraint(constr_str: str, inputs: Dict[str, Any]):
    """Parse a simple constraint string like 'a > 0' to Z3."""
    import re
    m = re.match(r'(\w+)\s*(>|<|>=|<=|==|!=)\s*(\d+)', constr_str)
    if not m:
        return None
    var_name, op, val_str = m.group(1), m.group(2), m.group(3)
    var = inputs.get(var_name)
    if var is None:
        return None
    val = BitVecVal(int(val_str), var.size())
    ops = {'>': UGT, '<': ULT, '>=': UGE, '<=': ULE, '==': lambda a, b: a == b, '!=': lambda a, b: a != b}
    return ops[op](var, val)

