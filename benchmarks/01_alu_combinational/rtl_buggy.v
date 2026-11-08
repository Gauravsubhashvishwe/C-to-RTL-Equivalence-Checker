/*
 * Benchmark 1: Combinational ALU — BUGGY RTL Implementation
 * ==========================================================
 * INJECTED BUG: SLL (op=5) uses b[3:0] (4-bit shift amount, range 0-15)
 *               instead of b[4:0] (5-bit, range 0-31).
 *
 * This means shifts of 16–31 positions are silently masked to 0–15,
 * producing incorrect results.  The formal checker should find a
 * counterexample with shamt >= 16.
 */
module alu (
    input  [31:0] a,
    input  [31:0] b,
    input  [2:0]  op,
    output reg [31:0] result
);

    wire [4:0] shamt = b[4:0];

    always @(*) begin
        case (op)
            3'd0: result = a + b;
            3'd1: result = a - b;
            3'd2: result = a & b;
            3'd3: result = a | b;
            3'd4: result = a ^ b;
            3'd5: result = a << b[3:0];          /* BUG: 4-bit shift, not 5-bit */
            3'd6: result = a >> shamt;
            3'd7: result = $signed(a) >>> shamt;
            default: result = 32'd0;
        endcase
    end
endmodule

