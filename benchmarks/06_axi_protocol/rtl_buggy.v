/*
 * Benchmark 6: AMBA AXI Protocol Controller — BUGGY RTL Implementation
 * ====================================================================
 * Course: Formal Verification
 * Reference: https://github.com/PreranaB-dev/axi/tree/master/src/axi
 *
 * INJECTED BUG: Unsynchronized Channel Write (Missing AWVALID Gate)
 *
 * In AXI, the write address channel (AW) and write data channel (W)
 * operate with independent handshakes. Data MUST NOT be committed to
 * memory until the write address is valid (AWVALID == 1).
 *
 * In this buggy implementation, the hardware designer checked `wvalid`
 * and `wstrb`, but forgot to verify `awvalid`:
 *     if (wvalid && wstrb) begin  // BUG: Missing 'awvalid &&' check!
 *         mem_out = wdata;
 *     end
 *
 * Consequence:
 *   When wvalid = 1 and wstrb = 1, but awvalid = 0:
 *   - Golden C spec preserves current memory: mem_out = current_val
 *   - Buggy RTL commits write data prematurely without valid address: mem_out = wdata
 *
 * The formal equivalence checker will flag this with a SAT counterexample
 * where awvalid = 0, wvalid = 1, wstrb = 1.
 */
module axi_protocol (
    input        aclk,
    input        aresetn,
    input        awvalid,
    input  [7:0] awaddr,
    input        wvalid,
    input  [7:0] wdata,
    input        wstrb,
    input        bready,
    input  [7:0] current_val,
    output reg [7:0] mem_out,
    output reg       awready,
    output reg       wready,
    output reg       bvalid,
    output reg [1:0] bresp
);

    always @(*) begin
        awready = 1'b1;
        wready  = 1'b1;
        bresp   = 2'b00;

        bvalid  = awvalid && wvalid;

        /* BUG: Commits write on wvalid without requiring awvalid! */
        if (wvalid && wstrb) begin   /* BUG: Missing 'awvalid &&' */
            mem_out = wdata;
        end else begin
            mem_out = current_val;
        end
    end

endmodule

