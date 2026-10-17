"""Frozen archetype sparring partner (v5_final with extreme hand-set weights)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import v5_final as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(res_w=(2.0, 2.0, 1.0, 1.2, 0.9), exp1=0.04, exp2=0.02, exp_n=0.10, road_len=0.10, road_lead=0.50, opp_k=1.1))
