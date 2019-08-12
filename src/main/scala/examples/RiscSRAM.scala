//See LICENSE for license details.

package dessert.examples

import chisel3._
import chisel3.util._

class RiscSRAM extends Module {
  val io = IO(new RiscIO)
  val fileMem = SeqMem(256, UInt(32.W))
  val codeMem = SeqMem(256, UInt(32.W))

  val idle :: next_pc :: fetch :: decode :: ra_read :: rb_read :: rc_write :: Nil = Enum(7)
  val state = RegInit(idle)

  val add_op :: imm_op :: Nil = Enum(UInt(), 2)
  val pc       = RegInit(0.U(8.W))
  val raData   = Reg(UInt(32.W))
  val rbData   = Reg(UInt(32.W))

  val inst = Reg(UInt(32.W))
  val op   = inst(31,24)
  val rci  = inst(23,16)
  val rai  = inst(15, 8)
  val rbi  = inst( 7, 0)
  val ra   = Mux(rai === 0.U, 0.U, raData)
  val rb   = Mux(rbi === 0.U, 0.U, rbData)

  val code_ren = state === next_pc
  val code = codeMem.read(pc, code_ren && !io.isWr)
  when(io.isWr) {
    codeMem.write(io.wrAddr, io.wrData)
  }

  val file_ren = state === decode || state === ra_read
  val file_wen = state === rc_write && rci =/= 255.U
  val file_addr = Mux(state === decode, rai, rbi)
  val file = fileMem.read(file_addr, file_ren && !file_wen)
  when(file_wen) {
    fileMem.write(rci, io.out)
  }

  io.valid := state === rc_write && rci === 255.U
  io.out := 0.U

  switch(state) {
    is(idle) {
      when(io.boot) {
        state := next_pc
      }
    }
    is(next_pc) {
      pc    := pc + 1.U
      state := fetch
    }
    is(fetch) {
      inst  := code
      switch(code(31,24)) {
        is(imm_op) {
          state := rc_write
        }
        is(add_op) {
          state := decode
        }
      }
    }
    is(decode) {
      state := ra_read
    }
    is(ra_read) {
      raData := file
      state  := rb_read
    }
    is(rb_read) {
      rbData := file
      state  := rc_write
    }
    is(rc_write) {
      state := Mux(io.valid, idle, next_pc)
      switch(op) {
        is(imm_op) {
          io.out := Cat(rai, rbi)
        }
        is(add_op) {
          io.out := ra + rb
        }
      }
    }
  }
}
