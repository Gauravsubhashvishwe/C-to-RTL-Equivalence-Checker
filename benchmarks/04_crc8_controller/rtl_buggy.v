/*
 * Benchmark 4: Bit-Serial CRC-8 Generator — BUGGY RTL Implementation
 * =====================================================================
 * INJECTED BUG: Generator polynomial is 0x05 instead of the correct
 *               0x07.  This corresponds to x^8 + x^2 + 1 (missing the
 *               x term), producing incorrect CRC values for most inputs.
 *
 * The formal checker should produce a counterexample showing that the
 * CRC computed by this RTL differs from the C golden model.
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
    reg [7:0] shreg;
    reg [3:0] bit_cnt;

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
                    if (feedback)
                        crc <= (crc << 1) ^ 8'h05;  /* BUG: wrong polynomial! */
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

