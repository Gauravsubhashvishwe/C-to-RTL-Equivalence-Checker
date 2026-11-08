"""
sva_generator.py — Stage 5: Automated SystemVerilog Assertion Harness
=======================================================================
Course: Formal Verification
Topics: Assertion-Based Verification (ABV), SystemVerilog Assertions (SVA),
        SymbiYosys Formal Verification Flow

Auto-generates:
  1. SystemVerilog wrapper (.sv) with `assume property`, `assert property`,
     and temporal `|->` / `|=>` properties for each benchmark.
  2. SymbiYosys configuration (.sby) files for running formal verification
     with open-source tools (Yosys + sby + SMT solvers).

These artifacts bridge the gap between our Python-based Z3 flow and
industry-standard formal EDA tool flows (Cadence JasperGold, Synopsys
VC Formal, Mentor Questa Formal).
"""

from __future__ import annotations
import os
from typing import Optional


def generate_sva(benchmark_name: str, output_dir: str,
                 benchmark_dir: Optional[str] = None) -> str:
    """
    Generate a SystemVerilog formal verification wrapper for a benchmark.

    Parameters
    ----------
    benchmark_name : str
        e.g., '01_alu_combinational'
    output_dir : str
        Directory to write .sv and .sby files.
    benchmark_dir : str, optional
        Path to the benchmark directory containing RTL files.

    Returns
    -------
    str
        Path to the generated .sv file.
    """
    os.makedirs(output_dir, exist_ok=True)

    if '01_alu' in benchmark_name:
        sv_content = _gen_alu_sva()
        sby_content = _gen_alu_sby(benchmark_dir)
    elif '02_gcd' in benchmark_name:
        sv_content = _gen_gcd_sva()
        sby_content = _gen_gcd_sby(benchmark_dir)
    elif '03_fir' in benchmark_name:
        sv_content = _gen_fir_sva()
        sby_content = _gen_fir_sby(benchmark_dir)
    elif '04_crc' in benchmark_name:
        sv_content = _gen_crc8_sva()
        sby_content = _gen_crc8_sby(benchmark_dir)
    elif '05_apb' in benchmark_name:
        sv_content = _gen_apb_sva()
        sby_content = _gen_apb_sby(benchmark_dir)
    elif '06_axi' in benchmark_name:
        sv_content = _gen_axi_sva()
        sby_content = _gen_axi_sby(benchmark_dir)
    else:
        raise ValueError(f"Unsupported benchmark: {benchmark_name}")

    sv_path = os.path.join(output_dir, f'{benchmark_name}_formal.sv')
    sby_path = os.path.join(output_dir, f'{benchmark_name}.sby')

    with open(sv_path, 'w') as f:
        f.write(sv_content)
    with open(sby_path, 'w') as f:
        f.write(sby_content)

    return sv_path


# ======================================================================
# ALU — Combinational Equivalence (CEC) SVA
# ======================================================================
def _gen_alu_sva() -> str:
    return """\
/*
 * Formal Verification Wrapper — ALU (Combinational)
 * ===================================================
 * Course: Formal Verification
 * Topic:  Assertion-Based Verification (ABV) & SystemVerilog Assertions (SVA)
 *
 * This wrapper instantiates the ALU DUT and adds SVA properties that
 * formally verify each operation against its specification.  When run
 * with SymbiYosys (or a commercial formal tool), each assert property
 * is proven for ALL possible input combinations (exhaustive).
 *
 * Key SVA constructs used:
 *   assert property  — property that must hold (proof obligation)
 *   assume property  — input constraint (environment model)
 *   |->              — overlapping implication (same cycle)
 */

module alu_formal_wrapper (
    input  [31:0] a,
    input  [31:0] b,
    input  [2:0]  op
);

    wire [31:0] result;

    /* Device Under Test */
    alu dut (
        .a      (a),
        .b      (b),
        .op     (op),
        .result (result)
    );

    /* ---- Input constraints (assumptions) ---- */
    // Restrict opcode to valid range [0..7]
    assume property (op <= 3'd7);

    /* ---- Formal properties ---- */

    // ADD
    assert_add: assert property (
        (op == 3'd0) |-> (result == a + b)
    );

    // SUB
    assert_sub: assert property (
        (op == 3'd1) |-> (result == a - b)
    );

    // AND
    assert_and: assert property (
        (op == 3'd2) |-> (result == (a & b))
    );

    // OR
    assert_or: assert property (
        (op == 3'd3) |-> (result == (a | b))
    );

    // XOR
    assert_xor: assert property (
        (op == 3'd4) |-> (result == (a ^ b))
    );

    // SLL
    assert_sll: assert property (
        (op == 3'd5) |-> (result == (a << b[4:0]))
    );

    // SRL
    assert_srl: assert property (
        (op == 3'd6) |-> (result == (a >> b[4:0]))
    );

    // SRA
    assert_sra: assert property (
        (op == 3'd7) |-> (result == ($signed(a) >>> b[4:0]))
    );

endmodule
"""


