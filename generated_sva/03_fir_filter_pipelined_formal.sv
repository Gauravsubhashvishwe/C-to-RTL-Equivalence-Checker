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
