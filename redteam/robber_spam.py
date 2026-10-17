"""Adversary: buys dev cards whenever possible, plays knights ASAP, always robs opp's best tile."""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adv_common import *
class Agent:
    def __init__(self): self.rng = random.Random(1)
    def decide(self, obs, acts):
        opp = opp_of(obs)
        rob = [i for i, a in enumerate(acts) if a.action_type == AT.MOVE_ROBBER]
        if rob:
            def sc(i):
                c, v = acts[i].value[0], acts[i].value[1]
                return tile_prod_for(obs, c, opp) * 10 - tile_prod_for(obs, c, obs.me) * 10 + (1 if v == opp else 0)
            return max(rob, key=sc)
        for t in (AT.PLAY_KNIGHT_CARD, AT.BUY_DEVELOPMENT_CARD):
            for i, a in enumerate(acts):
                if a.action_type == t: return i
        return f_pick(obs, acts, self.rng)
