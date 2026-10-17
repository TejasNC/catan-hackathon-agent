"""Adversary: always builds roads when possible, choosing roads nearest opp buildings/roads (cutting)."""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adv_common import *
class Agent:
    def __init__(self): self.rng = random.Random(2)
    def decide(self, obs, acts):
        roads = [i for i, a in enumerate(acts) if a.action_type == AT.BUILD_ROAD]
        st = obs._game.state
        if roads and not st.is_initial_build_phase:
            opp = opp_of(obs)
            b = st.board
            onodes = set()
            for e, c in b.roads.items():
                if c == opp: onodes.update(e)
            for n, bl in b.buildings.items():
                if bl[0] == opp: onodes.add(n)
            def sc(i):
                e = acts[i].value
                return sum(1 for n in e if n in onodes)
            best = max(roads, key=sc)
            return best
        # settle/city first otherwise F
        return f_pick(obs, acts, self.rng)
