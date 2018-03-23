import numpy as np

def cumulative_variance(x):

    n = len(x)
    csum = np.cumsum(x)
    mean = csum / (np.arange(n) + 1)
    return np.cumsum(np.power(x, 2)) - csum*mean

def segment(x, Kmax=np.infty):

    n = len(x)
    D = np.zeros((n+1, n+1), dtype=np.float32)
    for i in np.arange(n):
        D[i, i+1:] = cumulative_variance(x[i:])

    Kmax = min(n, Kmax)
    C = np.zeros((Kmax, n+1), dtype=np.float32)
    T = np.zeros((Kmax, n+1), dtype=np.uint16)
    C[0,:] = D[0,:]

    for k in np.arange(1, Kmax):
    
        for s in np.arange(1, n+1):

                costs = C[k-1, :s] + D[:s, s]
                t = np.argmin(costs)
                C[k, s] = costs[t]
                T[k, s] = t

        # test for termination

    return T, np.copy(C[:, n])

def backtrack(T, rank):

    sequence = np.zeros(rank+1, dtype=np.uint16)
    sequence[rank] = T.shape[1] - 1
    for k in np.arange(rank-1, 0, -1):
        sequence[k] = T[k, sequence[k+1]]

    return sequence.tolist()

def approx(x, segmentation):

    r = np.zeros(len(x))
    for t, s in zip(segmentation[:-1], segmentation[1:]):
        r[t:s] = np.mean(x[t:s])
    return r

class HubertKehagiasSegmentation(object):

    def __init__(self, x, Kmax=np.infty):
        self.x = x
        self.T, self.J = segment(x, Kmax)

    def bic(self):
        n = len(self.x)
        return n*np.log(self.J[:-1] / (n-1)) + 2*np.arange(1, len(self.J))*np.log(n)

    def kopt(self, kmax=None):
        bic = self.bic()
        if kmax is None:
            kmax = min(len(bic), np.floor_divide(len(self.x), 3))
        else:
            kmax = min(kmax, len(bic))
        return np.argmin(bic[:kmax+1]) + 1

    def segments(self, rank):
        return backtrack(self.T, rank)

    def model(self, rank):
        return approx(self.x, self.segments(rank))

    def sqerror(self, rank):
        return self.J[rank-1]

if __name__ == '__main__':

    from matplotlib import pyplot as plt

    np.random.seed(5)

    p = [[ 10, 5,  .25 ],
         [ 15, 2,  .10 ],
         [ 20, 8, 1.75 ],
         [  6, 3,  .85 ],
         [ 14, 6, 1.20 ]]

    sequence = np.zeros(0)
    for length, mean, std in p:
        sequence = np.concatenate([sequence, np.random.normal(mean, std, length)])

    segmentation = HubertKehagiasSegmentation(sequence)
    kopt = segmentation.kopt(len(sequence) // 3)

    plt.plot(sequence, 'b')
    plt.plot(segmentation.model(kopt), 'r-', linewidth=1.5)
    plt.show()

    residuals = sequence - segmentation.model(kopt)
    sqe = np.sum(np.power(residuals, 2))
    assert( np.float32(sqe) == segmentation.sqerror(kopt) )