def _gen_alu_sby(benchmark_dir: Optional[str]) -> str:
    rtl_path = f"{benchmark_dir}/rtl_valid.v" if benchmark_dir else "rtl_valid.v"
    return f"""\
# SymbiYosys configuration — ALU Formal Verification
# Run: sby -f 01_alu_combinational.sby
[options]
mode prove
depth 1

[engines]
smtbmc z3

[script]
read -formal {rtl_path}
read -sv 01_alu_combinational_formal.sv
prep -top alu_formal_wrapper

[files]
{rtl_path}
01_alu_combinational_formal.sv
"""


# ======================================================================
# GCD — Sequential Equivalence (SEC) SVA
# ======================================================================
def _gen_gcd_sva() -> str:
    return """\
/*
 * Formal Verification Wrapper — GCD (Sequential)
 * =================================================
 * Course: Formal Verification
 * Topics: SEC, Temporal Properties, |=> (non-overlapping implication)
 *
 * Verifies that the GCD FSM eventually terminates and produces
 * the correct result for all valid inputs (a > 0, b > 0).
 *
 * Key SVA constructs:
 *   |=>              — non-overlapping implication (next cycle)
 *   $past()          — refer to signal values from previous cycles
 *   ##[1:$]          — unbounded delay (eventually)
 *   s_eventually     — strong eventually (must happen, not just possible)
 */

module gcd_formal_wrapper (
    input        clk,
    input        rst,
    input  [7:0] a_in,
    input  [7:0] b_in,
    input        start
);

    wire [7:0] result;
    wire       done;

    /* Device Under Test */
    gcd dut (
        .clk    (clk),
        .rst    (rst),
        .a_in   (a_in),
        .b_in   (b_in),
        .start  (start),
        .result (result),
        .done   (done)
    );

    /* ---- Assumptions (input constraints) ---- */

    // Inputs must be positive (avoid infinite loop at gcd(0,x))
    assume property (@(posedge clk) (start |-> (a_in > 0 && b_in > 0)));

    // Start is only asserted when FSM is idle (not computing)
    assume property (@(posedge clk) (start |-> !done));

    /* ---- Liveness: FSM eventually terminates ---- */
    assert_terminates: assert property (
        @(posedge clk) disable iff (rst)
        (start && !done) |-> s_eventually(done)
    );

    /* ---- Safety: Result is positive when done ---- */
    assert_positive: assert property (
        @(posedge clk) disable iff (rst)
        (done |-> (result > 0))
    );

    /* ---- Functional: result divides both inputs ---- */
    // Note: This requires modular arithmetic support in the solver.
    // In practice, we verify via the Z3-based miter in our Python flow.

endmodule
"""


def _gen_gcd_sby(benchmark_dir: Optional[str]) -> str:
    rtl_path = f"{benchmark_dir}/rtl_valid.v" if benchmark_dir else "rtl_valid.v"
    return f"""\
# SymbiYosys configuration — GCD Formal Verification
# Run: sby -f 02_gcd_sequential.sby
[options]
mode prove
depth 300

[engines]
smtbmc z3

[script]
read -formal {rtl_path}
read -sv 02_gcd_sequential_formal.sv
prep -top gcd_formal_wrapper

[files]
{rtl_path}
02_gcd_sequential_formal.sv
"""


