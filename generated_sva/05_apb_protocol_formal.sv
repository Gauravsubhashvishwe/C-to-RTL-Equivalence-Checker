/*
 * Formal Verification Wrapper — AMBA APB Protocol
 * =================================================
 * Course: Formal Verification
 * Topics: Bus Interface Verification, Protocol Invariant Checking
 * Reference: https://github.com/shubhi704/APB-Protocol
 *
 * Verifies AMBA APB slave control and memory integrity properties:
 *   1. Setup phase: PSEL=1, PENABLE=0 -> memory state MUST remain unchanged.
 *   2. Access phase: PSEL=1, PENABLE=1, PWRITE=1 -> memory commits PWDATA.
 *   3. Idle phase: PSEL=0 -> memory state unchanged, PRDATA = 0.
 *   4. Read transfer: PSEL=1, PWRITE=0 -> PRDATA reflects current memory.
 */

module apb_protocol_formal_wrapper (
    input        pclk,
    input        presetn,
    input        psel,
    input        penable,
    input        pwrite,
    input  [7:0] paddr,
    input  [7:0] pwdata,
    input  [7:0] current_val
);

    wire [7:0] mem_out;
    wire [7:0] prdata;
    wire       pready;
    wire       pslverr;

    /* Device Under Test */
    apb_protocol dut (
        .pclk        (pclk),
        .presetn     (presetn),
        .psel        (psel),
        .penable     (penable),
        .pwrite      (pwrite),
        .paddr       (paddr),
        .pwdata      (pwdata),
        .current_val (current_val),
        .mem_out     (mem_out),
        .prdata      (prdata),
        .pready      (pready),
        .pslverr     (pslverr)
    );

    /* ---- Environmental Assumptions ---- */
    // Standard APB protocol sequencing: PENABLE is 0 during setup phase
    assume_reset_active: assume property (@(posedge pclk) presetn == 1'b1);

    /* ---- Protocol Assertions ---- */

    // Invariant 1: Setup phase MUST NOT commit write (Crucial bug detector)
    assert_setup_no_write: assert property (
        @(posedge pclk) (psel && !penable) |-> (mem_out == current_val)
    );

    // Invariant 2: Access phase write commitment
    assert_access_write: assert property (
        @(posedge pclk) (psel && penable && pwrite) |-> (mem_out == pwdata)
    );

    // Invariant 3: Idle phase memory stability
    assert_idle_stable: assert property (
        @(posedge pclk) (!psel) |-> (mem_out == current_val)
    );

    // Invariant 4: Read data integrity
    assert_read_integrity: assert property (
        @(posedge pclk) (psel && !pwrite) |-> (prdata == current_val)
    );

endmodule
