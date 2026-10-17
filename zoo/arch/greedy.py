"""Frozen archetype sparring partner (v5_final with extreme hand-set weights)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import v5_final as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(prod=0.10, prod_late=0.09, discard=0.02, dev_other=0.05, knight_hand=0.03, ready_dev=0.02))
