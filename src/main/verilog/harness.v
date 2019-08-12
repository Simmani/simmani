`ifndef RESET_DELAY
 `define RESET_DELAY 5.5*`CLOCK_PERIOD
`endif

module harness;
  reg clock = 1;
  reg reset = 1;
  reg[63:0] cycle = 0;
  reg[2047:0] vcdfile = 0;
  reg[2047:0] vcdplusfile = 0;

  always #(`CLOCK_PERIOD/2.0) clock = ~clock;
  initial #(`RESET_DELAY) reset = 0;

  `TOP_MODULE tester(
    .clock(clock),
    .reset(reset)
  );
 
  initial begin
    if ($value$plusargs("vcdfile=%s", vcdfile)) begin
      $dumpfile(vcdfile);
      $dumpvars(0, tester.dut);
      $dumpon;
    end
    if ($value$plusargs("vcdplusfile=%s", vcdplusfile)) begin
      $vcdplusfile(vcdplusfile);
      $vcdpluson(0);
    end
  end

  always @(posedge clock) begin
    if (!reset) begin
      cycle <= cycle + 1;
    end
  end
endmodule
