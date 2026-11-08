/*
 * Benchmark 1: Combinational ALU — VALID RTL Implementation
 * Functionally equivalent to spec.c (should prove UNSAT via miter)
 */
module alu (
    input  [31:0] a,
    input  [31:0] b,
    input  [2:0]  op,
    output reg [31:0] result
);

    wire [4:0] shamt = b[4:0];   /* 5-bit shift amount */

    always @(*) begin
        case (op)
            3'd0: result = a + b;                     /* ADD */
            3'd1: result = a - b;                     /* SUB */
            3'd2: result = a & b;                     /* AND */
            3'd3: result = a | b;                     /* OR  */
            3'd4: result = a ^ b;                     /* XOR */
            3'd5: result = a << shamt;                /* SLL */
            3'd6: result = a >> shamt;                /* SRL */
            3'd7: result = $signed(a) >>> shamt;      /* SRA */
            default: result = 32'd0;
        endcase
    end
endmodule

