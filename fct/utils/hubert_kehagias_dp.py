# -*- coding: utf-8 -*-

"""
Hubert-Kehagias Dynamic Programming Univariate Segmentation Procedure

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import numpy as np

def cumulative_variance(x):
    """ Cumulatiave variance of sequence `x`
    """

    n = len(x)
    csum = np.cumsum(x)
    mean = csum / (np.arange(n) + 1)
    return np.cumsum(np.power(x, 2)) - csum*mean

def segment(x, Kmax=np.infty):
    """
    Recursively break sequence `x` with 1 to max `Kmax` breakpoints.

    Returns
    -------

    T: breakpoints matrix
    C: costs vector for each segmentation
    """

    n = len(x)
    D = np.zeros((n+1, n+1), dtype=np.float32)
    for i in np.arange(n):
        D[i, i+1:] = cumulative_variance(x[i:])

    Kmax = min(n, Kmax)
    C = np.zeros((Kmax, n+1), dtype=np.float32)
    T = np.zeros((Kmax, n+1), dtype=np.uint16)
    C[0, :] = D[0, :]

    for k in np.arange(1, Kmax):

        for s in np.arange(1, n+1):

            costs = C[k-1, :s] + D[:s, s]
            t = np.argmin(costs)
            C[k, s] = costs[t]
            T[k, s] = t

        # test for termination

    return T, np.copy(C[:, n])

def backtrack(T, rank):
    """
    Extract breakpoints indices from matrix T
    for segmentation with `rank` breakpoints
    """

    sequence = np.zeros(rank+1, dtype=np.uint16)
    sequence[rank] = T.shape[1] - 1
    for k in np.arange(rank-1, 0, -1):
        sequence[k] = T[k, sequence[k+1]]

    return sequence.tolist()

def approx(x, segmentation):
    """
    Approximate observations in `x`
    by the mean of the segment corresponding to each observation.
    """

    r = np.zeros(len(x))
    for t, s in zip(segmentation[:-1], segmentation[1:]):
        r[t:s] = np.mean(x[t:s])
    return r

class HubertKehagiasSegmentation(object):
    """
    Find homogeneous segments in mean and variance
    within an ordered sequence of univariate observations (eg. time serie),
    using Hubert-Kehagias Dynamic Programming Segmentation Procedure.

    Example:

        Generate random normal sequence of observations,
        with 5 different segments
        `p` rows contain (number of observations to generate, mean, standard deviation)

        >>> np.random.seed(5)
        >>> p = [[ 10, 5,  .25 ],
        ...     [ 15, 2,  .10 ],
        ...      [ 20, 8, 1.75 ],
        ...      [  6, 3,  .85 ],
        ...      [ 14, 6, 1.20 ]]
        >>> sequence = np.zeros(0)
        >>> for length, mean, std in p:
        ...   sequence = np.concatenate([sequence, np.random.normal(mean, std, length)])

        Create a new segmentation object :

        >>> segmentation = HubertKehagiasSegmentation(sequence)

        Compute optimal number of breakpoints :
        >>> kopt = segmentation.kopt(len(sequence) // 3)
        >>> kopt
        5

        Indices of segment breakpoints :

        >>> segmentation.breakpoints(kopt)
        [0, 10, 25, 45, 51, 65]

        segments() returns a segment index sequence
        with same length as `sequence`:

        >>> len(segmentation.segments(kopt))
        65

        Plot modeled sequence (red) on top of input sequence (blue) :

        # >>> from matplotlib import pyplot as plt
        # >>> plt.plot(sequence, 'b')
        # >>> plt.plot(segmentation.model(kopt), 'r-', linewidth=1.5)
        # >>> plt.show()

        Compute model residuals :

        >>> residuals = sequence - segmentation.model(kopt)
        >>> sqe = np.sum(np.power(residuals, 2))
        >>> assert(np.float32(sqe) == segmentation.sqerror(kopt))

    References:

    [1] Hubert, P. (2000).
        The segmentation procedure as a tool for discrete modeling of hydrometeorological regimes.
        Stochastic Environmental Research and Risk Assessment, 14(4‑5), 297‑304.
        https://doi.org/10.1007/PL00013450


    [2] Kehagias, A., Nidelkou, E., & Petridis, V. (2006).
        A dynamic programming segmentation procedure for hydrological and environmental time series.
        Stochastic Environmental Research and Risk Assessment, 20(1‑2), 77‑94.
        https://doi.org/10.1007/s00477-005-0013-6
    """

    def __init__(self, x, Kmax=np.infty):
        """
        Segment sequence `x` into a maximum of `Kmax` segments.
        """
        self.x = x
        self.T, self.J = segment(x, Kmax)

    def bic(self):
        """
        Bayesian Information Criterion (BIC)
        for segmentation with 1,...,n breakpoints
        """
        n = len(self.x)
        return n*np.log(self.J[:-1] / (n-1)) + 2*np.arange(1, len(self.J))*np.log(n)

    def kopt(self, kmax=None):
        """
        Compute the optimal number of breakpoints,
        based on Bayesian Information Criterion (BIC)
        """
        bic = self.bic()
        if kmax is None:
            kmax = min(len(bic), np.floor_divide(len(self.x), 3))
        else:
            kmax = min(kmax, len(bic))
        return np.argmin(bic[:kmax+1]) + 1

    def breakpoints(self, rank):
        """
        Returns breakpoints indices for segmentation with `rank` breakpoints
        """
        return backtrack(self.T, rank)

    def segments(self, rank):
        """
        Returns the calculated segment index for each input observation
        for segmentation with `rank` breakpoints.
        The returned sequence has same length as the input sequence.
        """

        breakpoints = self.breakpoints(rank)
        segments = np.zeros(len(self.x), dtype=np.uint16)

        for seg_index, (start, stop) in enumerate(zip(breakpoints[:-1], breakpoints[1:])):
            segments[start:stop] = seg_index

        return segments

    def model(self, rank):
        """
        Returns the modeled observations sequence of same length as input sequence,
        for segmentation with `rank` breakpoints.

        Approximate observations in `x`
        by the mean of the segment corresponding to each observation.
        """
        return approx(self.x, self.breakpoints(rank))

    def sqerror(self, rank):
        """
        Return the total square error
        between the model with `rank` breakpoints and the input data.
        """
        return self.J[rank-1]

if __name__ == "__main__":

    #pylint: disable=wrong-import-position,wrong-import-order

    import doctest
    doctest.testmod()
