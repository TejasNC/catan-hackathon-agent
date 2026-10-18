"""catanatron's ValueFunctionPlayer ("VF"), written against the agent interface.

It scores a position with a weighted sum of 13 features and plays the move leading to the
best-scoring position, one move ahead and no further. The weights are catanatron's, unchanged.
It calls obs.sample_world() once, so it guesses the opponent's unplayed development cards.
"""
import random

from catanatron.players.value import DEFAULT_WEIGHTS, get_value_fn

VALUE_FN = get_value_fn("base_fn", DEFAULT_WEIGHTS)


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions) -> int:
        world = obs.sample_world(self.rng)
        best_index, best_value = 0, None
        for index, action in enumerate(playable_actions):
            successor = world.copy()
            try:
                successor.execute(action)
            except Exception:
                continue
            value = VALUE_FN(successor, obs.me)
            if best_value is None or value > best_value:
                best_index, best_value = index, value
        return best_index
