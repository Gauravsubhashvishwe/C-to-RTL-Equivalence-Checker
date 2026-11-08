/*
 * Benchmark 5: AMBA APB Protocol Controller — C Specification (Golden Reference)
 * ==============================================================================
 * Course: Formal Verification
 * Topic:  Protocol Verification, Bus Handshake & Transaction-Level Modeling
 * Reference: https://github.com/shubhi704/APB-Protocol
 *
 * Untimed behavioral specification of the AMBA Advanced Peripheral Bus (APB)
 * slave interface.
 *
 * APB Protocol Rules:
 *   1. A transfer is initiated when PSEL is asserted.
 *   2. The transfer consists of two phases:
 *      - SETUP phase:  PSEL = 1, PENABLE = 0. Address and control signals driven.
 *                      NO data transfer/write is permitted in this phase.
 *      - ACCESS phase: PSEL = 1, PENABLE = 1. Write strobe occurs; read data is sampled.
 *   3. If PWRITE = 1:
 *        Write occurs only when (PSEL && PENABLE).
 *        Output state = PWDATA.
 *      If PWRITE = 0:
 *        Read occurs when PSEL.
 *        Output PRDATA = current_val.
 *   4. If !PSEL:
 *        Idle state. Output state = current_val, PRDATA = 0.
 */

#include <stdint.h>

uint8_t apb_protocol(uint8_t psel, uint8_t penable, uint8_t pwrite,
                     uint8_t paddr, uint8_t pwdata, uint8_t current_val) {
    /* Mask inputs to standard bitwidths */
    uint8_t sel = psel & 1;
    uint8_t en  = penable & 1;
    uint8_t wr  = pwrite & 1;

    if (!sel) {
        /* IDLE Phase: Slave not selected, memory unchanged */
        return current_val;
    }

    if (wr) {
        /* Write transfer: permitted ONLY in ACCESS phase (PENABLE == 1) */
        if (en) {
            return pwdata;      /* ACCESS phase: write committed */
        } else {
            return current_val; /* SETUP phase: memory remains unchanged */
        }
    } else {
        /* Read transfer: returns current memory contents */
        return current_val;
    }
}

