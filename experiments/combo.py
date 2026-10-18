import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search as _s
class Agent(_s.Agent):
    TURN_K = 3
    MARGIN = 0.05
    def __init__(self):
        super().__init__(dict(regime=0.5, reg_fade=0.35, reg_dev=0.25))
