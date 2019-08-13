import os
import logging
from time import time
import numpy as np
from . import average_rows

def read_power_report(filename):
    """
    Read a PrimeTime-PX power report to return average power
    """
    logging.info("Power Report: %s", filename)
    assert os.path.isfile(filename), "%s not found" % (filename)
    modules = list()
    total_powers = dict() # Module -> Total Power
    extra_powers = dict() # Module -> Int, Switch, Leak Power
    with open(filename) as _f:
        scale = 1.0 # 1W
        class StateType: head, body = range(2)
        state = StateType.head
        for line in _f:
            tokens = line.split()
            if state == StateType.head:
                if tokens:
                    if tokens[0] == 'Hierarchy':
                        assert tokens[-1] == '%'
                        num_fields = len(tokens)
                        state = StateType.body
                    elif ' '.join(tokens[0:2]) == 'Dynamic Power Units':
                        assert tokens[3] == "="
                        if tokens[5] == "W":
                            scale = float(tokens[4])
                        else:
                            assert False, "unknown unit: %s" % (tokens[5])
                    elif ' '.join(tokens[0:2]) == 'Leakage Power Units':
                        assert tokens[3] == "="
                        if tokens[5] == "W":
                            assert scale == float(tokens[4])
                        else:
                            assert False, "unknown unit: %s" % (tokens[5])
            elif state == StateType.body:
                if len(tokens) >= num_fields:
                    instance = tokens[0]
                    if len(tokens) == num_fields:
                        paths = dict()
                        level = 0
                        offset = 1
                    else:
                        level = int((len(line) - len(line.lstrip(' '))) / 2)
                        offset = 2
                    paths[level] = instance
                    module = ".".join([paths[i] for i in range(level)] + [instance])
                    def to_float(pwr):
                        return 0.0 if pwr == 'N/A' else float(pwr)
                    percent = tokens[-1]
                    total_power = to_float(tokens[-2])
                    extra_power = [to_float(x) for x in tokens[offset:offset+3]]
                    logging.debug(
                        "[%s power] total: %.2f, percent: %.2f, "
                        "int: %.2f, swich: %.2f, leak: %.2f",
                        module, total_power, percent,
                        extra_power[0], extra_power[1], extra_power[2])
                    if 'clk_gate' not in module and '_ext' not in module:
                        modules.append(module)
                        total_powers[module] = total_power
                        extra_powers[module] = extra_power
            else:
                assert False, "unknown state: %d" % (state)

    return modules, total_powers, extra_powers


