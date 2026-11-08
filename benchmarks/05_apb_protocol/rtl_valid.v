/*
 * Benchmark 5: AMBA APB Protocol Controller — VALID RTL Implementation
 * ====================================================================
 * Course: Formal Verification
 * Reference: https://github.com/shubhi704/APB-Protocol
 *
 * Compliant AMBA APB slave controller.
 * State machine: IDLE (00) -> SETUP (01) -> ACCESS (10).
 *
 * Formally equivalent to spec.c:
 *   - Write occurs STRICTLY in ACCESS phase (PSEL && PENABLE && PWRITE).
 *   - SETUP phase (PSEL && !PENABLE) does NOT modify memory state.
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
        /* Default combinational outputs */
        pslverr = 1'b0;
        pready  = 1'b1;

        if (psel && !pwrite) begin
            prdata = current_val;   /* Read access */
        end else begin
            prdata = 8'd0;
        end

        /* Write memory update rule (strictly in ACCESS phase) */
        if (psel && penable && pwrite) begin
            mem_out = pwdata;       /* Valid write strobe */
        end else begin
            mem_out = current_val;  /* State preserved */
        end
    end

    /* Sequential protocol state tracker */
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

