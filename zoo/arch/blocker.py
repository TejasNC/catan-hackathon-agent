"""Frozen archetype sparring partner (v5_final with extreme hand-set weights)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import v5_final as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(opp_k=1.25))
