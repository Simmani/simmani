import os.path
import sys
import csv
import logging
import struct
from time import time
import numpy as np
from scipy.sparse import csr_matrix, hstack
from . import divide_csr
from .vcd import read_toggles_vcd

def read_toggles_csv(csv_filename):
    logging.info("CSV file: %s", csv_filename)
    assert os.path.isfile(csv_filename), "%s not found" % (csv_filename)
    indices = list()
    toggles = list()
    with open(csv_filename, "r") as _f:
        reader = csv.reader(_f)
        for i, line in enumerate(reader):
            if i == 0: # window
                window = int(line[0])
            elif i == 1: # cycles
                cycles = [int(x) for x in line]
            elif i == 2: # reset cycles
                reset_cycles = [int(x) for x in line]
            elif i == 3: # signals
                signals = line
            elif i == 4: # widths
                widths = np.array([int(x) for x in line])
            elif i == 5: # index pointers
                indptr = [int(x) for x in line]
            else: # index + toggle
                assert len(line) == 2
                indices.append(int(line[0]))
                toggles.append(int(line[1]))

    indptr = np.array(indptr, dtype=np.int64)
    indices = np.array(indices, dtype=np.int64)
    shape = len(signals), int((sum(cycles) - sum(reset_cycles) - 1) / window) + 1
    data = csr_matrix((toggles, indices, indptr), shape=shape)
    data = divide_csr(data, window * widths.reshape(-1, 1))

    return window, cycles, reset_cycles, signals, data, widths

def read_toggles_bin(bin_filename):
    logging.info("Binary file: %s", bin_filename)
    assert os.path.isfile(bin_filename), "%s not found" % (bin_filename)
    signals = list()
    indices = list()
    toggles = list()

    with open(bin_filename, "rb") as _f:
        window = struct.unpack("N", _f.read(8))[0]
        logging.debug("window: %d", window)

        cycles_len = struct.unpack("N", _f.read(8))[0]
        cycles = [x[0] for x in struct.iter_unpack("N", _f.read(8 * cycles_len))]

        reset_cycles_len = struct.unpack("N", _f.read(8))[0]
        reset_cycles = [x[0] for x in struct.iter_unpack("N", _f.read(8 * reset_cycles_len))]

        signals_len = struct.unpack("N", _f.read(8))[0]
        for _ in range(signals_len):
            signal_len = struct.unpack("N", _f.read(8))[0]
            signal = _f.read(signal_len).decode("utf-8")
            signals.append(signal)

        widths_len = struct.unpack("N", _f.read(8))[0]
        widths = [x[0] for x in struct.iter_unpack("N", _f.read(8 * widths_len))]

        assert len(signals) == len(widths)
        for signal, width in zip(signals, widths):
            logging.debug("signal: %s[%d]", signal, width)

        indptr_len = struct.unpack("N", _f.read(8))[0]
        indptr = [x[0] for x in struct.iter_unpack("N", _f.read(8 * indptr_len))]

        while True:
            data = _f.read(120000)
            if not data:
                break
            for index, toggle in struct.iter_unpack("NI", data):
                indices.append(index)
                toggles.append(toggle)

    widths = np.array(widths)
    indptr = np.array(indptr, dtype=np.int64)
    indices = np.array(indices, dtype=np.int64)
    shape = len(signals), int((sum(cycles) - sum(reset_cycles) - 1) / window) + 1
    data = csr_matrix((toggles, indices, indptr), shape=shape)
    data = divide_csr(data, window * widths.reshape(-1, 1))

    return window, cycles, reset_cycles, signals, data, widths

def read_toggles(toggle_file=None, vcd_files=None, window=1, signal_filter=None):
    """ Get signal toggles from toggle file or vcd """
    start_time = time()
    if toggle_file:
        (_window,
         vcd_cycle_list,
         reset_cycle_list,
         bus_signals,
         bus_toggles,
         bus_widths) = \
        read_toggles_csv(toggle_file) if toggle_file.endswith(".csv") else \
        read_toggles_bin(toggle_file)
        if signal_filter:
            _filter = np.array([s in signal_filter for s in bus_signals])
            bus_toggles = bus_toggles[_filter]
            bus_signals = np.array(bus_signals)[_filter]
            bus_widths = np.array(bus_widths)[_filter]
        assert window == _window
    elif vcd_files:
        vcd_cycle_list = list()
        reset_cycle_list = list()
        bus_signals = None
        for vcd_file in vcd_files:
            (vcd_cycles,
             reset_cycles,
             _bus_signals,
             _bus_toggles,
             _bus_widths) = read_toggles_vcd(
                 vcd_file, signal_filter=signal_filter, window=window)
            vcd_cycle_list.append(vcd_cycles)
            reset_cycle_list.append(reset_cycles)
            if bus_signals is None:
                bus_signals = _bus_signals
                bus_toggles = _bus_toggles
                bus_widths = _bus_widths
            else:
                assert all(x == y for x, y in zip(bus_signals, _bus_signals))
                assert all(x == y for x, y in zip(bus_widths, _bus_widths))
                bus_toggles = csr_matrix(hstack([bus_toggles, _bus_toggles]))
    end_time = time()
    logging.info("Toggle read time: %.2f s", end_time - start_time)

    # FIXME: filter from vcd_reader
    bus_signal_filter = [
        "_ext" not in bus_signal or "_reg" not in bus_signal for bus_signal in bus_signals]
    bus_signals = np.array(bus_signals)
    width_filter = bus_widths < (sys.maxsize if signal_filter else 96)
    width_filter &= np.array(bus_signal_filter) # FIMXE: remove
    logging.info("Remove %d wide signals:", np.count_nonzero(~width_filter))
    for signal in bus_signals[~width_filter]:
        logging.info("- %s", signal)
    bus_signals = bus_signals[width_filter]
    bus_toggles = bus_toggles[width_filter]
    bus_widths = bus_widths[width_filter]

    return vcd_cycle_list, reset_cycle_list, bus_signals, bus_toggles, bus_widths
