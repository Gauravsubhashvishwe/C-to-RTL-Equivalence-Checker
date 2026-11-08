/*
 * Benchmark 6: AMBA AXI Protocol Controller — VALID RTL Implementation
 * ====================================================================
 * Course: Formal Verification
 * Reference: https://github.com/PreranaB-dev/axi/tree/master/src/axi
 *
 * Compliant AMBA AXI slave write-channel controller.
 *
 * Complies with AXI3/4 specification:
 *   - Both AWVALID and WVALID must be asserted to complete a write transfer.
 *   - BVALID is asserted upon successful address and data handshake.
 *   - Memory state updates only on joint handshake (awvalid && wvalid && wstrb).
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
        /* Default ready handshakes */
        awready = 1'b1;
        wready  = 1'b1;
        bresp   = 2'b00;  /* OKAY response */

        /* Write response valid when both channels present */
        bvalid  = awvalid && wvalid;

        /* Write memory update: requires joint AWVALID && WVALID && WSTRB */
        if (awvalid && wvalid && wstrb) begin
            mem_out = wdata;
        end else begin
            mem_out = current_val;
        end
    end

endmodule

