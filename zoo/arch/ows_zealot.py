"""Frozen archetype sparring partner (v5_final with extreme hand-set weights)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import v5_final as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(res_w=(0.8, 0.8, 1.6, 2.2, 2.2), ready_dev=0.25, knight_hand=0.20, knight_played=0.25, army_lead=0.40))
