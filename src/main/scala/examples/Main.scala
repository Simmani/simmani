//See LICENSE for license details.

package dessert
package examples

import java.io.{File, FileWriter}
import chisel3.testers.BasicTester
import testers.TestParam
import dessert.passes.CustomTransforms.{
  passes => customPasses, annos => customAnnos}

object Generator extends App {
  require(args.size >= 3, Seq(
    "Usage: sbt> runMain", "dessert.examples.Generator", "TargetDir",
    "TopModuleProjectName", "TopModuleName", "[extra args]") mkString " ")

  val (targetDir :: 
    targetProject ::
    targetDesign ::
    extraArgs) = args.toList

  println(extraArgs)

  val miniParams = (new mini.MiniConfig).toInstance

  def dut = (targetProject, targetDesign) match {
    case ("mini", "Tile") =>
      new mini.Tile(miniParams)
    case (project, target) =>
      Class.forName(s"${project}.${target}")
           .newInstance.asInstanceOf[chisel3.core.UserModule]
  }

  val hexDir = new File("designs/riscv-mini/src/test/resources")
  def miniBox = new dessert.examples.testers.Tile(miniParams)
  def testers: Seq[(() => BasicTester, String)] = (targetProject, targetDesign) match {
    case ("mini", "Tile") => hexDir.listFiles filter (_.getName.endsWith(".hex")) map { hex =>
      val loadmem = io.Source.fromFile(hex).getLines
      val test = hex.getName.stripSuffix(".hex")
      (() => new mini.TileTester(miniBox, loadmem, 1000000)(miniParams), s"-${test}")
    }
    case (project, target) => Seq((5000, 0, ""), (5000, 1, "-5000")) map { case (testNum, seed, suffix) =>
      (() => Class.forName(s"${project}.testers.${target}Tester")
                  .getConstructor(classOf[TestParam])
                  .newInstance(TestParam(testNum, seed))
                  .asInstanceOf[BasicTester], suffix)
    }
  }

  def annos = customAnnos(targetDesign, new File(targetDir), extraArgs)
  replay.Compiler(dut, new File(targetDir), customPasses, annos)

  testers foreach { case (tester, suffix) =>
    val circuit = chisel3.Driver.elaborate(tester)
    val chirrtl = firrtl.Parser.parse(chisel3.Driver.emit(circuit))
    val verilog = new FileWriter(new File(targetDir, s"${targetDesign}.tester${suffix}.v"))
    val result  = (new firrtl.VerilogCompiler).compileAndEmit(
      firrtl.CircuitState(chirrtl, firrtl.ChirrtlForm), Nil)
    verilog.write(result.getEmittedCircuit.value)
    verilog.close
  }
}
