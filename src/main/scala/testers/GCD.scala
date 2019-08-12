//See LICENSE for license details.

package dessert
package examples
package testers

import chisel3._
import chisel3.util._

class GCD extends core.ExtModule {
  val clock = IO(Input(Clock()))
  val reset = IO(Input(Bool()))
  val io = IO(new GCDIO)
}

class GCDTester(p: TestParam) extends Tester(p) {
  val dut = Module(new GCD)

  def goldGCD(a: BigInt, b: BigInt): BigInt =
    if (b == BigInt(0)) a else goldGCD(b, a % b)

  def genData = {
    val n = BigInt(rnd.nextInt(1 << 8))
    val x = ((n * BigInt(rnd.nextInt(1 << 6))) & BigInt((1L << 16) - 1)) max n
    val y = ((n * BigInt(rnd.nextInt(1 << 6))) & BigInt((1L << 16) - 1)) max n
    val z = goldGCD(x, y)
    (x, y, z)
  }

  val data = Seq.fill(testNum)(genData)
  val as = VecInit(data map (_._1.U))
  val bs = VecInit(data map (_._2.U))
  val zs = VecInit(data map (_._3.U))

  val sStart :: sRun :: sDone :: Nil = Enum(3)
  val state = RegInit(sStart)

  val (cntr, done) = Counter(state === sDone, testNum)
  val cycle = RegInit(0.U(64.W))
  cycle := cycle + 1.U

  dut.clock := clock
  dut.reset := reset
  dut.io.a := as(cntr)
  dut.io.b := bs(cntr)
  dut.io.e := state === sStart

  switch(state) {
    is(sStart) {
      state := sRun
    }
    is(sRun) {
      when(dut.io.v) {
        printf("[cycle: %d] a: %d, b: %d, z: %d ?= %d\n",
          cycle, dut.io.a, dut.io.b, dut.io.z, zs(cntr))
        state := sDone
      }
    }
    is(sDone) {
      assert(dut.io.z === zs(cntr))
      when(done) {
        stop() ; stop()
      }.otherwise {
        state := sStart
      }
    }
  }
}
