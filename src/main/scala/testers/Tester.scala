package dessert
package examples
package testers

case class TestParam(num: Int, seed: Int)

abstract class Tester(p: TestParam) extends chisel3.testers.BasicTester {
  val testNum = p.num
  val rnd = new scala.util.Random(p.seed)
}
