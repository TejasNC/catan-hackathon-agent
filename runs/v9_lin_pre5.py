import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot'))
import agent as _a
W = [1.0, 0.2246, 0.1405, 0.211, 0.1457, 0.1981, 0.1102, 0.0652, 0.101, 0.1038, 0.101, -0.2796, 0.0092, 0.055, 0.1017, 0.1088, 0.0363, 0.7995, 0.8703, 0.2717, 1.4212, 1.4133, 0.8233, 0.0841, 1.1277, 0.0312, 0.0035, 0.4833, 0.3267]  # VP units, order tools/feats.NAMES, from pre5_w.npy
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(lin=W, card=W[15], knight_hand=W[21], dev_other=W[22], opp_k=1.0))
