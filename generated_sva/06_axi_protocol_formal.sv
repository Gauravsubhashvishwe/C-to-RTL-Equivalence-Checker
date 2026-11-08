/*
 * Formal Verification Wrapper — AMBA AXI Protocol
 * =================================================
 * Course: Formal Verification
 * Topics: Multi-Channel Handshaking, AXI Write Invariants
 * Reference: https://github.com/PreranaB-dev/axi/tree/master/src/axi
 *
 * Verifies AMBA AXI slave write channel handshakes and storage invariants:
 *   1. Write commitment requires simultaneous AWVALID && WVALID && WSTRB.
 *   2. If AWVALID == 0, memory state MUST remain unchanged (Crucial bug detector).
 *   3. If WSTRB == 0, memory state MUST remain unchanged.
 *   4. BVALID is asserted upon joint address and data handshakes.
 */

module axi_protocol_formal_wrapper (
    input        aclk,
    input        aresetn,
    input        awvalid,
    input  [7:0] awaddr,
    input        wvalid,
    input  [7:0] wdata,
    input        wstrb,
    input        bready,
    input  [7:0] current_val
);

    wire [7:0] mem_out;
    wire       awready;
    wire       wready;
    wire       bvalid;
    wire [1:0] bresp;

    /* Device Under Test */
    axi_protocol dut (
        .aclk        (aclk),
        .aresetn     (aresetn),
        .awvalid     (awvalid),
        .awaddr      (awaddr),
        .wvalid      (wvalid),
        .wdata       (wdata),
        .wstrb       (wstrb),
        .bready      (bready),
        .current_val (current_val),
        .mem_out     (mem_out),
        .awready     (awready),
        .wready      (wready),
        .bvalid      (bvalid),
        .bresp       (bresp)
    );

    /* ---- Environmental Assumptions ---- */
    assume_aresetn: assume property (@(posedge aclk) aresetn == 1'b1);

    /* ---- Protocol Assertions ---- */

    // Invariant 1: No write without AWVALID address handshake (Crucial bug detector)
    assert_no_write_without_awvalid: assert property (
        @(posedge aclk) (!awvalid) |-> (mem_out == current_val)
    );

    // Invariant 2: Joint handshake commits write
    assert_joint_write_commit: assert property (
        @(posedge aclk) (awvalid && wvalid && wstrb) |-> (mem_out == wdata)
    );

    // Invariant 3: Strobe gating
    assert_strobe_gating: assert property (
        @(posedge aclk) (!wstrb) |-> (mem_out == current_val)
    );

    // Invariant 4: Write response validity
    assert_bvalid_response: assert property (
        @(posedge aclk) (awvalid && wvalid) |-> (bvalid && bresp == 2'b00)
    );

endmodule
