#!/usr/bin/env python3

# See LICENSE for license details.

import os.path
import sys
import csv
import argparse
import logging
from time import time
import numpy as np
from utils import read_modules, translate_indices
from utils.toggle import read_toggles
from utils.power import read_power_files
from utils.data import plot_power, dump_power_bars, plot_data, store_data
from model.regression import get_terms

def parse_args(argv):
    parser = argparse.ArgumentParser(description='Power Model Test')
    parser.add_argument("-t", "--toggle", dest="toggle", type=str,
                        help='toggle file name')
    parser.add_argument("-v", "--vcd", dest="vcd", type=str,
                        help='vcd file name')
    parser.add_argument("-o", "--out", dest="out", type=str,
                        help='power out file name', required=True)
    parser.add_argument("-m", "--model", dest="model", type=str,
                        help='power model file name', required=True)
    parser.add_argument("-d", "--dir", dest="dir", type=str,
                        help='output directory', default=os.path.curdir)
    parser.add_argument("-w", "--window", dest="window", type=int,
                        help="windows size (in cycle)", default=128)
    parser.add_argument("--modules", dest="modules", type=str,
                        help="module hierarchy")
    parser.add_argument("--plot-data", dest="plot_data",
                        help="plot data graphs?",
                        action="store_true", default=False)

    args, _ = parser.parse_known_args(argv)
    assert args.vcd or args.toggle
    os.makedirs(args.dir, exist_ok=True)
    benchmark = os.path.splitext(os.path.basename(
        args.vcd if args.vcd else args.toggle))[0]
    return args, benchmark

def load_model(filename):
    logging.info("Model file: %s", filename)
    assert os.path.isfile(filename), "%s not found" % (filename)
    terms = list()
    models = list()
    def _int(lst):
        return [int(x) for x in lst]
    def _float(lst):
        return [float(x) for x in lst]
    with open(filename, "r") as _f:
        reader = csv.reader(_f)
        for line in reader:
            if line[0] == 'signals':
                signals = line[1:]
            elif line[0] == 'widths':
                widths = _int(line[1:])
            elif line[0] == 'modules':
                modules = line[1:]
            else:
                assert len(line) == len(modules) + 1
                if line[0] != 'const':
                    term = [signals.index(s) for s in line[0].split('*')]
                    terms.append(term)
                models.append(_float(line[1:]))
    models = np.array(models).T
    assert len(signals) == len(widths)
    assert models.shape == (len(modules), len(terms)+1)
    return signals, widths, modules, terms, models

MODULES = []
Ys = []
Y_hats = []
SCORES = []

def test_and_plot(module, A, X, y, benchmark, dirname, cycle, window):
    y_hat = A.dot(X)
    sse = np.sum((y - y_hat) ** 2)
    rmse = np.sqrt(sse / len(y)) / y.mean()
    avge = abs(y_hat.mean() - y.mean()) / y.mean()
    MODULES.append(module)
    Ys.append(y)
    Y_hats.append(y_hat)
    SCORES.append((rmse, avge))

    plot_dirname = os.path.join(dirname, "power", module)
    os.makedirs(plot_dirname, exist_ok=True)
    png_filename = os.path.join(plot_dirname, "test-%s.png" % (benchmark))
    plot_power(png_filename, [y, y_hat], cycle, window)

