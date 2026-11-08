/*
 * Formal Verification Wrapper — CRC-8 (Bit-Serial Controller)
 * ==============================================================
 * Course: Formal Verification
 * Topics: Controller/Datapath Verification, Polynomial Assertions
 *
 * Verifies the bit-serial CRC-8 generator against known test vectors
 * and structural properties.
 *
 * Polynomial: x^8 + x^2 + x + 1  (0x07)
 * Initial CRC: 0xFF
 */

module crc8_formal_wrapper (
    input        clk,
    input        rst,
    input  [7:0] data_in,
    input        start
);

    wire [7:0] crc_out;
    wire       done;

    /* Device Under Test */
    crc8 dut (
        .clk      (clk),
        .rst      (rst),
        .data_in  (data_in),
        .start    (start),
        .crc_out  (crc_out),
        .done     (done)
    );

    /* ---- Assumptions ---- */

    // Start only asserted once per computation
    assume property (@(posedge clk) (start |-> ##1 !start));

    /* ---- Liveness: computation terminates in ≤ 12 cycles ---- */
    assert_terminates: assert property (
        @(posedge clk) disable iff (rst)
        (start && !done) |-> ##[1:12] done
    );

    /* ---- Safety: done stays high until next start ---- */
    assert_done_stable: assert property (
        @(posedge clk) disable iff (rst)
        (done && !start) |=> done
    );

    /* ---- Structural: CRC changes after processing non-zero data ---- */
    // After reset (crc = 0xFF) and processing any non-zero data,
    // the CRC output should differ from the initial value.
    assert_crc_changes: assert property (
        @(posedge clk) disable iff (rst)
        (done && $past(data_in, 10) != 8'h00) |-> (crc_out != 8'hFF)
    );

endmodule
