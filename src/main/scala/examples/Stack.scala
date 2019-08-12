//See LICENSE for license details.

package dessert
package examples

import chisel3._
import chisel3.util._

class StackIO extends Bundle { 
  val push    = Input(Bool())
  val pop     = Input(Bool())
  val en      = Input(Bool())
  val dataIn  = Input(UInt(32.W))
  val dataOut = Output(UInt(32.W))
}

class Stack extends Module {
  val depth = 8
  val io = IO(new StackIO)

  val stack_mem = Mem(depth, UInt(32.W))
  val sp        = RegInit(0.U(log2Up(depth+1).W))
  val out       = RegInit(0.U(32.W))

  when (io.en) {
    when(io.push && (sp < depth.U)) {
      stack_mem(sp) := io.dataIn
      sp := sp + 1.U
    } .elsewhen(io.pop && (sp > 0.U)) {
      sp := sp - 1.U
    }
    when (sp > 0.U) {
      out := stack_mem(sp - 1.U)
    }
  }

  io.dataOut := out
}
