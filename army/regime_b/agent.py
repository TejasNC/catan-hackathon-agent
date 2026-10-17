"""v5 value function + regime B (expand->build resource weights, fade expansion, late dev value)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regime_b_base as _a


class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(regime=0.5, reg_fade=0.35, reg_dev=0.25))
