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
