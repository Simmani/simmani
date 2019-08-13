import os.path
import logging
from collections import deque
import numpy as np
from scipy.sparse import csr_matrix
from . import divide_csr

def read_toggles_vcd(vcd_filename, signal_filter=None, clock=1000, window=1):
    logging.info("VCD file: %s, Window: %d", vcd_filename, window)
    assert os.path.isfile(vcd_filename), "%s not found" % (vcd_filename)
    cycle = 0
    reset_cycle = 0
    bus_signals = list()
    bus_toggles = list()
    bus_indices = list()
    time = -1
    path = list()
    symbols = dict() # symbol -> idx
    widths = list()
    clock_value = None
    reset_value = None
    is_prefix = True
    with open(vcd_filename, "r") as _f:
        for line in _f:
            tokens = line.split()
            if not tokens:
                pass
            elif tokens[0][0] == "$":
                ######################
                # Decode Definitions #
                ######################
                if tokens[0] == "$scope":
                    assert tokens[1] == "module"
                    assert tokens[3] == "$end"
                    # module instance
                    path.append(tokens[2])
                    if is_prefix:
                        prefix = '.'.join(path) + '.'
                    is_prefix = True
                elif tokens[0] == "$upscope":
                    # move up to the upper module instance
                    path = path[:-1]
                elif tokens[0] == "$var":
                    is_prefix = False
                    # signal definition """
                    width = int(tokens[2])
                    symbol = tokens[3]
                    signal = ("%s.%s" % (".".join(path), tokens[4])).replace(prefix, "")
                    if signal == "clock":
                        clock_symbol = symbol
                        clock_value = '0'
                    elif signal == "reset":
                        reset_symbol = symbol
                    elif ("clock" in signal or "reset" in signal
                          or "_clk" in signal or "_rst" in signal
                          or "initvar" in signal or "_RAND" in signal
                          or "_GEN_" in signal): # FIXME: due to circuit mismatch
                        pass
                    elif signal_filter and signal not in signal_filter:
                        pass
                    elif symbol not in symbols:
                        symbols[symbol] = len(bus_signals)
                        widths.append(width)
                        bus_signals.append(signal)
                        bus_toggles.append(deque())
                        bus_indices.append(deque())
                elif tokens[0] == "$enddefinitions":
                    # no more variable definitions """
                    has_toggled = [False] * len(bus_signals)
                    cur_toggles = [0] * len(bus_signals)
                    cur_values = [0] * len(bus_signals)
                    prev_values = [0] * len(bus_signals)
                    path = list()

            elif tokens[0][0] == '#':
                # simulation time
                time = int(tokens[0][1:])

                ##############
                # Clock Tick #
                ##############
                if cycle > 0 and clock_value == '1':
                    if reset_value == '1':
                        reset_cycle += 1
                    # update toggles
                    for i, _t in enumerate(has_toggled):
                        if _t:
                            width = widths[i]
                            value = cur_values[i]
                            bus_diff = bin(value ^ prev_values[i]).count('1')
                            cur_toggles[i] += bus_diff
                            prev_values[i] = value
                            has_toggled[i] = False

                    if reset_value == '0' and ((cycle - reset_cycle) % window == 0):
                        idx = (cycle - reset_cycle) / window - 1
                        for i, (ids, ts, width) in enumerate(
                                zip(bus_indices, bus_toggles, widths)):
                            if cur_toggles[i] > 0:
                                ids.append(idx)
                                ts.append(cur_toggles[i])
                                # ts.append(float(cur_toggles[i]) / (window * width))
                                cur_toggles[i] = 0
            elif time >= 0 and tokens:
                #################
                # Update Values #
                #################
                if len(tokens) == 2:
                    assert tokens[0][0] == 'b'
                    value = tokens[0][1:]
                    symbol = tokens[1]
                elif len(tokens) == 1:
                    value = tokens[0][0]
                    symbol = tokens[0][1:]
                #assert cycle == 0 or time % clock == 0 or \
                #  symbol == clock_symbol or symbol == reset_symbol, \
                #  "time: %d, clock: %d, symbol: %s" % (time, clock, symbol)
                if symbol == clock_symbol:
                    clock_value = value
                    if time > 0 and clock_value == '1':
                        # clock tick
                        cycle += 1
                if symbol == reset_symbol:
                    reset_value = value
                elif cycle > 0 and clock_value == '1' and symbol in symbols:
                    # RTL signals tick at clock pos edges
                    idx = symbols[symbol]
                    try:
                        cur_values[idx] = int(value, 2)
                    except ValueError:
                        cur_values[idx] = int(value.replace('x', '0'), 2)
                    has_toggled[idx] = True

    # Leftovers
    tail = (cycle - reset_cycle) % window
    if tail != 0:
        idx = (cycle - reset_cycle - 1) / window
        for i, (ids, ts, width) in enumerate(zip(bus_indices, bus_toggles, widths)):
            if cur_toggles[i] > 0:
                ids.append(idx)
                ts.append(cur_toggles[i])
                # ts.append(float(cur_toggles[i]) / (width * tail))
                cur_toggles[i] = 0

    indptr = [0]
    for bus_index in bus_indices:
        indptr.append(indptr[-1] + len(bus_index))

    indices = list()
    toggles = list()
    for bus_index in bus_indices:
        indices.extend(bus_index)
    for bus_toggle in bus_toggles:
        toggles.extend(bus_toggle)

    widths = np.array(widths)
    indptr = np.array(indptr, dtype=np.int64)
    indices = np.array(indices, dtype=np.int64)
    shape = len(bus_signals), int((cycle - reset_cycle - 1) / window) + 1
    data = csr_matrix((toggles, indices, indptr), shape=shape)
    data = divide_csr(data, window * widths.reshape(-1, 1))

    return cycle, reset_cycle, bus_signals, data, widths
