"""In-process games between Agent classes (masked obs like the harness, no CPU clock).
Used for self-play statistics, tuning and data generation."""
import os, sys, random, importlib.util, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catan_eval
from catanatron.game import Game
from catanatron.models.player import Color, Player
from catanatron.models.actions import generate_playable_actions
from catan_eval.obs import Obs


def load_agent_class(path):
    spec = importlib.util.spec_from_file_location("ag_" + str(abs(hash(path))), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent


class Wrap(Player):
    def __init__(self, color, agent, mask_seed=0):
        super().__init__(color)
        self.agent = agent
        self.mrng = random.Random(mask_seed)
        self.hook = None

    def decide(self, game, playable_actions):
        if len(playable_actions) == 1:
            return playable_actions[0]
        o = Obs(game, self.color)
        # emulate the harness's masking without the copy (Obs.sample_world masks anyway)
        i = self.agent.decide(o, playable_actions)
        if self.hook:
            self.hook(game, self.color, playable_actions, i)
        return playable_actions[i]


def play(agent_a, agent_b, seed, a_first, hook=None):
    a = Wrap(Color.RED, agent_a, seed); b = Wrap(Color.BLUE, agent_b, seed + 1)
    a.hook = hook; b.hook = hook
    order = [a, b] if a_first else [b, a]
    random.seed(seed)
    g = Game(order, seed=seed)
    g.state.players = order; g.state.colors = tuple(p.color for p in order)
    g.state.color_to_index = {c: i for i, c in enumerate(g.state.colors)}
    g.state.buildings_by_color = {p.color: collections.defaultdict(list) for p in order}
    g.playable_actions = generate_playable_actions(g.state)
    random.seed(seed * 7919 + 13)
    w = g.play()
    return (None if w is None else (w == Color.RED)), g
