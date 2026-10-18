import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import agent as _a
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(army_lead=0.40,knight_played=0.23,road_lead=0.51,road_len=0.06))
