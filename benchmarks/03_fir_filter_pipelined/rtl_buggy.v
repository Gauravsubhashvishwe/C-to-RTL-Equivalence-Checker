/*
 * Benchmark 3: 4-Tap Pipelined FIR Filter — BUGGY RTL Implementation
 * =====================================================================
 * INJECTED BUG: Stage-2 pairwise adds use truncated 16-bit products
 *               instead of full 32-bit products:
 *
 *   sum01 <= {{16{p0[15]}}, p0[15:0]} + {{16{p1[15]}}, p1[15:0]};
 *   sum23 <= {{16{p2[15]}}, p2[15:0]} + {{16{p3[15]}}, p3[15:0]};
 *
 * In a 32-bit accumulator, truncating the 32-bit products to 16 bits
 * drops the high-order bits whenever c_i * x_i exceeds [-32768, +32767].
 * For example, with c1 = 5, any x1 > 6553 or x1 < -6554 causes
 * sign-extension distortion, producing a counterexample.
 */
module fir_filter (
    input                clk,
    input                rst,
    input  signed [15:0] x0, x1, x2, x3,
    input                valid_in,
    output reg signed [31:0] y_out,
    output reg               valid_out
);

    wire signed [15:0] c0 = 16'sd3;
    wire signed [15:0] c1 = 16'sd5;
    wire signed [15:0] c2 = 16'sd5;
    wire signed [15:0] c3 = 16'sd3;

    reg signed [31:0] p0, p1, p2, p3;
    reg               valid_s1;

    reg signed [31:0] sum01, sum23;
    reg               valid_s2;

    always @(posedge clk) begin
        if (rst) begin
            p0 <= 0; p1 <= 0; p2 <= 0; p3 <= 0; valid_s1 <= 0;
            sum01 <= 0; sum23 <= 0; valid_s2 <= 0;
            y_out <= 0; valid_out <= 0;
        end else begin
            /* Stage 1: Multiply (full precision — same as valid) */
            p0 <= c0 * x0;
            p1 <= c1 * x1;
            p2 <= c2 * x2;
            p3 <= c3 * x3;
            valid_s1 <= valid_in;

            /* Stage 2: BUG — pairwise add uses TRUNCATED 16-bit products */
            sum01 <= {{16{p0[15]}}, p0[15:0]} + {{16{p1[15]}}, p1[15:0]};
            sum23 <= {{16{p2[15]}}, p2[15:0]} + {{16{p3[15]}}, p3[15:0]};
            valid_s2 <= valid_s1;

            /* Stage 3: Final add */
            y_out <= sum01 + sum23;
            valid_out <= valid_s2;
        end
    end
endmodule
