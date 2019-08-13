import os
import csv
import shutil
import logging
import numpy as np
import matplotlib
matplotlib.use('Agg') # No DISPLAY
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 16})
plt.rcParams.update({'agg.path.chunksize': 10000})

def plot_data(dirname, signals, terms, A, modules, ys, filters=None):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
    os.makedirs(dirname)

    if filters is None:
        filters = np.ones((len(modules), len(terms)), dtype=bool)
    assert filters.shape == (len(modules), len(terms)), \
        "%s != (%s, %s)" % (str(filters.shape), len(modules), len(terms))

    for module, y, f in zip(modules, ys, filters):
        mod_dirname = os.path.join(dirname, module)
        os.makedirs(mod_dirname)

        for i, (term, a) in enumerate(zip(terms, A)):
            if f[i]:
                ts = [signals[x] for x in list(term)]
                filename = os.path.join(mod_dirname, "-".join(ts) + ".png")
                plt.figure(i)
                plt.title("*".join(ts))
                plt.xlabel("toggles", fontsize="large")
                plt.ylabel("Power(mW)", fontsize="large")
                plt.plot(a, y, 'o')
                plt.savefig(filename, format="png")
                plt.close(i)

def store_data(filename, signals, terms, modules, A, ys, y_hats):
    logging.info("Data file: %s", filename)
    headers = list()
    for term in terms:
        var = [signals[i] for i in list(term)]
        headers.append("*".join(var))
    for module in modules:
        headers.extend(["power-" + module, "predict-" + module])
    powers = list()
    for y, y_hat in zip(ys, y_hats):
        powers.extend([y, y_hat])
    powers = np.array(powers)
    with open(filename, "w") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for t, p in zip(A, np.array(powers).T):
            writer.writerow(t.tolist() + p.tolist())

def load_data(filename, signals, modules):
    logging.info("Data file: %s", filename)
    A = list()
    ys = list()
    y_hats = list()
    with open(filename, "r") as _f:
        reader = csv.reader(_f)
        for k, line in enumerate(reader):
            if k == 0:
                # header
                assert all(x == y for x, y in zip(signals, line[:len(signals)]))
                for i, module in enumerate(modules):
                    ys.append(list())
                    y_hats.append(list())
                    assert line[len(signals) + 2*i] == "power-%s" % (module), \
                        "%s != power-%s" % (line[len(signals) + 2*i], module)
                    assert line[len(signals) + 2*i + 1] == "predict-%s" % (module), \
                        "%s != predict-%s" % (line[len(signals) + 2*i + 1], module)
            else:
                # actual values
                A.append([float(x) for x in line[:len(signals)]])
                for i in range(len(modules)):
                    ys[i].append(float(line[len(signals) + 2*i]))
                    y_hats[i].append(float(line[len(signals) + 2*i + 1]))

    return np.array(A), np.array(ys), np.array(y_hats)

def plot_power(filename, ys, cycles, window, title=""):
    """
    Plot time-based power
    """
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    logging.info("Power Plot: %s", filename)
    assert len(ys) == 2
    intervals = np.arange(0, cycles, window)
    unit = ""
    if int(cycles / 1e9) > 5:
        intervals = intervals / 1e9
        unit = '(B)'
    elif int(cycles / 1e6) > 5:
        intervals = intervals / 1e6
        unit = '(M)'
    elif int(cycles / 1e3) > 5:
        intervals = intervals / 1e3
        unit = '(K)'
    #for y in ys:
      #assert len(intervals) == y.shape[0], \
        #"%d != %d" % (len(intervals), y.shape[0])

    xmax = np.max(intervals)
    ymax = 1.05 * (max(np.max(ys[0]), np.max(ys[1])) \
        if ys[0] is not None else np.max(ys[1]))
    ymin = 0.95 * (min(np.min(ys[0]), np.min(ys[1])) \
        if ys[0] is not None else np.min(ys[1]))

    plt.figure(figsize=(24, 8))

    if ys[0] is not None:
        plt.subplot(211)
        # plt.title("[Power] " + title)
        plt.xlim((0.0, xmax))
        plt.ylim((ymin, ymax))
        plt.plot(intervals, ys[0][:len(intervals)], 'b-')
        plt.ylabel("Actual Power (mW)")

    plt.subplot(212)
    # plt.title("[Predict] " + title)
    plt.xlim((0.0, xmax))
    plt.ylim((ymin, ymax))
    if ys[0] is not None:
        plt.plot(intervals, ys[0][:len(intervals)], 'b-')
    plt.plot(intervals, ys[1][:len(intervals)], 'g-')
    plt.ylabel("Predicted Power (mW)")
    plt.xlabel("Cycles %s" % unit)

    plt.savefig(filename, format="png", bbox_inches='tight')
    plt.close('all')

