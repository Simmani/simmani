#!/usr/bin/env python3

# See LICENSE for license details.

import os
import sys
import csv
import argparse
import logging
from operator import add
from functools import reduce
import numpy as np
from utils import read_modules
from utils.power import read_power_files
from utils.data import plot_power, dump_power_bars
from analyze_samples import load_power_trace

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--power", dest="power", type=str,
                        help='power trace from FPGA', nargs='+')
    parser.add_argument("-o", "--out", dest="out", type=str,
                        help='power data file from model test', nargs='+')
    parser.add_argument("-d", "--dir", dest="dir", type=str,
                        help='output directory', default=os.path.curdir)
    parser.add_argument("--modules", dest="modules", type=str,
                        help="module hierarchy")
    parser.add_argument("--skip", dest="skip", type=int,
                        help="# of cycles to skip")
    args, _ = parser.parse_known_args(argv)

    assert not args.out or len(args.power) == len(args.out)
    if not os.path.isdir(args.dir):
        os.makedirs(args.dir)
    return args

def plot_trace(benchmark, args, trace, out=None):
    window, _modules, ps = load_power_trace(trace)
    p = reduce(add, ps[1:]) if len(ps) > 1 else ps[0]

    if out is None:
        # Power Plot
        y = None
        ys = None
        total_cycles = len(p) * window
    else:
        # Read module hierarchy
        module_filter, misc_module, children, labels = read_modules(args.modules)
        modules, powers = read_power_files([out], window, module_filter=module_filter)

        assert len(p) - len(powers[0]) < 3, "%d != %d" % (len(p), len(powers[0]))
        p_size = min(len(p), len(powers[0]))
        total_cycles = p_size * window

        ys = [powers[0]]
        if children:
            label_ys = dict()
            for module, power in zip(modules[1:], powers[1:]):
                assert module in children
                idxs = [modules.index(child) for child in children[module]]
                label = labels[module]
                if label not in label_ys:
                    label_ys[label] = 0.0
                power -= np.array(powers)[idxs].sum(axis=0)
                label_ys[label] += power

            for module in _modules[1:-1]:
                ys.append(label_ys[module])

        if misc_module:
            ys.append(ys[0] - np.sum(ys[1:], axis=0))

        y = reduce(add, ys[1:]) if len(ys) > 1 else ys[0]

        assert len(ps) == len(ys)

    # Power Plot
    if args.skip:
        start_idx = (args.skip // window)
        total_cycles -= start_idx * window
        y = y[start_idx:] if y is not None else None
        p = p[start_idx:]
        ys = [y[start_idx:] for y in ys] if ys is not None else None
        ps = [p[start_idx:] for p in ps]
    png_filename = os.path.join(args.dir, "%s-trace.png" % benchmark)
    plot_power(png_filename, [y, p], total_cycles, window, benchmark)

    for i, (module, p) in enumerate(zip(_modules, ps)):
        y = ys[i] if ys is not None else None
        png_filename = os.path.join(args.dir, module, benchmark + ".png")
        plot_power(png_filename, [y, p], total_cycles, window, module)

    dump_power_bars(args.dir, benchmark, _modules, ys, ps)

    if args.out is None:
        return None, None

    stat_filename = os.path.join(args.dir, "%s-stats.csv" % benchmark)
    logging.info("Statistics file: %s", stat_filename)
    with open(stat_filename, "w") as _f:
        writer = csv.writer(_f)
        writer.writerow(["Module", "NRMSE (%)", "AVGE (%)"])
        for i, (module, p, y) in enumerate(zip(_modules, ps, ys)):
            sse = np.sum((p[:p_size] - y[:p_size]) ** 2)
            rmse = np.sqrt(sse / p_size) / y.mean()
            avge = abs((y.mean() - p.mean()) / y.mean())
            writer.writerow([module, "%.2f" % (100 * rmse), "%.2f" % (100 * avge)])
            if i == 0:
                total_rmse, total_avge = rmse, avge

    return total_rmse, total_avge

def main(argv):
    args = parse_args(argv)

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO
    )

    benchmarks = [
        os.path.splitext(os.path.basename(t))[0]
        for t in args.power
    ]

    rmses, avges = zip(*[
        plot_trace(benchmark, args, trace,
                   args.out[i] if args.out else None)
        for i, (benchmark, trace)
        in enumerate(zip(benchmarks, args.power))
    ])

    if args.out:
        total_stats_csv = os.path.join(args.dir, "total-stats.csv")
        logging.info("Total stat file: %s", total_stats_csv)
        with open(total_stats_csv, "w") as _f:
            writer = csv.writer(_f)
            writer.writerow(["Benchmark"] + benchmarks)
            writer.writerow(["RMSE(%)"] + ["%.2f" % (100 * e) for e in rmses])
            writer.writerow(["AVGE(%)"] + ["%.2f" % (100 * e) for e in avges])

if __name__ == "__main__":
    main(sys.argv[1:])
