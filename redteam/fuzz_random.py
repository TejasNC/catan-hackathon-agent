"""Random opponent that prefers weird actions (plays devs, trades) for state fuzzing."""
import random
from catanatron.models.enums import ActionType as AT
class Agent:
    def __init__(self): self.rng = random.Random(7)
    def decide(self, obs, acts):
        pref = [i for i, a in enumerate(acts) if a.action_type != AT.END_TURN]
        if pref and self.rng.random() < 0.8: return self.rng.choice(pref)
        return self.rng.randrange(len(acts))