def read_power_out(filename, module_filter=None):
    """
    Read PrimeTime-PX output_format to return cycle-by-cycle power
    """
    logging.info("Power Waveform: %s", filename)
    assert os.path.isfile(filename), "%s not found" % (filename)
    time = 0
    cycle = 0
    modules = list()
    powers = list()
    time_scale = 1.0
    hier_delim = '.'

    lookup = dict()
    energy = list()
    last_power = list()

    class PowerState: reset, skip, init, run = range(4)
    power_state = PowerState.reset
    updated, allzero = False, False

    def _power_update():
        pwr_cycles = max([len(p) for p in powers])
        for i, p in enumerate(powers):
            pwr = p[-1] if p else last_power[i]
            if not allzero:
                p.extend([pwr] * (pwr_cycles - len(p)))
            elif pwr_cycles == len(p):
                del p[-1]

    with open(filename) as _f:
        for line in _f:
            tokens = line.split()
            if not tokens:
                pass
            elif tokens[0] == ';':
                # Header => skip
                pass
            elif tokens[0] == '.time_resolution':
                # Time Resolustion w.r.t. ns
                time_scale = float(tokens[1]) # in ns
            elif tokens[0] == '.hier_separator':
                # Hierarchy Separator, likely /
                hier_delim = tokens[1]

            elif len(tokens) == 4 and tokens[0] == '.index':
                # Module Declaration
                assert tokens[-1] == "Pc"
                assert tokens[1][0:3] == "Pc(" and tokens[1][-1] == ")"
                module = tokens[1][3:-1].replace(hier_delim, '.')
                if (module_filter and module in module_filter) or \
                   (not module_filter and 'clk_gate' not in module and \
                    'pp_root' not in module and '_ext' not in module):
                    lookup[tokens[2]] = len(modules)
                    modules.append(module)
                    powers.append(list())
                    last_power.append(0.0)
                    energy.append(0.0)

            elif len(tokens) == 3 and tokens[0] == 'module:':
                # Module Declarating
                module = tokens[1]
                if (module_filter and module in module_filter) or \
                   (not module_filter and 'clk_gate' not in module and \
                    'pp_root' not in module and '_ext' not in module):
                    lookup[tokens[2]] = len(modules)
                    modules.append(module)
                    powers.append(list())
                    last_power.append(0.0)
                    energy.append(0.0)

            elif len(tokens) == 1:
                # This is a cycle-accurate power trace
                prev_cycle = cycle
                # FIXME: PrimeTime doesn't correctly dump odd cycles...
                # Is it a bug of PrimeTime?
                if power_state == PowerState.reset:
                    if int(tokens[0]) > 0:
                        reset_latency = int(tokens[0]) - prev_cycle
                        cycle = prev_cycle + reset_latency
                        power_state = PowerState.skip
                elif power_state == PowerState.skip:
                    cycle = int(tokens[0])
                    power_state = PowerState.run
                elif power_state == PowerState.init:
                    assert not updated
                    assert cycle <= int(tokens[0])
                    power_state = PowerState.run
                elif power_state == PowerState.run:
                    assert updated
                    _power_update()
                    if allzero:
                        prev_cycle -= 1
                        cycle = prev_cycle + reset_latency
                        power_state = PowerState.init
                    else:
                        cycle = prev_cycle + 1
                else:
                    assert False
                pwr_cycles = max([len(p) for p in powers])
                logging.debug("state: %d, token: %s, cycle: %d, prev_cycle: %d, reset_cycle: %d, pwr_cycle: %d",
                              power_state, tokens[0], cycle, prev_cycle, prev_cycle - pwr_cycles, pwr_cycles)
                updated = False
                allzero = True
            elif len(tokens) == 2:
                # Module Power
                idx = tokens[0]
                pwr = float(tokens[1]) * 1e3 # W -> mW
                if idx in lookup:
                    # This is a cycle-accurate power trace
                    if power_state == PowerState.run:
                        if cycle > prev_cycle:
                            powers[lookup[idx]].append(pwr)
                        else:
                            last_power[lookup[idx]] = pwr
                    allzero &= pwr < 1e-13
                    updated = True

    if power_state == PowerState.run:
        _power_update()
        if allzero:
            cycle -= 1

    powers = np.array(powers)
    reset_cycles = cycle - powers.shape[1]
    logging.debug("Inferred Reset Cycles: %d", reset_cycles)
    assert powers.shape[0] == len(modules) and powers.shape[1] < cycle, \
        "%s" % str(powers.shape)
    return cycle, reset_cycles, modules, powers

def read_power_files(out_files, window, vcd_cycle_list=None, reset_cycle_list=None, module_filter=None):
    """
    Read multiple power out files
    """
    start_time = time()
    assert vcd_cycle_list is None or len(vcd_cycle_list) == len(out_files)
    modules = None
    for i, out_file in enumerate(out_files):
        pwr_cycles, reset_cycles, _modules, _powers = read_power_out(out_file, module_filter)
        logging.debug("%s => cycles: %d, reset cycles: %d", out_file, pwr_cycles, reset_cycles)
        vcd_cycles = vcd_cycle_list[i] if vcd_cycle_list is not None else -1
        if reset_cycle_list is not None:
            assert reset_cycle_list[i] == reset_cycles, \
                "%d != %d" % (reset_cycle_list[i], reset_cycles)
            vcd_cycles -= reset_cycles
            pwr_cycles -= reset_cycles
        assert vcd_cycles < 0 or pwr_cycles >= vcd_cycles, \
            "%d < %d" % (pwr_cycles, vcd_cycles)
        assert vcd_cycles < 0 or pwr_cycles - vcd_cycles < 10, \
            "pwr_cycles - vcd_cycles = %d" % (pwr_cycles - vcd_cycles)
        #_powers = average_rows(_powers[:, :vcd_cycles], window)
        _powers = _powers[:, :vcd_cycles]
        if not modules:
            modules = _modules
            powers = _powers
        else:
            assert all(x == y for x, y in zip(modules, _modules))
            powers = np.append(powers, _powers, axis=1)
    end_time = time()
    logging.info("Power read time: %.2f s", end_time - start_time)

    return modules, average_rows(powers, window)
