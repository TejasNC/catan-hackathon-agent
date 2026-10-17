"""Adversary: hoards; never trades/spends except dev cards & cities; plays VP/knights for Largest Army."""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adv_common import *
BAN = (AT.MARITIME_TRADE, AT.BUILD_ROAD, AT.PLAY_MONOPOLY, AT.PLAY_YEAR_OF_PLENTY, AT.PLAY_ROAD_BUILDING)
class Agent:
    def __init__(self): self.rng = random.Random(3)
    def decide(self, obs, acts):
        st = obs._game.state
        if st.is_initial_build_phase: return f_pick(obs, acts, self.rng)
        for t in (AT.BUILD_CITY, AT.BUY_DEVELOPMENT_CARD, AT.PLAY_KNIGHT_CARD, AT.BUILD_SETTLEMENT):
            for i, a in enumerate(acts):
                if a.action_type == t: return i
        cand = [i for i, a in enumerate(acts) if a.action_type not in BAN]
        return f_pick(obs, acts, self.rng, cand or None)
