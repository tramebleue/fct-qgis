from scipy.stats import f as Fischer


def ScheffeTest(x1, x2, k, alpha):
    """ Tukey range test
        https://en.wikipedia.org/wiki/Tukey%27s_range_test
    """

    n1 = len(x1)
    n2 = len(x2)
    mean1 = np.mean(x1)
    mean2 = np.mean(x2)
    variance = np.var(np.concatenate([ x1, x2 ]))

    sobs = np.abs(mean2 - mean1) / np.sqrt(variance * (1./n1 + 1./n2))
    
    df1 = k - 1
    df2 = n1 + n2 - k
    if df2 <= 0:
        df2 = -df2 + 0.01

    q = Fischer.isf(alpha, df1, df2)
    # scrit = np.sqrt(q * (k - 1))

    return bool(sobs >= q)

def test_segmentation(x, segmentation, alpha):

    k = len(segmentation) - 1
    if k < 2:
        return False

    for a, b, c in zip(segmentation[:-2], segmentation[1:-1], segmentation[2:]):
        t = ScheffeTest(x[a:b], x[b:c], k, alpha)
        if t is False:
            return False

    return True