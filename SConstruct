import os
import datetime
from operator import add
from functools import reduce

EXAMPLES = ['GCD', 'Stack', 'Risc', 'RiscSRAM']
MINI = ['Tile']

def _suffixes(env):
    return [
        os.path.basename(loadmem).replace('.hex', '')
        for loadmem in env['LOADMEMS']
    ] if env['LOADMEMS'] else [None, 5000]

def compile_rtl_v(env):
    # Compile FIRRTL first
    def publish(target, source, env):
        with open(target[0].name, 'w') as _f:
            _f.write(str(datetime.datetime.now()))

    env.SBT('publish', [],
            SBT_CWD='firrtl',
            SBT_CMD='publishLocal',
            SBT_ACTIONS=[publish])
    env.Precious('publish')
    env.NoClean('publish')

    targets = env.SBT(
        [
            os.path.join(env['GEN_DIR'], env['DESIGN'] + '.v'),
            os.path.join(env['GEN_DIR'], env['DESIGN'] + '.macros.v'),
        ] + [
            os.path.join(env['GEN_DIR'], env['DESIGN'] + '.tester%s.v' % (
                '-' + str(suffix) if suffix is not None else ''))
            for suffix in _suffixes(env)
        ], 
        ['publish', os.path.abspath('macro.45nm.json')],
        SBT_CMD='"%s"' % ' '.join([
            "runMain",
            'dessert.examples.Generator',
            env['GEN_DIR'],
            env['PROJECT'],
            env['DESIGN'],
            '+macro=%s' % os.path.abspath("macro.45nm.json")
        ]))

    env.SideEffect('#sbt', targets)
    env.Alias('rtl-v', targets)

    return targets 

def _run_testers_examples(env, backend, suffix=None):
    out_dir = env['OUT_DIR']
    name = env['DESIGN']
    if suffix:
        name += '-' + str(suffix)
    emul = os.path.join(out_dir, name)
    out = emul + '.out'
    vcd = os.path.join(out_dir, name + '.vcd')
    tgts = env.SIM([out, vcd], emul)
    env.Precious(tgts)
    env.Alias('run-testers', tgts)
    return vcd

def run_testers(env):
    return [
        _run_testers_examples(env, 'rtl', suffix)
        for suffix in _suffixes(env)
    ]

def _get_submodule_files(submodule):
    return reduce(add, [
        [
            os.path.join(dirpath, f)
            for f in filenames if f.endswith('.scala')
        ]
        for dirpath, _, filenames in os.walk(os.path.join(
            submodule, 'src', 'main', 'scala'))
    ], [])

def _scala_srcs(target, source, env):
    if target[0].name == 'publish':
        return target, source + _get_submodule_files('firrtl')

    extra_srcs = ['publish']

    submodules = [
        os.path.curdir,
        os.path.join('designs', 'riscv-mini'),
    ]

    return target, source + ['publish'] + reduce(add, [
        _get_submodule_files(submodule) for submodule in submodules
    ], [])

def _sbt_actions(target, source, env, for_signature):
    return [' '.join(
        (['cd', env['SBT_CWD'], '&&'] if 'SBT_CWD' in env else []) + \
        [env['SBT'], env['SBT_FLAGS'], env['SBT_CMD']]
    )] + (env['SBT_ACTIONS'] if 'SBT_ACTIONS' in env else [])

def _sim_actions(target, source, env, for_signature):
    disasm = '&>'
    cmd = ' '.join([
        'cd', source[0].dir.abspath, '&&',
        './' + source[0].name
    ] + [
        '+vcdfile=' + w.abspath for w in target
        if os.path.splitext(w.name)[1] == '.vcd'
    ] + [
        '+vcdplusfile=' + w.abspath for w in target
        if os.path.splitext(w.name)[1] == '.vpd'
    ] + [
        '+loadmem=' + m.abspath for m in source
        if os.path.splitext(m.name)[1] == '.hex'
    ] + reduce(add, [
        ['&>', o.abspath] for o in target
        if os.path.splitext(o.name)[1] == '.out'
    ], []))

    def check(target, source, env):
        out = [
            o for o in target
            if os.path.splitext(o.name)[1] == '.out'
        ]
        lines = [
            l for l in out[0].get_text_contents().splitlines()
            if 'Fatal' in l or 'FAIL' in l
        ]
        for _l in lines:
            logging.error(_l)
        return '\n'.join(lines)

    dirs = [os.path.dirname(t.abspath) for t in target]
    return [
        Mkdir(d) for d in dirs if not os.path.isdir(d)
    ] + [cmd, check]

for design in EXAMPLES:
    AddOption('--' + design,
              dest=design,
              action='store_true',
              default=False,
              help='build %s' % design)
AddOption('--mini',
          dest='mini',
          action='store_true',
          default=False,
          help='build riscv-mini')

config_file = os.path.join('configs',
    reduce(lambda x, y: y + '.py' if GetOption(y) else x, EXAMPLES, 'Mini.py'))

variables = Variables(config_file, ARGUMENTS)
variables.AddVariables(
    EnumVariable('PROJECT', 'Target project name', 'dessert.examples',
                 allowed_values=['dessert.examples', 'mini']),
    EnumVariable('DESIGN', 'Target design name', 'GCD',
                 allowed_values=EXAMPLES + MINI),
    ('LOADMEMS', 'Hex file to run (riscv-mini only)', []),
    ('WINDOWS', 'Window sizes for signal clustering', [64, 128, 256]),
    ('WINDOW', 'Window size for power-model regression', 256))

env = Environment(
    variables=variables,
    ENV=os.environ,
    SBT='sbt',
    SBT_FLAGS=' '.join([
        '-ivy', os.path.join(os.path.abspath(os.path.curdir), '.ivy2'),
        '-J-Xmx16G',
        '-J-Xss8M',
        '-J-XX:MaxMetaspaceSize=512M',
        '++2.12.4'
    ]),
    VERILATOR='verilator --cc --exe',
    VCS='vcs -full64',
    RISCV=os.environ.get('RISCV', '/home/centos/riscv'),
    CLOCK_PERIOD=1.0
)

env.SetDefault(
    GEN_DIR=os.path.abspath(os.path.join('generated-src', env['DESIGN'])),
    OUT_DIR=os.path.abspath(os.path.join('output', env['DESIGN'])))

env.Append(
    BUILDERS={
        'SBT': Builder(generator=_sbt_actions, emitter=_scala_srcs),
        'SIM': Builder(generator=_sim_actions),
    },
)

num_cpus = 0
with open('/proc/cpuinfo', 'r') as _f:
    for line in _f:
        if line[:9] == 'processor':
            num_cpus += 1
print("# of processors: %d" % num_cpus)

if GetOption('num_jobs') < 8:
    SetOption('num_jobs', max(num_cpus-4, 8))
print("# of job: %d" % GetOption('num_jobs'))

targets = compile_rtl_v(env)
rtl_v, macro, tester_v = targets[0], targets[1], targets[2:]

# Compile testers
env.SConscript(
    os.path.join('src', 'main', 'verilog', 'SConscript'),
    exports=['env', 'rtl_v', 'macro', 'tester_v'])

run_testers(env)
