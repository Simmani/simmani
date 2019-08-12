ThisBuild / scalaVersion := "2.12.4"
ThisBuild / crossScalaVersions := Seq("2.12.4", "2.11.12")
ThisBuild / scalacOptions ++= Seq("-deprecation","-unchecked","-Xsource:2.11")
ThisBuild / libraryDependencies ++= Seq(
  "org.scalatest" %% "scalatest" % "3.0.1" % Test,
  "com.typesafe.play" %% "play-json" % "2.6.2",
  "edu.berkeley.cs" %% "chisel3" % "3.1.0"
)

lazy val mini = (project in file("designs/riscv-mini"))
lazy val root = (project in file("."))
  .dependsOn(mini % "compile->compile;compile->test")
