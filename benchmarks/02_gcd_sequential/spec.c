/*
 * Benchmark 2: Multi-Cycle Euclidean GCD — C Specification (Golden Reference)
 * =============================================================================
 * Course: Formal Verification
 * Topic:  Sequential Equivalence Checking (SEC), FSMD, Bounded Model Checking
 *
 * Subtraction-based Euclidean GCD.  The corresponding RTL is a multi-cycle
 * FSM that performs one compare-and-subtract per clock cycle.  Formal
 * equivalence is established by bounded unrolling of both the C loop and
 * the RTL state machine, then building an FSMD product machine (miter)
 * and querying the Z3 SMT solver.
 *
 * Inputs are restricted to 8-bit unsigned (1–255) to keep bounded
 * unrolling tractable while still demonstrating SEC methodology.
 */

#include <stdint.h>

uint8_t gcd(uint8_t a, uint8_t b) {
    /* Precondition: a > 0 && b > 0 */
    while (a != b) {
        if (a > b)
            a = a - b;
        else
            b = b - a;
    }
    return a;
}

