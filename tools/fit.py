"""Logistic regression of game outcome on difference features (Buro-style), from self-play data.
Prints weights in log-odds and in VP units (divided by the VP weight)."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sklearn.linear_model import LogisticRegression
from tools.feats import NAMES

files = sorted(glob.glob(sys.argv[1] + "_*.npz"))
X = np.concatenate([np.load(f)["X"] for f in files]); Y = np.concatenate([np.load(f)["Y"] for f in files])
T = np.concatenate([np.load(f)["T"] for f in files])
print("states", len(Y), "files", len(files))
# symmetric augmentation: the other seat sees -x and the opposite outcome
Xa = np.concatenate([X, -X]); Ya = np.concatenate([Y, 1 - Y])
n = len(Y); idx = np.arange(n)
rng = np.random.default_rng(0)
# split by row blocks (approx by game) for an honest holdout
cut = int(0.8 * n)
tr = np.concatenate([idx[:cut], idx[:cut] + n]); te = np.concatenate([idx[cut:], idx[cut:] + n])
clf = LogisticRegression(fit_intercept=False, C=1.0, max_iter=2000)
clf.fit(Xa[tr], Ya[tr])
from sklearn.metrics import log_loss, accuracy_score
p = clf.predict_proba(Xa[te])[:, 1]
print("holdout logloss", round(log_loss(Ya[te], p), 4), "acc", round(accuracy_score(Ya[te], p > .5), 4))
w = clf.coef_[0]
wvp = w[NAMES.index("vp")]
for name, wi in zip(NAMES, w):
    print(f"{name:14s} logodds {wi:+.4f}   VP-units {wi / wvp:+.4f}")
np.save(sys.argv[1] + "_w.npy", w)
