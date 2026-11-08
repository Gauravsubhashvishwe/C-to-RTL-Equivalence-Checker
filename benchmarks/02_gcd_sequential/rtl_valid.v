/*
 * Benchmark 2: Multi-Cycle Euclidean GCD — VALID RTL Implementation
 * Functionally equivalent to spec.c (should prove UNSAT via miter)
 *
 * Three-state FSM:  IDLE → COMPUTE → DONE
 *   - IDLE:    Wait for start; latch inputs.
 *   - COMPUTE: One compare-and-subtract per clock cycle.
 *   - DONE:    Assert done and hold result.
 */
module gcd (
    input        clk,
    input        rst,
    input  [7:0] a_in,
    input  [7:0] b_in,
    input        start,
    output reg [7:0] result,
    output reg       done
);

    localparam IDLE    = 2'd0,
               COMPUTE = 2'd1,
               DONE    = 2'd2;

    reg [1:0] state;
    reg [7:0] a, b;

    always @(posedge clk) begin
        if (rst) begin
            state  <= IDLE;
            a      <= 8'd0;
            b      <= 8'd0;
            result <= 8'd0;
            done   <= 1'b0;
        end else begin
            case (state)
                IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        a     <= a_in;
                        b     <= b_in;
                        state <= COMPUTE;
                    end
                end

                COMPUTE: begin
                    if (a == b) begin
                        result <= a;
                        done   <= 1'b1;
                        state  <= DONE;
                    end else if (a > b) begin
                        a <= a - b;
                    end else begin
                        b <= b - a;
                    end
                end

                DONE: begin
                    /* Hold result; wait for new start */
                    done <= 1'b1;
                end

                default: state <= IDLE;
            endcase
        end
    end
endmodule

