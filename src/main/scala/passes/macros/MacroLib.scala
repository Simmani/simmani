package mdf.macrolib

import java.io.File
import play.api.libs.json._
import scala.collection.mutable.ListBuffer
import scala.language.implicitConversions

// TODO: decide if we should always silently absorb errors

// See macro_format.yml for the format description.

// "Base class" for macros
abstract class Macro {
  def name: String

  // Type of macro is determined by subclass
  def typeStr: String

  def toJSON(): JsObject
}

// Filler and metal filler
abstract class FillerMacroBase(name: String, vt: String) extends Macro {
  override def toString(): String = {
    s"${this.getClass.getSimpleName}(name=${name}, vt=${vt})"
  }

  override def toJSON(): JsObject = {
    JsObject(Seq(
      "type" -> JsString(typeStr),
      "name" -> Json.toJson(name),
      "vt" -> Json.toJson(vt)
    ))
  }
}
object FillerMacroBase {
  def parseJSON(json:Map[String, JsValue]): Option[FillerMacroBase] = {
    val typee: String = json.get("type") match {
      case Some(x:JsString) => x.value match {
        case "" => return None
        case x => x
      }
      case _ => return None
    }
    val name: String = json.get("name") match {
      case Some(x:JsString) => x.value match {
        case "" => return None
        case x => x
      }
      case _ => return None
    }
    val vt: String = json.get("vt") match {
      case Some(x:JsString) => x.value match {
        case "" => return None
        case x => x
      }
      case _ => return None
    }
    typee match {
      case "metal filler cell" => Some(MetalFillerMacro(name, vt))
      case "filler cell" => Some(FillerMacro(name, vt))
      case _ => None
    }
  }
}

case class FillerMacro(name: String, vt: String) extends FillerMacroBase(name, vt) {
  override def typeStr = "filler cell"
}
case class MetalFillerMacro(name: String, vt: String) extends FillerMacroBase(name, vt) {
  override def typeStr = "metal filler cell"
}

// SRAM macro
case class SRAMMacro(
  name: String,
  width: Int,
  depth: Int,
  family: String,
  ports: Seq[MacroPort],
  extraPorts: Seq[MacroExtraPort] = List()
) extends Macro {
  override def toJSON(): JsObject = {
    val output = new ListBuffer[(String, JsValue)]()
    output.appendAll(Seq(
      "type" -> JsString("sram"),
      "name" -> Json.toJson(name),
      "width" -> Json.toJson(width),
      "depth" -> Json.toJson(depth),
      "ports" -> JsArray(ports map { _.toJSON })
    ))
    if (family != "") {
      output.appendAll(Seq("family" -> Json.toJson(family)))
    }
    if (extraPorts.length > 0) {
      output.appendAll(Seq("extra ports" -> JsArray(extraPorts map { _.toJSON })))
    }

    JsObject(output)
  }

  override def typeStr = "sram"
}
object SRAMMacro {
  def parseJSON(json: Map[String, JsValue]): Option[SRAMMacro] = {
    val name: String = json.get("name") match {
      case Some(x: JsString) => x.as[String]
      case _ => return None
    }
    val width: Int = json.get("width") match {
      case Some(x: JsNumber) => x.value.intValue
      case _ => return None
    }
    val depth: Int = json.get("depth") match {
      case Some(x: JsNumber) => x.value.intValue
      case _ => return None
    }
    val family: String = json.get("family") match {
      case Some(x: JsString) => x.as[String]
      case _ => "" // optional
    }
    val ports: Seq[MacroPort] = json.get("ports") match {
      case Some(x: JsArray) => x.as[List[Map[String, JsValue]]] map { a =>
        val b = MacroPort.parseJSON(a, width, depth); if (b == None) {
          return None
        } else b.get
      }
      case _ => List()
    }
    if (ports.length == 0) {
      // Can't have portless memories.
      return None
    }
    val extraPorts: Seq[MacroExtraPort] = json.get("extra ports") match {
      case Some(x: JsArray) => x.as[List[Map[String, JsValue]]] map { a =>
        val b = MacroExtraPort.parseJSON(a); if (b == None) {
          return None
        } else b.get
      }
      case _ => List()
    }
    Some(SRAMMacro(name, width, depth, family, ports, extraPorts))
  }
}

