//See LICENSE for license details.

package dessert
package examples
package testers

import chisel3.core._
import freechips.rocketchip.config.Parameters
import mini._

class Tile(tileParam: Parameters) extends ExtModule with TileBase {
  implicit val p = tileParam
  val io = IO(new TileIO)
  val clock = IO(Input(Clock()))
  val reset = IO(Input(Bool()))
}
