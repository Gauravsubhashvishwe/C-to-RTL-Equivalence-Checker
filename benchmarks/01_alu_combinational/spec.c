/*
 * Benchmark 1: Combinational ALU — C Specification (Golden Reference)
 * ====================================================================
 * Course: Formal Verification
 * Topic:  Combinational Equivalence Checking (CEC)
 *
 * This is the untimed, unscheduled high-level specification that serves
 * as the golden reference model.  The corresponding RTL implementations
 * (rtl_valid.v / rtl_buggy.v) must be proven functionally equivalent
 * (or a counterexample must be produced) using SAT/SMT-based formal
 * equivalence checking via miter construction.
 *
 * Operations (3-bit opcode):
 *   0 = ADD   1 = SUB   2 = AND   3 = OR
 *   4 = XOR   5 = SLL   6 = SRL   7 = SRA
 */

#include <stdint.h>

uint32_t alu(uint32_t a, uint32_t b, uint8_t op) {
    uint8_t shamt = b & 31;   /* Shift amount masked to 5 bits */
    switch (op) {
        case 0: return a + b;                          /* ADD */
        case 1: return a - b;                          /* SUB */
        case 2: return a & b;                          /* AND */
        case 3: return a | b;                          /* OR  */
        case 4: return a ^ b;                          /* XOR */
        case 5: return a << shamt;                     /* SLL */
        case 6: return a >> shamt;                     /* SRL (logical)     */
        case 7: return (uint32_t)((int32_t)a >> shamt);/* SRA (arithmetic)  */
        default: return 0;
    }
}

