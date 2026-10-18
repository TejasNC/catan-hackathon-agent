import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import agent as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(prog_city=0.9, prog_settle=0.5, prog_dev=0.15))
