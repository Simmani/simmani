import sys
import logging
from time import time
import numpy as np
from scipy.sparse.linalg import svds
from sklearn.cluster import KMeans

def pca(A, k):
    """
    Principle Component Analysis

    Inputs:
      - A: m x n CSR matrix
      - k: # of components

    Outputs:
      - projections to k singular vectors
    """

    m = A.shape[0]
    Vt = svds(A, k=k)[2]
    A_k = A.dot(Vt.T)
    assert A_k.shape == (m, k)
    return A_k

def spectral_clustering(A, min_k, max_k):
    """
    Spectral clustering with model selection

    Inputs:
      - A: data (CSR matrix)
      - min_k: min # of clusters
      - max_k: max # of clusters
    Outputs:
      - cluster centers
    """

    n = A.shape[0]
    # Dimension reduction
    start_time = time()
    A_max_k = pca(A, max_k)
    end_time = time()
    logging.info("[Spectral Clustering] dimension reduction time: %.2fs",
                 end_time - start_time)

    def clustering(A, k):
        # Run k-menas multiple times
        kmeans = KMeans(n_clusters=k, n_jobs=8).fit(A)

        # compute BIC
        sig = kmeans.inertia_ / (n - k)
        if sig < 1e-25:
            return None, float('inf')
        counts = np.array([
            np.count_nonzero(kmeans.labels_ == i)
            for i in range(k)
        ])
        d = k
        l = 0.5 * k
        l -= 0.5 * (n * d) * np.log(sig)
        l += np.sum(counts * np.log(counts / n))
        score = ((k + 1) * d) - (2 * l)

        # Find centers
        centers = []
        for i, mean in enumerate(kmeans.cluster_centers_):
            label_i = kmeans.labels_ == i
            dist = np.full(A.shape[0], np.inf)
            dist[label_i] = np.power((A[label_i] - mean), 2).sum(axis=1)
            centers.append(np.argmin(dist))

        assert all([
            kmeans.labels_[center] == i
            for i, center in enumerate(centers)
        ])

        return centers, score, kmeans.labels_

    T = None
    score = float('inf')
    for k in range(min_k, max_k + 1):
        start_time = time()
        A_k = A_max_k[:, :k]
        score_k = -float('inf')
        centers_k, score_k, labels_k = clustering(A_k, k)
        delta = score_k - score
        end_time = time()
        logging.info("[Spectral Clustering] k: %d, BIC: %.2f, delta: %.2f, time: %.2fs",
                     k, score_k, delta, end_time - start_time)
        sys.stdout.flush()

        if not T:
            T = abs(score_k)
            T_step = T / max(max_k - min_k, 1)
        if np.exp(-delta / T) < np.random.uniform():
            break
        if delta < -10:
            score = score_k
            centers = centers_k
            labels = labels_k
        T -= T_step

    assert centers is not None
    return centers, labels
