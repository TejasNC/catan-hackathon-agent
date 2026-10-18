"""combo (v5 + regime B + turn-plan lookahead) with op1's learned opening draft.

Mid-game: combo unchanged (cop1_core.py, cop1_base.py). Initial settlements: op1's draft search
(cop1_opener.py), which scores the final four settlements with a logistic P(win | opening) model
(open_model.json, 16k games) and predicts the opponent's picks with v5's draft (cop1_mbase.py).
The opening search stops at a CPU deadline and is skipped below 120 ms of clock.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cop1_core as CC  # noqa: E402
import cop1_mbase as MB  # noqa: E402
from cop1_opener import Opener  # noqa: E402
from catanatron.models.enums import SETTLEMENT  # noqa: E402


class Agent(CC.Agent):
    def __init__(self):
        super().__init__()
        self.opener = Opener(MB.Agent())

    def decide(self, obs, playable_actions):
        left = obs.cpu_left
        if len(playable_actions) > 1 and (left is None or left > 0.12):
            st = obs._game.state
            if st.is_initial_build_phase and st.current_prompt.name == "BUILD_INITIAL_SETTLEMENT":
                try:
                    me = obs.me
                    opp = st.colors[1 - st.color_to_index[me]]
                    c = MB.ctx_for(obs._game)
                    mine = list(st.buildings_by_color[me][SETTLEMENT])
                    theirs = list(st.buildings_by_color[opp][SETTLEMENT])
                    legal = {a.value: i for i, a in enumerate(playable_actions)}
                    node = self.opener.pick(
                        mine, theirs, set(st.board.board_buildable_ids), c, st.colors[0] == me, legal,
                        deadline=time.process_time() + (0.15 if left is None else min(0.15, (left - 0.08) / 2)))
                    if node in legal:
                        return legal[node]
                except Exception:
                    pass
        return super().decide(obs, playable_actions)
