"""CPU per decision of agent_v2, by decision kind, against F, in one process.

    PYTHONHASHSEED=0 python tests/profile_agent_v2.py [games]

The harness charges CPU per game against min(300 ms + 12.5 ms x decisions, 1500 ms). This prints
where the time goes and the tightest point of the clock in any game (lowest cpu_left seen).
"""
import os
import random
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent_v2"))
sys.path.insert(0, os.path.join(ROOT, "examples"))

import catan_kit  # noqa: F401,E402
from catan_kit.obs import Obs, masked_copy  # noqa: E402
from catan_kit import match  # noqa: E402
from catanatron.game import Game  # noqa: E402
from catanatron.models.player import Color, Player  # noqa: E402

import agent as v2  # noqa: E402
import f_agent  # noqa: E402


class Seat(Player):
    def __init__(self, color, agent, timed):
        super().__init__(color)
        self.agent, self.timed = agent, timed
        self.mask_rng = random.Random(color.value.__hash__())

    def begin(self):
        self.used = 0.0
        self.calls = 0
        self.min_left = float("inf")

    def decide(self, game, actions):
        actions = list(actions)
        if len(actions) == 1:
            return actions[0]
        obs = Obs(masked_copy(game, self.color, self.mask_rng), self.color)
        allow = min(match.CPU_BASE_S + (self.calls + 1) * match.CPU_PER_DECISION_S, match.CPU_MAX_S)
        obs.cpu_left = allow - self.used
        self.calls += 1
        t0 = time.process_time()
        i = self.agent.decide(obs, actions)
        dt = time.process_time() - t0
        self.used += dt
        if self.timed:
            self.min_left = min(self.min_left, obs.cpu_left - dt)
            kind = game.state.current_prompt.name
            if kind == "PLAY_TURN":
                kind += "/rolled" if any(a.action_type.name == "END_TURN" for a in actions) \
                    else "/pre-roll"
            STATS[kind].append(dt)
            NACT[kind].append(len(actions))
        return actions[i]


STATS = defaultdict(list)
NACT = defaultdict(list)


def main(games=40):
    me = Seat(Color.RED, v2.Agent(), True)
    opp = Seat(Color.BLUE, f_agent.Agent(), False)
    per_game, worst_left, wins = [], [], 0
    for g in range(games):
        seats = [me, opp] if g % 2 == 0 else [opp, me]
        random.seed(777 + g // 2)
        game = Game(seats, seed=777 + g // 2)
        random.seed(match.dice_seed(777 + g // 2, g // 2))
        me.begin()
        opp.begin()
        wins += game.play() == Color.RED
        per_game.append(me.used)
        worst_left.append(me.min_left)
    print(f"games {games}, wins {wins}")
    print(f"CPU per game: mean {1000*sum(per_game)/games:.0f} ms, max {1000*max(per_game):.0f} ms")
    print(f"lowest cpu_left after a decision: {1000*min(worst_left):.0f} ms")
    print(f"{'decision':22s} {'n':>6s} {'acts':>5s} {'mean ms':>8s} {'p99 ms':>8s} {'max ms':>8s}")
    for k, v in sorted(STATS.items(), key=lambda kv: -sum(kv[1])):
        v = sorted(v)
        print(f"{k:22s} {len(v):6d} {sum(NACT[k])/len(v):5.1f} {1000*sum(v)/len(v):8.2f} "
              f"{1000*v[int(0.99*(len(v)-1))]:8.2f} {1000*v[-1]:8.2f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