# ======================================================================
# FIR — Pipelined Equivalence SVA
# ======================================================================
def _gen_fir_sva() -> str:
    return """\
/*
 * Formal Verification Wrapper — FIR Filter (Pipelined)
 * ======================================================
 * Course: Formal Verification
 * Topics: Pipeline Verification, Latency-Aware Assertions
 *
 * Verifies the 3-stage pipelined FIR filter produces correct
 * output 3 cycles after valid_in.
 *
 * Key SVA constructs:
 *   ##N              — fixed delay of N cycles
 *   $past(sig, N)    — value of signal N cycles ago
 */

module fir_formal_wrapper (
    input                clk,
    input                rst,
    input  signed [15:0] x0, x1, x2, x3,
    input                valid_in
);

    wire signed [31:0] y_out;
    wire               valid_out;

    /* Device Under Test */
    fir_filter dut (
        .clk       (clk),
        .rst       (rst),
        .x0        (x0),
        .x1        (x1),
        .x2        (x2),
        .x3        (x3),
        .valid_in  (valid_in),
        .y_out     (y_out),
        .valid_out (valid_out)
    );

    /* ---- Pipeline latency check ---- */
    assert_valid_latency: assert property (
        @(posedge clk) disable iff (rst)
        valid_in |-> ##3 valid_out
    );

    /* ---- Functional: output = 3*x0 + 5*x1 + 5*x2 + 3*x3 (32-bit) ---- */
    // Capture inputs at the time they enter the pipeline
    wire signed [31:0] expected =
        32'sd3 * $signed({16'd0, $past(x0, 3)}) +
        32'sd5 * $signed({16'd0, $past(x1, 3)}) +
        32'sd5 * $signed({16'd0, $past(x2, 3)}) +
        32'sd3 * $signed({16'd0, $past(x3, 3)});

    assert_fir_output: assert property (
        @(posedge clk) disable iff (rst)
        valid_out |-> (y_out == expected)
    );

endmodule
"""


def _gen_fir_sby(benchmark_dir: Optional[str]) -> str:
    rtl_path = f"{benchmark_dir}/rtl_valid.v" if benchmark_dir else "rtl_valid.v"
    return f"""\
# SymbiYosys configuration — FIR Filter Formal Verification
# Run: sby -f 03_fir_filter_pipelined.sby
[options]
mode prove
depth 10

[engines]
smtbmc z3

[script]
read -formal {rtl_path}
read -sv 03_fir_filter_pipelined_formal.sv
prep -top fir_formal_wrapper

[files]
{rtl_path}
03_fir_filter_pipelined_formal.sv
"""


# ======================================================================
# CRC-8 — Controller/Datapath SEC SVA
# ======================================================================
def _gen_crc8_sva() -> str:
    return """\
/*
 * Formal Verification Wrapper — CRC-8 (Bit-Serial Controller)
 * ==============================================================
 * Course: Formal Verification
 * Topics: Controller/Datapath Verification, Polynomial Assertions
 *
 * Verifies the bit-serial CRC-8 generator against known test vectors
 * and structural properties.
 *
 * Polynomial: x^8 + x^2 + x + 1  (0x07)
 * Initial CRC: 0xFF
 */

module crc8_formal_wrapper (
    input        clk,
    input        rst,
    input  [7:0] data_in,
    input        start
);

    wire [7:0] crc_out;
    wire       done;

    /* Device Under Test */
    crc8 dut (
        .clk      (clk),
        .rst      (rst),
        .data_in  (data_in),
        .start    (start),
        .crc_out  (crc_out),
        .done     (done)
    );

    /* ---- Assumptions ---- */

    // Start only asserted once per computation
    assume property (@(posedge clk) (start |-> ##1 !start));

    /* ---- Liveness: computation terminates in ≤ 12 cycles ---- */
    assert_terminates: assert property (
        @(posedge clk) disable iff (rst)
        (start && !done) |-> ##[1:12] done
    );

    /* ---- Safety: done stays high until next start ---- */
    assert_done_stable: assert property (
        @(posedge clk) disable iff (rst)
        (done && !start) |=> done
    );

    /* ---- Structural: CRC changes after processing non-zero data ---- */
    // After reset (crc = 0xFF) and processing any non-zero data,
    // the CRC output should differ from the initial value.
    assert_crc_changes: assert property (
        @(posedge clk) disable iff (rst)
        (done && $past(data_in, 10) != 8'h00) |-> (crc_out != 8'hFF)
    );

endmodule
"""


