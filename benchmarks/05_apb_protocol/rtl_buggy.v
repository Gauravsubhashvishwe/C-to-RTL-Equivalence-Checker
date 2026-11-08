/*
 * Benchmark 5: AMBA APB Protocol Controller — BUGGY RTL Implementation
 * ====================================================================
 * Course: Formal Verification
 * Reference: https://github.com/shubhi704/APB-Protocol
 *
 * INJECTED BUG: Premature Write Violation (Missing PENABLE Qualification)
 *
 * In the AMBA APB specification, writing memory data during the SETUP
 * phase (PSEL = 1, PENABLE = 0) is strictly forbidden.
 *
 * In this buggy implementation, the write condition omits `penable`:
 *     if (psel && pwrite) begin  // BUG: Missing '&& penable'
 *         mem_out = pwdata;
 *     end
 *
 * Consequence:
 *   When psel = 1, penable = 0, pwrite = 1 (SETUP phase):
 *   - Golden C spec leaves memory unchanged: mem_out = current_val
 *   - Buggy RTL commits the write prematurely: mem_out = pwdata
 *
 * The formal verification engine will detect this protocol violation
 * and synthesize a counterexample with penable = 0, psel = 1, pwrite = 1.
 */
module apb_protocol (
    input        pclk,
    input        presetn,
    input        psel,
    input        penable,
    input        pwrite,
    input  [7:0] paddr,
    input  [7:0] pwdata,
    input  [7:0] current_val,
    output reg [7:0] mem_out,
    output reg [7:0] prdata,
    output reg       pready,
    output reg       pslverr
);

    localparam IDLE   = 2'b00,
               SETUP  = 2'b01,
               ACCESS = 2'b10;

    reg [1:0] state;

    always @(*) begin
        pslverr = 1'b0;
        pready  = 1'b1;

        if (psel && !pwrite) begin
            prdata = current_val;
        end else begin
            prdata = 8'd0;
        end

        /* BUG: Writes immediately on PSEL without waiting for PENABLE! */
        if (psel && pwrite) begin   /* BUG: Omitted '&& penable' */
            mem_out = pwdata;
        end else begin
            mem_out = current_val;
        end
    end

    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            state <= IDLE;
        end else begin
            case (state)
                IDLE: begin
                    if (psel && !penable)
                        state <= SETUP;
                    else
                        state <= IDLE;
                end

                SETUP: begin
                    if (psel && penable)
                        state <= ACCESS;
                    else
                        state <= IDLE;
                end

                ACCESS: begin
                    if (pready)
                        state <= (psel && !penable) ? SETUP : IDLE;
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule

