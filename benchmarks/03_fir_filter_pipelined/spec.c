/*
 * Benchmark 3: 4-Tap Pipelined FIR Filter — C Specification (Golden Reference)
 * ===============================================================================
 * Course: Formal Verification
 * Topic:  Pipeline Latency Alignment, Datapath Term Normalization
 *
 * Computes y = c0*x0 + c1*x1 + c2*x2 + c3*x3  with fixed coefficients
 * {3, 5, 5, 3}.  The result is accumulated at full 32-bit precision.
 *
 * The RTL implementation uses a 3-stage pipeline (multiply → pairwise-add
 * → final-add).  The formal miter aligns the untimed C specification
 * with the RTL output that appears 3 clock cycles after valid_in.
 */

#include <stdint.h>

int32_t fir_filter(int16_t x0, int16_t x1, int16_t x2, int16_t x3) {
    /* Fixed symmetric coefficients */
    int32_t c0 = 3, c1 = 5, c2 = 5, c3 = 3;

    int32_t acc = c0 * (int32_t)x0
               + c1 * (int32_t)x1
               + c2 * (int32_t)x2
               + c3 * (int32_t)x3;

    return acc;   /* Full 32-bit accumulated output */
}
