#!/usr/bin/env python3

# See LICENSE for license details.

import os.path
import sys
import argparse
import logging
import warnings
from time import time
import csv
import numpy as np
from utils.toggle import read_toggles
from model.clustering import spectral_clustering

def parse_args(argv):
    parser = argparse.ArgumentParser(description='Signal Clustering')
    parser.add_argument("-t", "--toggle", dest="toggle", type=str,
                        help='toggle file name')
    parser.add_argument("-v", "--vcd", dest="vcd", type=str,
                        help='vcd file name', nargs='+')
    parser.add_argument("-d", "--dir", dest="dir", type=str,
                        help='output directory', default=os.path.curdir)
    parser.add_argument("-n", "--num", dest="K", type=int,
                        help='min # of clusters', default=2)
    parser.add_argument("-w", "--window", dest="window", type=int,
                        help="clustering window size (in cycle)", default=64)
    parser.add_argument("--log", dest="log", type=str,
                        help="log level", default="info")

    args, _ = parser.parse_known_args(argv)
    assert args.vcd or args.toggle
    assert args.log in ['info', 'debug']
    os.makedirs(args.dir, exist_ok=True)
    return args

def store_clusters(filename, signals, labels, centers):
    logging.info("Cluster file: %s", filename)
    assert len(signals) == len(labels)

    clusters = list()
    for i, center in enumerate(centers):
        cluster = list()
        for signal in signals[labels == i]:
            if signal != center:
                cluster.append(signal)
        cluster = [center] + sorted(cluster)
        assert len(cluster) == len(signals[labels == i])
        clusters.append(cluster)

    clusters = sorted(clusters, key=lambda x: x[0])
    max_len = max([len(cluster) for cluster in clusters])
    for cluster in clusters:
        cluster.extend([''] * (max_len - len(cluster)))

    with open(filename, "w") as _f:
        writer = csv.writer(_f)
        for row in np.array(clusters).T:
            writer.writerow(row.tolist())

def main(argv):
    args = parse_args(argv)

    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if args.log == 'debug' else logging.INFO
    )

    # Read VCD
    vcd_cycle_list, reset_cycle_list, bus_signals, toggles, _ = \
        read_toggles(args.toggle, args.vcd, args.window)
    logging.info("Cycles: %d", sum(vcd_cycle_list))
    logging.info("Reset Cycles: %d", sum(reset_cycle_list))
    logging.info("# Signals: %d", len(bus_signals))
    sys.stdout.flush()

    # Clustering
    min_k = args.K
    max_k = 200 if len(bus_signals) > 200 else \
            min(args.K + 10, int(toggles.shape[0] / 2))
    start_time = time()
    centers, labels = spectral_clustering(toggles, min_k, max_k)
    signals = bus_signals[centers]
    end_time = time()
    logging.info("Total clustering time: %.2f s", end_time - start_time)
    logging.info("%d Selected Signals:", len(signals))
    for signal in signals:
        logging.info("- %s", signal)
    sys.stdout.flush()

    signal_filename = os.path.join(args.dir, 'signals_%d.csv' % args.window)
    logging.info('Signal file: %s', signal_filename)
    np.savetxt(signal_filename, sorted(signals), fmt='%s', delimiter=',')

    cluster_filename = os.path.join(args.dir, 'clusters_%d.csv' % args.window)
    store_clusters(cluster_filename, bus_signals, labels, signals)

if __name__ == "__main__":
    np.seterr(divide='raise')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        logging.captureWarnings(True)
        main(sys.argv[1:])
