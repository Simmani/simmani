import os

PROJECT="mini"
DESIGN="Tile"
WINDOW=120
WINDOWS=[4, 6, 8, 10, 12]
SIMMANI_ARGS=[
   "--module=" + os.path.abspath(os.path.join(
       "src", "main", "resources", "mini-modules.csv"))
]
HAMMER_DESIGN_CONFIG=[
    os.path.abspath(os.path.join('tools', 'hammer-configs', 'mini.json'))
]
assert os.path.isfile(HAMMER_DESIGN_CONFIG[0])

_loadmem_dir=os.path.join(
    "designs", "riscv-mini", "src", "test", "resources")
LOADMEMS=[
    os.path.abspath(os.path.join(_loadmem_dir, x))
    for x in os.listdir(_loadmem_dir)
    if x.endswith(".hex")
]
