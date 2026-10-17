import random
from catanatron.players.weighted_random import WeightedRandomPlayer


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions):
        p = WeightedRandomPlayer(obs.me)
        a = p.decide(obs.sample_world(self.rng), playable_actions)
        return next((i for i, b in enumerate(playable_actions) if b == a), 0)
