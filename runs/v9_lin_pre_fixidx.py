import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot'))
import agent as _a
W = [1.0, 0.1122, 0.1432, 0.2038, 0.1674, 0.1313, 0.0597, 0.1073, 0.1206, 0.0692, 0.0718, 0.5223, 0.0335, 0.0154, 0.2459, 0.0295, 0.036, 1.0636, 1.4811, 0.1333, 0.9805, 0.5394, 0.4837, -0.2179, 0.9035, -0.0184, 0.1737, 0.4353, -0.675]  # VP units, order tools/feats.NAMES, from data_v2_w.npy
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(lin=W, card=W[15], knight_hand=W[21], dev_other=W[22], opp_k=1.0))
