/*
 * Benchmark 3: 4-Tap Pipelined FIR Filter — VALID RTL Implementation
 * Functionally equivalent to spec.c (should prove UNSAT via miter)
 *
 * 3-Stage Pipeline:
 *   Stage 1 (posedge clk): Multiply — p_i = c_i * x_i  (16×16 → 32-bit)
 *   Stage 2 (posedge clk): Pairwise add — sum01 = p0+p1, sum23 = p2+p3 (32-bit)
 *   Stage 3 (posedge clk): Final add — y_out = sum01 + sum23 (full 32-bit precision)
 *
 * Output valid_out asserted 3 cycles after valid_in.
 */
module fir_filter (
    input                clk,
    input                rst,
    input  signed [15:0] x0, x1, x2, x3,
    input                valid_in,
    output reg signed [31:0] y_out,
    output reg               valid_out
);

    /* Fixed coefficients */
    wire signed [15:0] c0 = 16'sd3;
    wire signed [15:0] c1 = 16'sd5;
    wire signed [15:0] c2 = 16'sd5;
    wire signed [15:0] c3 = 16'sd3;

    /* --- Stage 1 registers: products (full 32-bit precision) --- */
    reg signed [31:0] p0, p1, p2, p3;
    reg               valid_s1;

    /* --- Stage 2 registers: pairwise sums (full 32-bit precision) --- */
    reg signed [31:0] sum01, sum23;
    reg               valid_s2;

    always @(posedge clk) begin
        if (rst) begin
            p0 <= 0; p1 <= 0; p2 <= 0; p3 <= 0; valid_s1 <= 0;
            sum01 <= 0; sum23 <= 0; valid_s2 <= 0;
            y_out <= 0; valid_out <= 0;
        end else begin
            /* Stage 1: Multiply */
            p0 <= c0 * x0;
            p1 <= c1 * x1;
            p2 <= c2 * x2;
            p3 <= c3 * x3;
            valid_s1 <= valid_in;

            /* Stage 2: Pairwise add */
            sum01 <= p0 + p1;
            sum23 <= p2 + p3;
            valid_s2 <= valid_s1;

            /* Stage 3: Final add */
            y_out <= sum01 + sum23;
            valid_out <= valid_s2;
        end
    end
endmodule