// SRAM compiler
case class SRAMGroup(
  name: Seq[String],
  family: String,
  vt: Seq[String],
  mux: Int,
  depth: Range,
  width: Range,
  ports: Seq[MacroPort],
  extraPorts: Seq[MacroExtraPort] = List()
) {
  def toJSON: JsObject = {
    val output = new ListBuffer[(String, JsValue)]()
    output.appendAll(Seq(
      "name" -> JsArray(name.map(Json.toJson(_))),
      "vt" -> JsArray(vt.map(Json.toJson(_))),
      "mux" -> Json.toJson(mux),
      "depth" -> JsArray(Seq(depth.start, depth.end, depth.step).map{x =>Json.toJson(x)}),
      "width" -> JsArray(Seq(width.start, width.end, width.step).map{x =>Json.toJson(x)}),
      "ports" -> JsArray(ports map { _.toJSON })
    ))
    if (family != "") {
      output.appendAll(Seq("family" -> Json.toJson(family)))
    }
    if (extraPorts.length > 0) {
      output.appendAll(Seq("extra ports" -> JsArray(extraPorts map { _.toJSON })))
    }
    JsObject(output)
  }
}
object SRAMGroup {
  def parseJSON(json: Map[String, JsValue]): Option[SRAMGroup] = {
    val family: String = json.get("family") match {
      case Some(x: JsString) => x.as[String]
      case _ => "" // optional
    }
    val name: Seq[String] = json.get("name") match {
      case Some(x: JsArray) => x.as[List[JsString]].map(_.as[String])
      case _ => return None
    }
    val vt: Seq[String] = json.get("vt") match {
      case Some(x: JsArray) => x.as[List[JsString]].map(_.as[String])
      case _ => return None
    }
    val mux: Int = json.get("mux") match {
      case Some(x: JsNumber) => x.value.intValue
      case _ => return None
    }
    val depth: Range = json.get("depth") match {
      case Some(x: JsArray) =>
        val seq = x.as[List[JsNumber]].map(_.value.intValue)
        Range.inclusive(seq(0), seq(1), seq(2))
      case _ => return None
    }
    val width: Range = json.get("width") match {
      case Some(x: JsArray) =>
        val seq = x.as[List[JsNumber]].map(_.value.intValue)
        Range.inclusive(seq(0), seq(1), seq(2))
      case _ => return None
    }
    val ports: Seq[MacroPort] = json.get("ports") match {
      case Some(x: JsArray) => x.as[List[Map[String, JsValue]]] map { a => {
        val b = MacroPort.parseJSON(a, None, None); if (b == None) {
          return None
        } else b.get
      }
      }
      case _ => List()
    }
    if (ports.length == 0) {
      // Can't have portless memories.
      return None
    }
    val extraPorts: Seq[MacroExtraPort] = json.get("extra ports") match {
      case Some(x: JsArray) => x.as[List[Map[String, JsValue]]] map { a => {
        val b = MacroExtraPort.parseJSON(a); if (b == None) {
          return None
        } else b.get
      }
      }
      case _ => List()
    }
    Some(SRAMGroup(name, family, vt, mux, depth, width, ports, extraPorts))
  }
}

case class SRAMCompiler(
  name: String,
  groups: Seq[SRAMGroup]
) extends Macro {
  override def toJSON(): JsObject = {
    val output = new ListBuffer[(String, JsValue)]()
    output.appendAll(Seq(
      "type" -> Json.toJson("sramcompiler"),
      "name" -> Json.toJson(name),
      "groups" -> JsArray(groups map { _.toJSON })
    ))

    JsObject(output)
  }

  override def typeStr = "sram"
}
object SRAMCompiler {
  def parseJSON(json:Map[String, JsValue]): Option[SRAMCompiler] = {
    val name: String = json.get("name") match {
      case Some(x:JsString) => x.as[String]
      case _ => return None
    }
    val groups: Seq[SRAMGroup] = json.get("groups") match {
      case Some(x:JsArray) => x.as[List[Map[String, JsValue]]] map { a => { val b = SRAMGroup.parseJSON(a); if (b == None) { return None } else b.get } }
      case _ => List()
    }
    if (groups.length == 0) {
      // Can't have portless memories.
      return None
    }
    Some(SRAMCompiler(name, groups))
  }
}

// Type of extra port
sealed abstract class MacroExtraPortType
case object Constant extends MacroExtraPortType
object MacroExtraPortType {
  implicit def toMacroExtraPortType(s: Any): Some[MacroExtraPortType] = {
    s match {
      case "constant" => Some(Constant)
      case _ => None
    }
  }

