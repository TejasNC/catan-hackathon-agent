import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot'))
import agent as _a
P = {'div': 0.2736, 'exp1': 0.0133, 'exp2': 0, 'exp_n': 0.296, 'port3': 0.407, 'port2': 0.0402, 'road_len': 0.0395}  # static assets from after_w.npy (VP units); transition terms stay v5
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(P))
