//See LICENSE for license details.

package dessert
package examples
package testers

import chisel3._
import chisel3.util._
import scala.collection.mutable.ArrayStack

class Stack extends core.ExtModule {
  val clock = IO(Input(Clock()))
  val reset = IO(Input(Bool()))
  val io = IO(new StackIO)
}

class StackTester(p: TestParam) extends Tester(p) {
  val dut = Module(new Stack)

  val ens     = Seq.fill(testNum)(rnd.nextInt(2))
  val pushes  = Seq.fill(testNum)(rnd.nextInt(2))
  val pops    = Seq.fill(testNum)(rnd.nextInt(2))
  val dataIns = Seq.fill(testNum)(BigInt(rnd.nextInt >>> 1) << 1 | rnd.nextInt(2))

  // Gold Stack
  val stack = ArrayStack[BigInt]()
  val (dataOuts, _) = ((0 until testNum) foldLeft (Seq[BigInt](), BigInt(0))){ case ((outs, data), i) =>
    (ens(i): @unchecked) match {
      case 0 => (outs :+ data, data)
      case 1 =>
        val nextData = if (stack.nonEmpty) stack.top else data
        if (pushes(i) == 1 && stack.size < 8) {
          stack.push(dataIns(i))
        } else if (pops(i) == 1 && stack.nonEmpty) {
          stack.pop
        }
        (outs :+ data, nextData)
    }
  }

  val (cntr, done) = Counter(true.B, dataIns.size)
  val success = RegInit(true.B)
  dut.clock := clock
  dut.reset := reset
  dut.io.en     := VecInit(ens     map (_.U))(cntr)
  dut.io.push   := VecInit(pushes  map (_.U))(cntr)
  dut.io.pop    := VecInit(pops    map (_.U))(cntr)
  dut.io.dataIn := VecInit(dataIns map (_.U))(cntr)

  val dataOut = VecInit(dataOuts map (_.U))(cntr)
  when(RegNext(done)) {
    stop(); stop()
  }.otherwise {
    assert(dataOut === dut.io.dataOut)
  }
  printf("cycle: %d, enable: %x, push: %x, pop: %x, dataIn: %x, dataOut: %x ?= %x\n",
    cntr, dut.io.en, dut.io.push, dut.io.pop, dut.io.dataIn, dut.io.dataOut, dataOut)
}