  implicit def toString(t: MacroExtraPortType): String = {
    t match {
      case Constant => "constant"
      case _ => ""
    }
  }
}

// Extra port in SRAM
case class MacroExtraPort(
  name: String,
  width: Int,
  portType: MacroExtraPortType,
  value: BigInt
) {
  def toJSON(): JsObject = {
    JsObject(Seq(
      "name" -> Json.toJson(name),
      "width" -> Json.toJson(width),
      "type" -> JsString(MacroExtraPortType.toString(portType)),
      "value" -> JsNumber(BigDecimal(value))
    ))
  }
}
object MacroExtraPort {
  def parseJSON(json:Map[String, JsValue]): Option[MacroExtraPort] = {
    val name = json.get("name") match {
      case Some(x:JsString) => x.value
      case _ => return None
    }
    val width = json.get("width") match {
      case Some(x:JsNumber) => x.value.intValue
      case _ => return None
    }
    val portType: MacroExtraPortType = json.get("type") match {
      case Some(x:JsString) => MacroExtraPortType.toMacroExtraPortType(x.value) match {
        case Some(t:MacroExtraPortType) => t
        case _ => return None
      }
      case _ => return None
    }
    val value = json.get("value") match {
      case Some(x:JsNumber) => x.value.toBigInt
      case _ => return None
    }
    Some(MacroExtraPort(name, width, portType, value))
  }
}

// A named port that also has polarity.
case class PolarizedPort(name: String, polarity: PortPolarity) {
  def toSeqMap(prefix: String): Seq[Tuple2[String, JsValue]] = {
    Seq(
      prefix + " port name" -> Json.toJson(name),
      prefix + " port polarity" -> JsString(polarity)
    )
  }
}
object PolarizedPort {
  // Parse a pair of "<prefix> port name" and "<prefix> port polarity" keys into a
  // polarized port definition.
  def parseJSON(json:Map[String, JsValue], prefix: String): Option[PolarizedPort] = {
    val name = json.get(prefix + " port name") match {
      case Some(x:JsString) => Some(x.value)
      case _ => None
    }
    val polarity: Option[PortPolarity] = json.get(prefix + " port polarity") match {
      case Some(x:JsString) => Some(x.value)
      // TODO: eliminate this hack once PLSI is fixed to always emit polarities
      case None => Some(if (prefix == "clock") PositiveEdge else ActiveHigh)
      case _ => None
    }

    (name, polarity) match {
      case (Some(n:String), Some(p:PortPolarity)) => Some(PolarizedPort(n, p))
      case _ => None
    }
  }
}

// A SRAM memory port
case class MacroPort(
  address: PolarizedPort,
  clock: PolarizedPort,

  writeEnable: Option[PolarizedPort] = None,
  readEnable: Option[PolarizedPort] = None,
  chipEnable: Option[PolarizedPort] = None,

  output: Option[PolarizedPort] = None,
  input: Option[PolarizedPort] = None,

  maskPort: Option[PolarizedPort] = None,
  maskGran: Option[Int] = None,

  // For internal use only; these aren't port-specific.
  width: Option[Int],
  depth: Option[Int]
  ) {
  def effectiveMaskGran = maskGran.getOrElse(width.get)

  def toJSON(): JsObject = {
    val keys: Seq[Tuple2[String, Option[Any]]] = Seq(
      "address" -> Some(address),
      "clock" -> Some(clock),
      "write enable" -> writeEnable,
      "read enable" -> readEnable,
      "chip enable" -> chipEnable,

      "output" -> output,
      "input" -> input,

      "mask" -> maskPort,
      "mask granularity" -> maskGran
    )
    JsObject(keys.flatMap(k => {
      val (key, value) = k
      value match {
        case Some(x:Int) => Seq(key -> JsNumber(x))
        case Some(x:PolarizedPort) => x.toSeqMap(key)
        case _ => List()
      }
    }))
  }

  // Check that all port names are unique.
  private val polarizedPorts = List(Some(address), Some(clock), writeEnable, readEnable, chipEnable, output, input, maskPort).flatten
  assert (polarizedPorts.distinct.size == polarizedPorts.size, "All port names must be unique")
}
object MacroPort {
  def parseJSON(json:Map[String, JsValue]): Option[MacroPort] = parseJSON(json, None, None)
  def parseJSON(json:Map[String, JsValue], width:Int, depth:Int): Option[MacroPort] = parseJSON(json, Some(width), Some(depth))
  def parseJSON(json:Map[String, JsValue], width:Option[Int], depth:Option[Int]): Option[MacroPort] = {
    val address = PolarizedPort.parseJSON(json, "address")
    val clock = PolarizedPort.parseJSON(json, "clock")
    if (address == None || clock == None) {
      return None
    }

    // TODO: validate based on family (e.g. 1rw must have a write enable, etc)
    val writeEnable = PolarizedPort.parseJSON(json, "write enable")
    val readEnable = PolarizedPort.parseJSON(json, "read enable")
    val chipEnable = PolarizedPort.parseJSON(json, "chip enable")

    val output = PolarizedPort.parseJSON(json, "output")
    val input = PolarizedPort.parseJSON(json, "input")

    val maskPort = PolarizedPort.parseJSON(json, "mask")
    val maskGran: Option[Int] = json.get("mask granularity") match {
      case Some(x:JsNumber) => Some(x.value.intValue)
      case _ => None
    }

    if (maskPort.isDefined != maskGran.isDefined) {
      return None
    }

    Some(MacroPort(width=width, depth=depth,
      address=address.get,
      clock=clock.get,

      writeEnable=writeEnable,
      readEnable=readEnable,
      chipEnable=chipEnable,

      output=output,
      input=input,

      maskPort=maskPort,
      maskGran=maskGran
    ))
  }
}