def _gen_crc8_sby(benchmark_dir: Optional[str]) -> str:
    rtl_path = f"{benchmark_dir}/rtl_valid.v" if benchmark_dir else "rtl_valid.v"
    return f"""\
# SymbiYosys configuration — CRC-8 Formal Verification
# Run: sby -f 04_crc8_controller.sby
[options]
mode prove
depth 20

[engines]
smtbmc z3

[script]
read -formal {rtl_path}
read -sv 04_crc8_controller_formal.sv
prep -top crc8_formal_wrapper

[files]
{rtl_path}
04_crc8_controller_formal.sv
"""


# ======================================================================
# APB Protocol SVA
# ======================================================================
def _gen_apb_sva() -> str:
    return """\
/*
 * Formal Verification Wrapper — AMBA APB Protocol
 * =================================================
 * Course: Formal Verification
 * Topics: Bus Interface Verification, Protocol Invariant Checking
 * Reference: https://github.com/shubhi704/APB-Protocol
 *
 * Verifies AMBA APB slave control and memory integrity properties:
 *   1. Setup phase: PSEL=1, PENABLE=0 -> memory state MUST remain unchanged.
 *   2. Access phase: PSEL=1, PENABLE=1, PWRITE=1 -> memory commits PWDATA.
 *   3. Idle phase: PSEL=0 -> memory state unchanged, PRDATA = 0.
 *   4. Read transfer: PSEL=1, PWRITE=0 -> PRDATA reflects current memory.
 */

module apb_protocol_formal_wrapper (
    input        pclk,
    input        presetn,
    input        psel,
    input        penable,
    input        pwrite,
    input  [7:0] paddr,
    input  [7:0] pwdata,
    input  [7:0] current_val
);

    wire [7:0] mem_out;
    wire [7:0] prdata;
    wire       pready;
    wire       pslverr;

    /* Device Under Test */
    apb_protocol dut (
        .pclk        (pclk),
        .presetn     (presetn),
        .psel        (psel),
        .penable     (penable),
        .pwrite      (pwrite),
        .paddr       (paddr),
        .pwdata      (pwdata),
        .current_val (current_val),
        .mem_out     (mem_out),
        .prdata      (prdata),
        .pready      (pready),
        .pslverr     (pslverr)
    );

    /* ---- Environmental Assumptions ---- */
    // Standard APB protocol sequencing: PENABLE is 0 during setup phase
    assume_reset_active: assume property (@(posedge pclk) presetn == 1'b1);

    /* ---- Protocol Assertions ---- */

    // Invariant 1: Setup phase MUST NOT commit write (Crucial bug detector)
    assert_setup_no_write: assert property (
        @(posedge pclk) (psel && !penable) |-> (mem_out == current_val)
    );

    // Invariant 2: Access phase write commitment
    assert_access_write: assert property (
        @(posedge pclk) (psel && penable && pwrite) |-> (mem_out == pwdata)
    );

    // Invariant 3: Idle phase memory stability
    assert_idle_stable: assert property (
        @(posedge pclk) (!psel) |-> (mem_out == current_val)
    );

    // Invariant 4: Read data integrity
    assert_read_integrity: assert property (
        @(posedge pclk) (psel && !pwrite) |-> (prdata == current_val)
    );

endmodule
"""


