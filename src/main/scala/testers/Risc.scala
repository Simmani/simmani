package dessert
package examples
package testers

import chisel3._
import chisel3.util._

class Risc extends core.ExtModule {
  val clock = IO(Input(Clock()))
  val reset = IO(Input(Bool()))
  val io = IO(new RiscIO)
}
class RiscSRAM extends Risc

case class RiscInst(op: Int, rc: Int, ra: Int, rb: Int) {
  def inst = BigInt(op) << 24 | BigInt(rc) << 16 | BigInt(ra) << 8 | BigInt(rb)
}

abstract class RiscTesterBase[T <: Risc](
    p: TestParam)
   (box: => Risc) extends Tester(p) {
  val dut = Module(box)
  dut.clock := clock
  dut.reset := reset

  val fileData = Array.fill(256)(BigInt(0))
  val fileAddrs = collection.mutable.ArrayBuffer[Int]()
  def randOperand(op: Int) = op match {
    case 0 =>
      val idx = rnd.nextInt(fileAddrs.size + 1)
      if (idx == fileAddrs.size) 0 else fileAddrs(idx)
    case 1 =>
      rnd.nextInt(1 << 8)
  }
  def randInst(rci: Int = rnd.nextInt((1 << 8) - 1)) = {
    val op =
      if (rci == 255) 0
      else if (fileAddrs.nonEmpty) rnd.nextInt(2)
      else 1
    val rai = randOperand(op)
    val rbi = randOperand(op)
    val ra = if (rai == 0) BigInt(0) else fileData(rai)
    val rb = if (rbi == 0) BigInt(0) else fileData(rbi)
    val result = op match {
      case 0 => ra + rb
      case 1 => BigInt(rai) << 8 | BigInt(rbi)
    }
    fileAddrs += rci
    fileData(rci) = result
    // println("file[%d] <= %x".format(rci, result))
    RiscInst(op, rci, rai, rbi).inst
  }

  val numBmarks = (testNum - 1) / 255 + 1
  val (insts, outputs) =
    ((0 until numBmarks) foldLeft (Seq[BigInt](), Seq[BigInt]())){ case ((insts, outputs), i) =>
      // println("")
      fileAddrs.clear
      val size = 255 min (testNum - 255 * i)
      (insts ++ Seq.fill(size)(randInst()) :+ randInst(255), outputs :+ fileData(255))
    }
  val sInit :: sWrite :: sBoot :: sRun :: sDone :: Nil = Enum(5)
  val state = RegInit(sInit)
  val wCntr = RegInit(0.U(log2Ceil(insts.size).W))
  val bCntr = RegInit(0.U(log2Ceil(numBmarks).W))
  val output = VecInit(outputs map (_.U))(bCntr)
  val (cycle, timeout) = Counter(state === sRun, 100000)
  dut.io.isWr   := state === sWrite
  dut.io.boot   := state === sBoot
  dut.io.wrAddr := wCntr
  dut.io.wrData := VecInit(insts map (_.U))(wCntr)

  printf("cycle: %d, isWr: %x, wrAddr: %x, wrData: %x, boot: %x, out: %x, valid: %x\n",
    cycle, dut.io.isWr, dut.io.wrAddr, dut.io.wrData, dut.io.boot, dut.io.out, dut.io.valid)

  switch(state) {
    is(sInit) {
      state := sWrite
    }
    is(sWrite) {
      wCntr := wCntr + 1.U
      when(dut.io.wrAddr === 0xff.U || wCntr === (insts.size - 1).U) {
        state := sBoot
      }
    }
    is(sBoot) {
      state := sRun
    }
    is(sRun) {
      when(dut.io.valid || timeout) {
        printf("output: %x ?= %x\n", dut.io.out, output) 
        assert(dut.io.valid)
        assert(dut.io.out === output)
        state := sInit
        bCntr := bCntr + 1.U
        when(bCntr === (numBmarks - 1).U) {
          stop() ; stop()
        }
      }
    }
  }
}

class RiscTester(p: TestParam) extends RiscTesterBase(p)(new Risc)
class RiscSRAMTester(p: TestParam) extends RiscTesterBase(p)(new RiscSRAM)