// Port polarity
trait PortPolarity
case object ActiveLow extends PortPolarity
case object ActiveHigh extends PortPolarity
case object NegativeEdge extends PortPolarity
case object PositiveEdge extends PortPolarity
object PortPolarity {
  implicit def toPortPolarity(s: String): PortPolarity = (s: @unchecked) match {
    case "active low" => ActiveLow
    case "active high" => ActiveHigh
    case "negative edge" => NegativeEdge
    case "positive edge" => PositiveEdge
  }
  implicit def toPortPolarity(s: Option[String]): Option[PortPolarity] =
    s map toPortPolarity

  implicit def toString(p: PortPolarity): String = {
    p match {
      case ActiveLow => "active low"
      case ActiveHigh => "active high"
      case NegativeEdge => "negative edge"
      case PositiveEdge => "positive edge"
    }
  }
}

object Utils {
  // Read a MDF file from a String.
  def readMDFFromString(str: String): Option[Seq[Macro]] = {
    Json.parse(str) match {
      // Make sure that the document is a list.
      case arr:JsArray => {
        val result: List[Option[Macro]] = arr.as[List[Map[String, JsValue]]] map { obj =>
          // Check the type of object.
          val objTypeStr: String = obj.get("type") match {
            case Some(x:JsString) => x.as[String]
            case _ => return None // error, no type found
          }
          objTypeStr match {
            case "filler cell" | "metal filler cell" => FillerMacroBase.parseJSON(obj)
            case "sram" => SRAMMacro.parseJSON(obj)
            case "sramcompiler" => SRAMCompiler.parseJSON(obj)
            case _ => None // skip unknown macro types
          }
        }
        // Remove all the Nones and convert back to Seq[Macro]
        Some(result.filter { x => x != None } map { x => x.get })
      }
      case _ => None
    }
  }

  // Read a MDF file from a path.
  def readMDFFromPath(path: Option[String]): Option[Seq[Macro]] = {
    path match {
      case None => None
      // Read file into string and parse
      case Some(p) => Utils.readMDFFromString(scala.io.Source.fromFile(p).mkString)
    }
  }

  // Write a MDF file to a String.
  def writeMDFToString(s: Seq[Macro]): String = {
    Json.prettyPrint(JsArray(s map (_.toJSON)))
  }

  // Write a MDF file from a path.
  // Returns true upon success.
  def writeMDFToPath(path: Option[String], s: Seq[Macro]): Boolean = {
    path match {
      case None => false
      // Read file into string and parse
      case Some(p: String) => {
        import java.io._
        val pw = new PrintWriter(new File(p))
        pw.write(writeMDFToString(s))
        val error = pw.checkError
        pw.close()
        !error
      }
    }
  }

  // Write a macro file to a String.
  def writeMacroToString(s: Macro): String = {
    Json.prettyPrint(s.toJSON)
  }

