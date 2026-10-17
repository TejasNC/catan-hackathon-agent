import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import agent as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(kn_hold=0.15))
