"""The simplest legal agent: a uniformly random legal move."""
import random


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions) -> int:
        return self.rng.randrange(len(playable_actions))
