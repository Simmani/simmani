//See LICENSE for license details.

package dessert
package examples

import chisel3._
import chisel3.util._

class ParityIO extends Bundle {
  val in  = Input(Bool())
  val out = Output(Bool())
}

class Parity extends Module {
  val io = IO(new ParityIO)
  val s_even :: s_odd :: Nil = Enum(2)
  val state  = RegInit(s_even)
  when (io.in) {
    when (state === s_even) { state := s_odd  }
    .otherwise              { state := s_even }
  }
  io.out := (state === s_odd)
}
