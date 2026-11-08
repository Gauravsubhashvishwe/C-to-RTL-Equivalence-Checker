/*
 * Benchmark 6: AMBA AXI Protocol Controller — C Specification (Golden Reference)
 * ==============================================================================
 * Course: Formal Verification
 * Topic:  Multi-Channel Protocol Handshaking & AXI Write/Read Invariants
 * Reference: https://github.com/PreranaB-dev/axi/tree/master/src/axi
 *
 * Untimed behavioral specification of the AMBA AXI3/AXI4 slave interface.
 *
 * AXI Multi-Channel Handshake Rules:
 *   1. Write Address Channel (AW): AWVALID indicates valid address & control.
 *   2. Write Data Channel (W):     WVALID indicates valid payload data.
 *      WSTRB indicates active byte lane strobe.
 *   3. Write Transaction Invariant:
 *      A write transaction is committed to storage IF AND ONLY IF:
 *        AWVALID == 1 (address valid) AND
 *        WVALID  == 1 (data valid)    AND
 *        WSTRB   == 1 (strobe enabled).
 *      If AWVALID == 0 or WVALID == 0, memory state MUST remain unchanged.
 *   4. Write Response Channel (B):
 *      Asserted after successful address + data handshake.
 */

#include <stdint.h>

uint8_t axi_protocol(uint8_t awvalid, uint8_t wvalid, uint8_t wstrb,
                     uint8_t bready, uint8_t awaddr, uint8_t wdata,
                     uint8_t current_val) {
    uint8_t aw_v = awvalid & 1;
    uint8_t w_v  = wvalid & 1;
    uint8_t strb = wstrb & 1;

    /* AXI Handshake Rule: Commit write ONLY when BOTH address and data are valid */
    if (aw_v && w_v && strb) {
        return wdata;       /* Write committed */
    } else {
        return current_val; /* Memory state preserved */
    }
}

