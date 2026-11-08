/*
 * Benchmark 4: Bit-Serial CRC-8 Generator — C Specification (Golden Reference)
 * ===============================================================================
 * Course: Formal Verification
 * Topic:  Controller/Datapath SEC, Polynomial Arithmetic Verification
 *
 * Computes CRC-8 with polynomial 0x07 (x^8 + x^2 + x + 1) and
 * initial CRC value 0xFF.  Processes one byte of data MSB-first.
 *
 * The RTL implementation is a bit-serial FSM that processes one bit
 * per clock cycle (8 cycles total).  The buggy variant uses a wrong
 * polynomial tap (0x05 instead of 0x07) which the formal checker
 * should expose with a counterexample.
 */

#include <stdint.h>

uint8_t crc8(uint8_t data) {
    uint8_t crc = 0xFF;          /* Initial CRC value */
    int i;
    for (i = 7; i >= 0; i--) {
        uint8_t bit = (data >> i) & 1;
        if (((crc >> 7) & 1) ^ bit) {
            crc = (crc << 1) ^ 0x07;   /* XOR with generator polynomial */
        } else {
            crc = crc << 1;
        }
    }
    return crc;
}

