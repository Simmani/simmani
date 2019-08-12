package dessert
package passes

import firrtl._
import firrtl.annotations._
import firrtl.passes.memlib._
import firrtl.CompilerUtils.getLoweringTransforms
import barstools.macros._
import barstools.macros.MacroCompilerAnnotation._
import java.io.File

object CustomMacroTransform extends SeqTransform {
  def inputForm = LowForm
  def outputForm = LowForm
  def transforms = Seq(
    new MacroCompilerTransform,
    firrtl.passes.ResolveKinds,
    firrtl.passes.RemoveEmpty)
}

object CustomTransforms {
  def passes = Seq(
    new InferReadWrite,
    new ReplSeqMem,
    ConfToJSON,
    CustomMacroTransform)

  private sealed trait ArgField
  private case object Macro extends ArgField
  private case object Model extends ArgField
  private case object SVF extends ArgField
  private type Args = Map[ArgField, File]

  private def parseExtraArgs(map: Args, args: List[String]): Args = args match {
    case Nil => map
    case head :: tail if head.size >= 7 &&  head.substring(0, 7) == "+macro=" && head.substring(7).nonEmpty =>
      parseExtraArgs(map + (Macro -> new File(head.substring(7))), tail)
    case head :: tail =>
      parseExtraArgs(map, tail)
  }

  def annos(main: String,
            dir: File,
            // synflop: Boolean,
            args: Seq[String]) = {
    val argMap = parseExtraArgs(Map[ArgField, File](), args.toList)
    val conf = new File(dir, s"${main}.conf")
    val json = new File(dir, s"${main}.json")
    (argMap get Macro match {
      case None => Nil
      case Some(lib) => Seq(
        InferReadWriteAnnotation,
        ReplSeqMemAnnotation("", conf.toString),
        ConfToJSONAnnotation(conf, json),
        MacroCompilerAnnotation(main, Params(
          json.toString,
          Some(lib.toString),
          CostMetric.default,
          /* if (synflop) Synflops else */ Strict,
          false)))
    })
  }
}