def main(argv):
    args, benchmark = parse_args(argv)

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO
    )

    signals, _, _modules, _terms, models = load_model(args.model)
    module_filter, misc_module, children, labels = read_modules(args.modules)

    vcd_cycle_list, reset_cycle_list, bus_signals, toggles, widths = \
        read_toggles(args.toggle, [args.vcd], args.window, set(signals))
    assert len(bus_signals) == len(signals), "%s != %s" % (
        str(bus_signals), str(signals))
    terms = translate_indices(signals, bus_signals, _terms)
    modules, powers = read_power_files(
        [args.out], args.window, vcd_cycle_list, reset_cycle_list, module_filter)

    toggles = toggles.A

    logging.info("Cycles: %d", sum(vcd_cycle_list))
    logging.info("Reset Cycles: %d", sum(reset_cycle_list))
    logging.info("Signals: %d", len(bus_signals))
    logging.info("Toggles: %s", str(toggles.shape))
    total_cycles = sum(vcd_cycle_list) - sum(reset_cycle_list)
    logging.info("Average Power:")
    for module, power in zip(modules, powers):
        logging.info("- %s: %.2f", module, power.mean())

    # Dump toggles
    signal_idxs = translate_indices(signals, bus_signals, [(i,) for i in range(len(signals))])
    np.savetxt(os.path.join(args.dir, 'test-toggle-%s.csv' % benchmark),
               get_terms((toggles * (args.window * widths.reshape(-1, 1))).T, signal_idxs),
               fmt="%d", delimiter=',', header=','.join(signals), comments='')

    # Contruct matrix
    signals = bus_signals.tolist()
    A0 = toggles.T
    ones = np.ones((A0.shape[0], 1), dtype=A0.dtype)
    A = np.append(ones, get_terms(A0, terms), axis=1)
    ys = list(powers)

    # Power plots
    test_and_plot(
        modules[0], A, models[0], ys[0],
        benchmark, args.dir, total_cycles, args.window)

    if children:
        label_ys = dict()
        for module, y in zip(modules[1:], ys[1:]):
            assert module in children
            idxs = [modules.index(child) for child in children[module]]
            label = labels[module]
            if label not in label_ys:
                label_ys[label] = 0.0
            y -= np.array(ys)[idxs].sum(axis=0)
            label_ys[label] += y

        for module, model in zip(_modules[1:-1], models[1:-1]):
            test_and_plot(
                module, A, model, label_ys[module],
                benchmark, args.dir, total_cycles, args.window)

    if misc_module:
        y = ys[0] - np.sum(ys[1:], axis=0)
        test_and_plot(
            misc_module, A, models[-1], y,
            benchmark, args.dir, total_cycles, args.window)

    png_filename = os.path.join(args.dir, "test-%s.png" % benchmark)
    y = np.sum(Ys[1:], axis=0) if children else Ys[0]
    y_hat = np.sum(Y_hats[1:], axis=0) if children else Y_hats[0]
    plot_power(png_filename, [y, y_hat], total_cycles, args.window, benchmark)
    dump_power_bars(args.dir, benchmark, MODULES, Ys, Y_hats)

    if args.plot_data:
        start_time = time()
        data_dirname = os.path.join(args.dir, "test-data-%s" % benchmark)
        filters = np.array([abs(X[1:]) > 0.0 for X in models])
        plot_data(data_dirname, signals, terms, A.T, MODULES, Ys, filters)
        end_time = time()
        logging.info("Data plot time: %.2f s", end_time - start_time)

    header = '\n'.join([
        ','.join(['window', str(args.window)]),
        ','.join(MODULES)
    ])

    # Dump power traces
    power_trace = os.path.join(args.dir, "test-power-%s.csv" % benchmark)
    np.savetxt(power_trace, np.array(Ys).T, fmt='%f', delimiter=',', comments='', header=header)

    predict_trace = os.path.join(args.dir, "test-predict-%s.csv" % benchmark)
    np.savetxt(predict_trace, np.array(Y_hats).T, fmt='%f', delimiter=',', comments='', header=header)

    stats_filename = os.path.join(args.dir, "test-stats-%s.csv" % benchmark)
    logging.info("Statistics file: %s", stats_filename)
    with open(stats_filename, 'w') as _f:
        writer = csv.writer(_f)
        writer.writerow(['module', 'NRMSE (%)', 'AVGE (%)'])
        for module, y, y_hat, (rmse, avge) in zip(MODULES, Ys, Y_hats, SCORES):
            writer.writerow([module, "%.2f" % (100 * rmse), "%.2f" % (100 * avge)])
            logging.info("[%s] y = %.2f, y_hat = %.2f, NRMSE = %f %%, AVGE %f %%",
                         module, y.mean(), y_hat.mean(), 100 * rmse, 100 * avge)

if __name__ == "__main__":
    main(sys.argv[1:])
