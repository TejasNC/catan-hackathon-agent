import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot'))
import agent as _a
P = {'prod': 0.189, 'prod_late': 0.0937, 'res_w': (1.271, 1.115, 0.889, 0.823, 0.902), 'div': 0, 'exp1': 0.0133, 'exp2': 0, 'exp_n': 0.296, 'port3': 0.407, 'port2': 0.0402, 'road_len': 0.2281}  # static assets from after_w.npy (VP units); transition terms stay v5
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(P))
