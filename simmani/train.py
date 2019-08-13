#!/usr/bin/env python3

# See LICENSE for license details.

import os.path
import sys
import csv
import argparse
import logging
import warnings
from time import time
import numpy as np
from utils import read_modules
from utils.toggle import read_toggles
from utils.power import read_power_files
from utils.data import plot_power, dump_power_bars, plot_data, store_data
from model.regression import polynomial_regression, get_terms

def parse_args(argv):
    parser = argparse.ArgumentParser(description='Power Model Training')
    parser.add_argument("-s", "--signals", dest="signals", type=str,
                        help='cache file from signal clustering',
                        required=True)
    parser.add_argument("-t", "--toggle", dest="toggle", type=str,
                        help='toggle file name')
    parser.add_argument("-v", "--vcd", dest="vcd", type=str,
                        help='vcd file name', nargs='+')
    parser.add_argument("-o", "--out", dest="out", type=str,
                        help='power waveform from PrimeTime',
                        nargs='+', required=True)
    #parser.add_argument("-r", "--rpt", dest="rpt", type=str,
    #                    help='power report from PrimeTime', nargs='+')
    parser.add_argument("-d", "--dir", dest="dir", type=str,
                        help='output directory', default=os.path.curdir)
    parser.add_argument("-w", "--window", dest="window", type=int,
                        help="regression window size (in cycle)", default=128)
    parser.add_argument("--modules", dest="modules", type=str,
                        help="module hierarchy")
    parser.add_argument("--degree", dest="degree", type=int,
                        help='degree of polynomial', default=2)
    parser.add_argument("--log", dest="log", type=str,
                        help="log level", default="info")
    parser.add_argument("--plot-data", dest="plot_data",
                        help="plot data graphs?",
                        action="store_true", default=False)
    parser.add_argument("--max", dest="max", type=int,
                        help="max number of signals")

    args, _ = parser.parse_known_args(argv)
    assert args.vcd or args.toggle
    assert args.log in ['info', 'debug']
    assert os.path.isfile(args.signals)
    os.makedirs(args.dir, exist_ok=True)
    return args

Ys = list()
Y_hats = list()
MODULES = list()
MODELS = list()
SCORES = list()
TERMS = None

def train_and_plot(module, A, y, degree, dirname, cycles, window, positive=True):
    start_time = time()
    model, terms, df, y_hat = polynomial_regression(A, y, degree, positive)
    end_time = time()
    logging.info("Training time for %s: %.2fs", module, end_time - start_time)
    sys.stdout.flush()

    n = A.shape[0]
    sse = np.sum((y - y_hat) ** 2)
    sigma2 = np.var(y) + np.finfo('float64').eps
    r2 = 1.0 - (sse / np.sum((y - y.mean()) ** 2))
    bic = (sse / sigma2) + np.log(n) * df

    Ys.append(y)
    Y_hats.append(y_hat)
    MODULES.append(module)
    MODELS.append(model)
    SCORES.append((r2, bic))
    global TERMS
    if TERMS is None:
        TERMS = terms

    # Plot
    png_filename = os.path.join(dirname, "train-%s.png" % module)
    plot_power(png_filename, [y, y_hat], cycles, window)

def store_model(filename, signals, widths, modules):
    logging.info("Model file: %s", filename)
    models = np.array(MODELS)
    with open(filename, "w") as _f:
        writer = csv.writer(_f)
        writer.writerow(['signals'] + signals)
        writer.writerow(['widths'] + widths)
        writer.writerow(['modules'] + modules)

        labels = ['const'] + [
            '*'.join([signals[i] for i in list(term)])
            for term in TERMS
        ]
        assert len(labels) == models.shape[1], "%d != %d" % (len(labels), models.shape[1])
        for label, model in zip(labels, models.T):
            if np.count_nonzero(model) > 0:
                writer.writerow([label] + model.tolist())

