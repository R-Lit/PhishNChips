import numpy as np


def safetility(recall, fpr, tau=0.10, n=5, alpha=2):
    """
    Compute Safetility score.

    recall: float in [0, 1] — proportion of phishing correctly blocked
    fpr:    float in [0, 1] — proportion of legitimate emails incorrectly blocked
    tau:    float — FPR threshold above which deployability drops sharply
    n:      float — Hill function exponent (steepness of penalty)
    alpha:  float — recall exponent (default 2, i.e. Recall²)

    Returns float in [0, 1]
    """
    if n == float('inf'):
        penalty = 0.0 if fpr > tau else 1.0
    else:
        penalty = 1.0 / (1.0 + (fpr / tau) ** n)
    return (recall ** alpha) * penalty


def safetility_batch(df, tau=0.10, n=5, alpha=2, recall_col='recall', fpr_col='fpr'):
    """
    Compute Safetility for a DataFrame of configurations.
    Expects recall and FPR as fractions (not percentages).
    """
    return df.apply(
        lambda row: safetility(row[recall_col], row[fpr_col], tau=tau, n=n, alpha=alpha),
        axis=1
    )
