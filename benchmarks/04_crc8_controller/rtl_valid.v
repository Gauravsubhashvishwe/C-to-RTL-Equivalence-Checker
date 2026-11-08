/*
 * Benchmark 4: Bit-Serial CRC-8 Generator — VALID RTL Implementation
 * Functionally equivalent to spec.c (should prove UNSAT via miter)
 *
 * Polynomial: 0x07  (x^8 + x^2 + x + 1)
 * Initial CRC: 0xFF
 * Processes data MSB-first, one bit per clock cycle (8 cycles total).
 *
 * Protocol:
 *   1. Assert rst for at least 1 cycle.
 *   2. De-assert rst, apply data_in, assert start for 1 cycle.
 *   3. Wait 9 cycles: 1 load + 8 compute.
 *   4. done goes high; crc_out holds the CRC result.
 */
module crc8 (
    input        clk,
    input        rst,
    input  [7:0] data_in,
    input        start,
    output reg [7:0] crc_out,
    output reg       done
);

    localparam IDLE    = 2'd0,
               COMPUTE = 2'd1,
               FINISH  = 2'd2;

    reg [1:0] state;
    reg [7:0] crc;
    reg [7:0] shreg;      /* Shift register holding data being processed */
    reg [3:0] bit_cnt;    /* Counts 0 → 7 (8 bits processed) */

    wire feedback = crc[7] ^ shreg[7];

    always @(posedge clk) begin
        if (rst) begin
            state   <= IDLE;
            crc     <= 8'hFF;
            shreg   <= 8'd0;
            bit_cnt <= 4'd0;
            crc_out <= 8'd0;
            done    <= 1'b0;
        end else begin
            case (state)
                IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        shreg   <= data_in;
                        crc     <= 8'hFF;
                        bit_cnt <= 4'd0;
                        state   <= COMPUTE;
                    end
                end

                COMPUTE: begin
                    /* Process one bit per cycle */
                    if (feedback)
                        crc <= (crc << 1) ^ 8'h07;  /* Polynomial XOR */
                    else
                        crc <= (crc << 1);

                    shreg   <= shreg << 1;
                    bit_cnt <= bit_cnt + 1;

                    if (bit_cnt == 4'd7) begin
                        state <= FINISH;
                    end
                end

                FINISH: begin
                    crc_out <= crc;
                    done    <= 1'b1;
                end

                default: state <= IDLE;
            endcase
        end
    end
endmodule

