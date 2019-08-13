import os.path
import csv
import numpy as np
from scipy.sparse import csr_matrix, isspmatrix_csr, issparse

def _average_rows_dense(A, window):
    """
    A utility function to average intervals of each row
    TODO: is there a better way?
    Inputs:
      - A: m x n matrix
      - window: window size
    Outputs:
      - m x (n / window) matrix
    """
    def avg(a):
        if a.shape[0] % window == 0:
            return np.mean(a.reshape(-1, window), axis=1)

        return np.nanmean(np.pad(
            a,
            (0, window - a.shape[0] % window),
            mode='constant',
            constant_values=np.nan).reshape(-1, window), axis=1)

    return np.apply_along_axis(avg, 1, A) if window > 0 else A

def _average_rows_csr(A, window):
    """
    A utility function to average intervals of each row
    TODO: is there a better way?
    Inputs:
      - A: m x n matrix
      - window: window size
    Outputs:
      - m x (n / window) matrix
    """
    if window == 1:
        return A

    m, n = A.shape

    def avg(idxs, vals):
        _idxs = (idxs / window).astype(int)
        _vals = (vals / window)
        avg_idxs = np.unique(_idxs)
        avg_vals = np.bincount(_idxs, weights=_vals)[avg_idxs]
        return avg_idxs, avg_vals

    indptr = [0]
    indices = []
    values = []
    for i in range(len(A.indptr)-1):
        low, high = A.indptr[i], A.indptr[i+1]
        idxs = A.indices[low:high]
        vals = A.data[low:high]
        avg_idxs, avg_vals = avg(idxs, vals)
        assert len(avg_idxs) == len(avg_vals)
        indptr.append(indptr[-1] + len(avg_idxs))
        indices.extend(avg_idxs)
        values.extend(avg_vals)
    shape = (m, int((n - 1) / window) + 1)
    return csr_matrix((values, indices, indptr), shape=shape)

def average_rows(A, window):
    if window == 1:
        return A
    if isspmatrix_csr(A):
        return _average_rows_csr(A, window)
    assert not issparse(A)
    return _average_rows_dense(A, window)

def divide_csr(A, denoms):
    """
    Divide the CSR matrix by a vector
    """
    assert A.shape[0] == len(denoms)
    data = np.empty(A.data.shape, dtype=float)
    for i in range(len(A.indptr)-1):
        low, high = A.indptr[i], A.indptr[i+1]
        data[low:high] = A.data[low:high] / denoms[i]
    return csr_matrix((data, A.indices, A.indptr), shape=A.shape)

def translate_indices(from_signals, to_signals, terms):
    """
    A utility function to get new indices in terms
    """
    assert len(from_signals) >= len(to_signals)

    signal_map = dict()
    for i, signal in enumerate(to_signals):
        signal_map[from_signals.index(signal)] = i

    return [
        [
            signal_map[var]
            for var in term
        ]
        for term in terms
    ]

def find_children(modules):
    """
    Find children for modules
    """
    children = dict()
    _modules = list(reversed(modules))
    for module in _modules:
        children[module] = list()
    for i, module1 in enumerate(_modules):
        for module2 in _modules[(i+1):]:
            if module2 in module1:
                children[module2].append(module1)
                break

    return children

def read_modules(filename):
    """
    Read module hierarchies
    """
    if not filename:
        return None, None, None, None

    modules = list()
    labels = dict()
    assert os.path.exists(filename)
    with open(filename) as _f:
        reader = csv.reader(_f)
        for line in reader:
            module = line[0]
            modules.append(module)
            labels[module] = line[1] if len(line) > 1 else module

    return set(modules[:-1]), modules[-1], find_children(modules), labels
