package dessert
package replay

import chisel3.Data
import firrtl._
import firrtl.transforms._
import firrtl.ir.Circuit
import firrtl.annotations.Annotation
import firrtl.CompilerUtils.getLoweringTransforms
import java.io.{File, FileWriter}
import barstools.macros.MacroCompilerAnnotation
import mdf.macrolib.SRAMMacro
import mdf.macrolib.Utils.readMDFFromString

class Compiler extends firrtl.VerilogCompiler {
  override def transforms =
    Seq(new IRToWorkingIR,
        new ResolveAndCheck,
        new HighFirrtlToMiddleFirrtl) ++
    getLoweringTransforms(MidForm, LowForm) :+
    new LowFirrtlOptimization
}

object Compiler {
  def apply(
      chirrtl: Circuit,
      annos: Seq[Annotation],
      io: Seq[Data],
      dir: File,
      customTransforms: Seq[Transform]): CircuitState = {
    dir.mkdirs
    val fir     = new FileWriter(new File(dir, s"${chirrtl.main}.fir"))
    val verilog = new FileWriter(new File(dir, s"${chirrtl.main}.v"))
    val state   = (new LowFirrtlCompiler).compile(
      CircuitState(chirrtl, ChirrtlForm, annos), customTransforms)
    val result  = (new Compiler).compileAndEmit(state, Nil)
    fir write result.circuit.serialize
    fir.close
    verilog write result.getEmittedCircuit.value
    verilog.close
    annos foreach {
      case barstools.macros.MacroCompilerAnnotation(_, params) =>
        // Generate verilog for macros
        val json = params.lib getOrElse params.mem
        val str = scala.io.Source.fromFile(json).mkString
        val srams = readMDFFromString(str) map (_ collect { case x: SRAMMacro => x })
        val mods = (result.circuit.modules map (_.name)).toSet
        val macroWriter = new FileWriter(new File(dir, s"${chirrtl.main}.macros.v"))
        (srams map (_ filter (x => mods(x.name)))
               foreach (_ foreach MacroEmitter(macroWriter)))
        macroWriter.close

        // 
        val pathWriter = new FileWriter(new File(dir, s"${chirrtl.main}.macros.path"))
        val insts = new firrtl.analyses.InstanceGraph(state.circuit)
        srams foreach (_ foreach { m =>
          (insts findInstancesInHierarchy m.name) foreach { is =>
            val path = is map (_.name) mkString "."
            pathWriter write s"${m.name} $path\n"
          }
        })
        pathWriter.close
      case _ =>
    }
    state
  }

  def apply[T <: chisel3.core.UserModule](
      w: => T,
      dir: File,
      customTransforms: Seq[Transform] = Nil,
      annos: Seq[Annotation] = Nil): CircuitState = {
    lazy val dut = w
    val circuit = chisel3.Driver.elaborate(() => dut)
    val chirrtl = firrtl.Parser.parse(chisel3.Driver.emit(circuit))
    val io = dut.getPorts map (_.id)
    apply(chirrtl, (circuit.annotations map (_.toFirrtl)) ++ annos, io, dir, customTransforms)
  }
}