  // Write a Macro file from a path.
  // Returns true upon success.
  def writeMacroToPath(path: Option[String], s: Macro): Boolean = {
    path match {
      case None => false
      // Read file into string and parse
      case Some(p: String) => {
        import java.io._
        val pw = new PrintWriter(new File(p))
        pw.write(writeMacroToString(s))
        val error = pw.checkError
        pw.close()
        !error
      }
    }
  }
}

object ConfReader {
  import scala.util.matching.Regex._

  type ConfPort = (String, Boolean) // prefix (e.g. "RW0") and true if masked

  /** Rename ports like "read" to R0, "write" to W0, and "rw" to RW0, and
   * return a count of read, write, and readwrite ports. */
  def renamePorts(ports: Seq[String]): (Seq[ConfPort], Int, Int, Int) = {
    var readCount = 0
    var writeCount = 0
    var readWriteCount = 0
    (ports.map { _ match {
      case "read" => readCount += 1; (s"R${readCount - 1}", false)
      case "write" => writeCount += 1; (s"W${writeCount - 1}", false)
      case "mwrite" => writeCount += 1; (s"W${writeCount - 1}", true)
      case "rw" => readWriteCount += 1; (s"RW${readWriteCount - 1}", false)
      case "mrw" => readWriteCount += 1; (s"RW${readWriteCount - 1}", true)
    }}, readCount, writeCount, readWriteCount)
  }

  def generateFirrtlPort(port: ConfPort, width: Int, depth: Int, maskGran: Option[Int]): MacroPort = {
    val (prefix, masked) = port
    val isReadWriter = prefix.startsWith("RW")
    val isReader = prefix.startsWith("R") && !isReadWriter
    val isWriter = prefix.startsWith("W")
    val r = if (isReadWriter) "r" else ""
    val w = if (isReadWriter) "w" else ""
    MacroPort(
      address=PolarizedPort(s"${prefix}_addr", ActiveHigh),
      clock=PolarizedPort(s"${prefix}_clk", PositiveEdge),

      writeEnable=if (isReadWriter) Some(PolarizedPort(s"${prefix}_${w}mode", ActiveHigh)) else None,

      output=if (isReader || isReadWriter) Some(PolarizedPort(s"${prefix}_${w}data", ActiveHigh)) else None,
      input=if (isWriter || isReadWriter) Some(PolarizedPort(s"${prefix}_${r}data", ActiveHigh)) else None,

      maskPort=if (masked) Some(PolarizedPort(s"${prefix}_${w}mask", ActiveHigh)) else None,
      maskGran=if (masked) maskGran else None,

      width=Some(width), depth=Some(depth)
    )
  }

  /**
   * Read a conf line into a SRAMMacro, but returns an error string in Left
   * instead of throwing errors if the line is malformed.
   */
  def readSingleLineSafe(line: String): Either[String, SRAMMacro] = {
    val pattern = """name ([^\s]+) depth (\d+) width (\d+) ports ([a-z,]+)\s?(?:mask_gran (\d+))?""".r
    pattern.findFirstMatchIn(line) match {
      case Some(m: Match) => {
        val name: String = m group 1
        val depth: Int = (m group 2).toInt
        val width: Int = (m group 3).toInt
        val ports: Seq[String] = (m group 4) split ","
        val (firrtlPorts, readPortCount, writePortCount, readWritePortCount) = renamePorts(ports)
        val familyStr =
          (if (readPortCount > 0) s"${readPortCount}r" else "") +
          (if (writePortCount > 0) s"${writePortCount}w" else "") +
          (if (readWritePortCount > 0) s"${readWritePortCount}rw" else "")
        val maskGran: Option[Int] = Option(m group 5) map(_.toInt)
        Right(SRAMMacro(name=name,
          width=width,
          depth=depth,
          family=familyStr,
          ports=firrtlPorts map (generateFirrtlPort(_, width, depth, maskGran)),
          extraPorts=List()
        ))
      }
      case _ => Left("Input line did not match conf regex")
    }
  }

  /** Read a conf line into a SRAMMacro. */
  def readSingleLine(line: String): SRAMMacro = {
    readSingleLineSafe(line).right.get
  }

  /** Read the contents of the conf file into a seq of SRAMMacro. */
  def readFromString(contents: String): Seq[SRAMMacro] = {
    // Trim, remove empty lines, then pass to readSingleLine
    contents.split("\n").map(_.trim).filter(_ != "").map(readSingleLine(_))
  }
}