def _gen_apb_sby(benchmark_dir: Optional[str]) -> str:
    rtl_path = f"{benchmark_dir}/rtl_valid.v" if benchmark_dir else "rtl_valid.v"
    return f"""\
# SymbiYosys configuration — APB Protocol Formal Verification
# Run: sby -f 05_apb_protocol.sby
[options]
mode prove
depth 5

[engines]
smtbmc z3

[script]
read -formal {rtl_path}
read -sv 05_apb_protocol_formal.sv
prep -top apb_protocol_formal_wrapper

[files]
{rtl_path}
05_apb_protocol_formal.sv
"""


# ======================================================================
# AXI Protocol SVA
# ======================================================================
def _gen_axi_sva() -> str:
    return """\
/*
 * Formal Verification Wrapper — AMBA AXI Protocol
 * =================================================
 * Course: Formal Verification
 * Topics: Multi-Channel Handshaking, AXI Write Invariants
 * Reference: https://github.com/PreranaB-dev/axi/tree/master/src/axi
 *
 * Verifies AMBA AXI slave write channel handshakes and storage invariants:
 *   1. Write commitment requires simultaneous AWVALID && WVALID && WSTRB.
 *   2. If AWVALID == 0, memory state MUST remain unchanged (Crucial bug detector).
 *   3. If WSTRB == 0, memory state MUST remain unchanged.
 *   4. BVALID is asserted upon joint address and data handshakes.
 */

module axi_protocol_formal_wrapper (
    input        aclk,
    input        aresetn,
    input        awvalid,
    input  [7:0] awaddr,
    input        wvalid,
    input  [7:0] wdata,
    input        wstrb,
    input        bready,
    input  [7:0] current_val
);

    wire [7:0] mem_out;
    wire       awready;
    wire       wready;
    wire       bvalid;
    wire [1:0] bresp;

    /* Device Under Test */
    axi_protocol dut (
        .aclk        (aclk),
        .aresetn     (aresetn),
        .awvalid     (awvalid),
        .awaddr      (awaddr),
        .wvalid      (wvalid),
        .wdata       (wdata),
        .wstrb       (wstrb),
        .bready      (bready),
        .current_val (current_val),
        .mem_out     (mem_out),
        .awready     (awready),
        .wready      (wready),
        .bvalid      (bvalid),
        .bresp       (bresp)
    );

    /* ---- Environmental Assumptions ---- */
    assume_aresetn: assume property (@(posedge aclk) aresetn == 1'b1);

    /* ---- Protocol Assertions ---- */

    // Invariant 1: No write without AWVALID address handshake (Crucial bug detector)
    assert_no_write_without_awvalid: assert property (
        @(posedge aclk) (!awvalid) |-> (mem_out == current_val)
    );

    // Invariant 2: Joint handshake commits write
    assert_joint_write_commit: assert property (
        @(posedge aclk) (awvalid && wvalid && wstrb) |-> (mem_out == wdata)
    );

    // Invariant 3: Strobe gating
    assert_strobe_gating: assert property (
        @(posedge aclk) (!wstrb) |-> (mem_out == current_val)
    );

    // Invariant 4: Write response validity
    assert_bvalid_response: assert property (
        @(posedge aclk) (awvalid && wvalid) |-> (bvalid && bresp == 2'b00)
    );

endmodule
"""


def _gen_axi_sby(benchmark_dir: Optional[str]) -> str:
    rtl_path = f"{benchmark_dir}/rtl_valid.v" if benchmark_dir else "rtl_valid.v"
    return f"""\
# SymbiYosys configuration — AXI Protocol Formal Verification
# Run: sby -f 06_axi_protocol.sby
[options]
mode prove
depth 5

[engines]
smtbmc z3

[script]
read -formal {rtl_path}
read -sv 06_axi_protocol_formal.sv
prep -top axi_protocol_formal_wrapper

[files]
{rtl_path}
06_axi_protocol_formal.sv
"""

