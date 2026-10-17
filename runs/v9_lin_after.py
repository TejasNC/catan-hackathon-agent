import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot'))
import agent as _a
W = [1.0, 0.2401, 0.2108, 0.168, 0.1556, 0.1704, 0.0907, 0.1027, 0.0989, 0.089, 0.087, -0.1864, 0.0133, -0.0065, 0.296, 0.0552, 0.0511, 0.9299, 1.0701, 0.229, 1.5909, 1.0846, 0.7994, -0.231, 0.407, 0.0402, 0.2281, 0.5505, -0.6247]  # VP units, order tools/feats.NAMES, from after_w.npy
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(lin=W, card=W[15], knight_hand=W[21], dev_other=W[22], opp_k=1.0))
