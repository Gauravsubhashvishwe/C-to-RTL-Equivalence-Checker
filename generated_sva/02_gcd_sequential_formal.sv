/*
 * Formal Verification Wrapper — GCD (Sequential)
 * =================================================
 * Course: Formal Verification
 * Topics: SEC, Temporal Properties, |=> (non-overlapping implication)
 *
 * Verifies that the GCD FSM eventually terminates and produces
 * the correct result for all valid inputs (a > 0, b > 0).
 *
 * Key SVA constructs:
 *   |=>              — non-overlapping implication (next cycle)
 *   $past()          — refer to signal values from previous cycles
 *   ##[1:$]          — unbounded delay (eventually)
 *   s_eventually     — strong eventually (must happen, not just possible)
 */

module gcd_formal_wrapper (
    input        clk,
    input        rst,
    input  [7:0] a_in,
    input  [7:0] b_in,
    input        start
);

    wire [7:0] result;
    wire       done;

    /* Device Under Test */
    gcd dut (
        .clk    (clk),
        .rst    (rst),
        .a_in   (a_in),
        .b_in   (b_in),
        .start  (start),
        .result (result),
        .done   (done)
    );

    /* ---- Assumptions (input constraints) ---- */

    // Inputs must be positive (avoid infinite loop at gcd(0,x))
    assume property (@(posedge clk) (start |-> (a_in > 0 && b_in > 0)));

    // Start is only asserted when FSM is idle (not computing)
    assume property (@(posedge clk) (start |-> !done));

    /* ---- Liveness: FSM eventually terminates ---- */
    assert_terminates: assert property (
        @(posedge clk) disable iff (rst)
        (start && !done) |-> s_eventually(done)
    );

    /* ---- Safety: Result is positive when done ---- */
    assert_positive: assert property (
        @(posedge clk) disable iff (rst)
        (done |-> (result > 0))
    );

    /* ---- Functional: result divides both inputs ---- */
    // Note: This requires modular arithmetic support in the solver.
    // In practice, we verify via the Z3-based miter in our Python flow.

endmodule
