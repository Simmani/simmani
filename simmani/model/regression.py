import logging
from functools import reduce
from itertools import combinations, repeat
import numpy as np
from scipy.sparse import csr_matrix, issparse, isspmatrix_csr
from sklearn.linear_model import LassoCV
# from sklearn.linear_model import LassoLarsCV as LassoCV
from sklearn.linear_model import ElasticNetCV
from sklearn.preprocessing import StandardScaler

def lasso(A, y, positive=True):
    A_scaler = StandardScaler().fit(A[:, 1:])
    y_scaler = StandardScaler().fit(y.reshape(-1, 1))
    A_new = A_scaler.transform(A[:, 1:])
    y_new = y_scaler.transform(y.reshape(-1, 1)).reshape(-1)
    clf = LassoCV(
        cv=5,
        n_jobs=8,
        normalize=False,
        fit_intercept=False,
        positive=positive).fit(A_new, y_new)
    score = clf.score(A_new, y_new)
    df = np.count_nonzero(clf.coef_)
    logging.info("[LASSO] # iter: %d, alpha: %e, # of terms: %d, score: %f",
                 clf.n_iter_, clf.alpha_, df, score)
    logging.debug("[LASSO] alphas:")
    logging.debug(str(clf.alphas_))
    logging.debug("[LASSO] MSE path:")
    logging.debug(str(clf.mse_path_))
    nonzero = abs(clf.coef_) > 0.0
    coef = np.zeros_like(clf.coef_)
    # coef[nonzero] = ((y_scaler.var_ / A_scaler.var_[nonzero]) ** 0.5) * clf.coef_[nonzero]
    coef[nonzero] = (y_scaler.scale_ / A_scaler.scale_[nonzero]) * clf.coef_[nonzero]
    intercept = y_scaler.mean_ - np.dot(A_scaler.mean_, coef)
    return np.append(intercept, coef), df

def elastic_net(A, y, positive=True):
    A_scaler = StandardScaler().fit(A[:, 1:])
    y_scaler = StandardScaler().fit(y.reshape(-1, 1))
    A_new = A_scaler.transform(A[:, 1:])
    y_new = y_scaler.transform(y.reshape(-1, 1)).reshape(-1)
    clf = ElasticNetCV(
        l1_ratio=[0.1, 0.5, 1.0],
        cv=5,
        n_jobs=8,
        normalize=False,
        fit_intercept=False,
        positive=positive).fit(A_new, y_new)
    score = clf.score(A_new, y_new)
    # Approximate assuming the elastic net is very close to the lasso
    df = np.count_nonzero(clf.coef_)
    logging.info("[ElasticNet] # iter: %d, alpha: %e, l1_ratio: %.2f, # of terms: %d, score: %f",
                 clf.n_iter_, clf.alpha_, clf.l1_ratio_, df, score)
    logging.debug("[ElasticNet] alphas:")
    logging.debug(str(clf.alphas_))
    logging.debug("[ElasticNet] MSE path:")
    logging.debug(str(clf.mse_path_))
    nonzero = abs(clf.coef_) > 0.0
    coef = np.zeros_like(clf.coef_)
    coef[nonzero] = (y_scaler.scale_ / A_scaler.scale_[nonzero]) * clf.coef_[nonzero]
    intercept = y_scaler.mean_ - np.dot(A_scaler.mean_, coef)
    return np.append(intercept, coef), df

def polynomial_regression(A, y, degree, positive=True, use_elastic_net=True):
    """
    Regression with high-order terms
    """
    n, m = A.shape
    assert n == y.shape[0], "%d != %d" % (n, y.shape[0])
    ones = np.ones((n, 1), dtype=A.dtype)
    terms = [(x,) for x in range(m)]
    # Cross terms
    for k in range(2, degree+1):
        terms.extend(list(combinations(range(m), k)))
    # High-order terms
    for k in range(2, degree+1):
        terms.extend([tuple(repeat(x, k)) for x in range(m)])
    A_ = np.append(ones, get_terms(A, terms), axis=1)
    logging.info("[Polynomial Regression] Total # of terms: %d, "
                 "matrix shape: %s", len(terms), str(A_.shape))
    model, df = elastic_net(A_, y, positive) \
        if use_elastic_net else lasso(A_, y, positive)
    return model, terms, df, A_.dot(model)

def get_terms(A, idxs):
    """
    Get high-order terms from idxs
    Inputs:
    - A: n x m matrix
    - idxs: column indice sets
    Outputs:
    - corresponding terms
    """
    n = A.shape[0]
    if isspmatrix_csr(A):
        data = list()
        indices = list()
        indptr = [0]
        for idx in idxs:
            var = A[:, np.array(idx)] if idx else \
                  csr_matrix(np.ones((n, 1)))
            term = None
            for a in var.T:
                term = a if term is None else term.multiply(a)
            data.extend(term.data)
            indices.extend(term.indices)
            indptr.append(indptr[-1] + term.indices.shape[0])
        data = np.array(data, dtype=A.dtype)
        indices = np.array(indices, dtype=np.int64)
        indptr = np.array(indptr, dtype=np.int64)
        shape = len(idxs), n
        return csr_matrix((data, indices, indptr), shape=shape).T

    assert not issparse(A)
    terms = np.empty((n, len(idxs)), dtype=A.dtype)
    for i, idx in enumerate(idxs):
        var = A[:, np.array(idx)].reshape(n, len(idx)) \
              if idx else np.ones((n, 1))
        terms[:, i] = reduce(np.multiply, var.T).T
    return terms