def main(argv):
    args = parse_args(argv)

    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if args.log == 'debug' else logging.INFO
    )

    # Read signals
    logging.info("Load signals from %s", args.signals)
    with open(args.signals, 'r') as _f:
        _signals = _f.read().splitlines()
    logging.debug("Signals: %s", ','.join(_signals))

    if args.max and args.max < len(_signals):
        logging.info("# signal: %d > max: %d", len(_signals), args.max)
        open(os.path.join(args.dir, "model.csv"), 'w').close()
        return

    # Read toggle
    vcd_cycle_list, reset_cycle_list, signals, toggles, widths = \
        read_toggles(args.toggle, args.vcd, args.window, set(_signals))
    assert len(signals) == len(_signals), "%s != %s" % (
        str(signals), str(_signals))
    A = toggles.A.T
    logging.info("Cycles: %d", sum(vcd_cycle_list))
    logging.info("Reset Cycles: %d", sum(reset_cycle_list))
    logging.info("# Selected Signals: %d", len(signals))
    for signal, width in zip(signals, widths):
        logging.info("- %s [%d]", signal, width)

    # Read module hierarchy
    module_filter, misc_module, children, labels = read_modules(args.modules)

    # Read power waveforms
    modules, powers = read_power_files(
        args.out, args.window, vcd_cycle_list, reset_cycle_list, module_filter)

    if labels is None:
        labels = dict()
        for module in modules:
            labels[module] = module
    logging.info("Regression Window: %d", args.window)

    logging.info("Modules:")
    for module, power in zip(modules, powers):
        logging.info("- %s (%s): %.3f mW", module, labels[module], power.mean())

    ys = list(powers)
    total_cycles = sum(vcd_cycle_list) - sum(reset_cycle_list)
    total_cycles = args.window * (
        int((total_cycles  - 1) / args.window) + 1) # For plots

    # Train power models
    start_time = time()
    train_and_plot(
        modules[0], A, ys[0], args.degree,
        args.dir, total_cycles, args.window)

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

        for module in label_ys:
            train_and_plot(
                module, A, label_ys[module], args.degree,
                args.dir, total_cycles, args.window)

    if misc_module:
        y = ys[0] - np.sum(ys[1:], axis=0)
        train_and_plot(
            misc_module, A, y, args.degree,
            args.dir, total_cycles, args.window, False)

    end_time = time()
    logging.info("Total training time: %.2f s", end_time - start_time)
    sys.stdout.flush()

    png_filename = os.path.join(args.dir, "train.png")
    plot_power(png_filename, [
        np.sum(Ys[1:], axis=0) if children else Ys[0],
        np.sum(Y_hats[1:], axis=0) if children else Y_hats[0]
    ], total_cycles, args.window, "Train")

    dump_power_bars(args.dir, 'train', MODULES, Ys, Y_hats)

    if args.plot_data:
        start_time = time()
        data_dirname = os.path.join(args.dir, "train-data")
        A_ = get_terms(A, TERMS).T
        filters = np.array([abs(X[1:]) > 0.0 for X in MODELS])
        plot_data(data_dirname, signals, TERMS, A_, MODULES, Ys, filters)
        end_time = time()
        logging.info("Data plot time: %.2f s", end_time - start_time)

    # data_filename = os.path.join(args.dir, "train-data.csv")
    # idxs = [[x] for x in range(len(signals))]
    # store_data(data_filename, signals, idxs, MODULES, A, Ys, Y_hats)

    model_filename = os.path.join(args.dir, "model.csv")
    store_model(model_filename, signals.tolist(), widths.tolist(), MODULES)

    stats_filename = os.path.join(args.dir, "model-stats.csv")
    logging.info("Statistics file: %s", stats_filename)
    with open(stats_filename, 'w') as _f:
        writer = csv.writer(_f)
        writer.writerow(['module', 'R^2', 'BIC'])
        for module, y, y_hat, (r2, bic) in zip(MODULES, Ys, Y_hats, SCORES):
            writer.writerow([module, "%f" % r2, "%f" % bic])
            logging.info("[%s] y = %.2f, y_hat = %.2f, std = %.2f, R^2 = %f, BIC = %f",
                         module, np.mean(y), np.mean(y_hat), np.std(y), r2, bic)

if __name__ == "__main__":
    np.seterr(divide='raise')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        logging.captureWarnings(True)
        main(sys.argv[1:])