def plot_power_bars(filename, modules, ys, y_hats, title=None):
    """
    Plot Power Breakdown
    """
    logging.info("Power Break-down: %s", filename)
    plt.figure(figsize=(8, 6))
    if title is not None:
        plt.title(title)
    y1_means = [np.mean(y) for y in ys]
    y2_means = [np.mean(y_hat) for y_hat in y_hats]
    y1_stacks = [sum(y1_means[:i]) for i in range(len(y1_means))]
    y2_stacks = [sum(y2_means[:i]) for i in range(len(y2_means))]
    bars = list()
    for i, (module, y1_mean, y1_stack, y2_mean, y2_stack) in \
        enumerate(zip(modules, y1_means, y1_stacks, y2_means, y2_stacks)):
        color = plot_power_bars.colors[i % len(plot_power_bars.colors)]
        bars.append(plt.bar(np.arange(2), (y1_mean, y2_mean), 0.5,
                            bottom=(y1_stack, y2_stack),
                            align='center',
                            color=color,
                            label=module)[0])
    plt.xlim((-0.5, 3.0))
    plt.xticks(np.arange(2), ("Power", "Predict"))
    plt.ylabel("Power(mW)", fontsize='large')
    plt.legend(reversed(bars), reversed(modules), fontsize='x-small')
    plt.savefig(filename, format="png", bbox_inches='tight')
    plt.close('all')
plot_power_bars.colors = [
    'darkslategray',
    'mediumseagreen',
    'orangered',
    'c',
    'm',
    'y',
    'k',
    "peachpuff",
    "darkcyan",
    "peru",
    "orchid",
    "salmon",
    "lime"]

def store_power_bars(filename, modules, ys, y_hats):
    logging.info("Power Bars in CSV: %s", filename)
    def _mean(y):
        return "%.2f" % y.mean()
    with open(filename, "w") as _f:
        writer = csv.writer(_f)
        if ys is not None:
            writer.writerow(["Module", "Actual Power", "Predicted Power"])
            writer.writerow([modules[0], _mean(ys[0]), _mean(y_hats[0])])
            for module, y, y_hat in sorted(zip(modules[1:], ys[1:], y_hats[1:])):
                writer.writerow([module, _mean(y), _mean(y_hat)])
        else:
            writer.writerow(["Module", "Predicted Power"])
            writer.writerow([modules[0], _mean(y_hats[0])])
            for module, y_hat in sorted(zip(modules[1:], y_hats[1:])):
                writer.writerow([module, _mean(y_hat)])

def dump_power_bars(dirname, benchmark, labels, ys, y_hats):
    csv_filename = os.path.join(dirname, "power-bars-%s.csv" % benchmark)
    png_filename = os.path.join(dirname, "power-bars-%s.png" % benchmark)
    store_power_bars(csv_filename, labels, ys, y_hats)
    if ys is not None:
        idx = 1 if len(labels) > 1 else 0
        plot_power_bars(png_filename, labels[idx:], ys[idx:], y_hats[idx:])
