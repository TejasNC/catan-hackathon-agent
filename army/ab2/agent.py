"""catanatron AlphaBetaPlayer (depth 2, pruning, F's value fn) behind the Agent interface. Zoo only."""
import random
from catanatron.players.minimax import AlphaBetaPlayer


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions):
        world = obs.sample_world(self.rng)
        p = AlphaBetaPlayer(obs.me, depth=2, prunning=True)
        a = p.decide(world, playable_actions)
        for i, b in enumerate(playable_actions):
            if b == a:
                return i
        return 0
