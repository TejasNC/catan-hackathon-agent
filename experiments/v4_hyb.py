import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import agent as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(prod=0.15, prod_late=0.08, res_w=(0.8, 0.95, 1.2, 1.1, 0.95), div=0.45,
                              exp_n=0.2, port3=0.5))
