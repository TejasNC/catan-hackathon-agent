"""M (the affectionate-mayer bot) with a learned, opponent-aware opening draft (opener.py).

Optional parameter overrides (SPSA fitted against M) are read from params.json next to this file.
"""
import json
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import op1_mbase as MB  # noqa: E402
from op1_opener import Opener  # noqa: E402
from catanatron.models.enums import SETTLEMENT  # noqa: E402

DEFAULT = dict(MB.DEFAULT)
_P = os.path.join(_HERE, os.environ.get("OP1_PARAMS", "params.json"))
PARAMS = json.load(open(_P)) if os.path.exists(_P) else None
USE_OPENER = os.environ.get("OP1_OPENER", "1") == "1"


class Agent:
    def __init__(self, params=None):
        self.base = MB.Agent(params if params is not None else PARAMS)
        self.m_ref = MB.Agent()          # M's own weights, to predict M's picks exactly
        self.opener = Opener(self.m_ref)
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions):
        left = obs.cpu_left
        if USE_OPENER and len(playable_actions) > 1 and (left is None or left > 0.12):
            st = obs._game.state if hasattr(obs, "_game") else None
            if st is not None and st.is_initial_build_phase and \
                    st.current_prompt.name == "BUILD_INITIAL_SETTLEMENT":
                try:
                    me = obs.me
                    opp = st.colors[1 - st.color_to_index[me]]
                    c = MB.ctx_for(obs._game)
                    mine = list(st.buildings_by_color[me][SETTLEMENT])
                    theirs = list(st.buildings_by_color[opp][SETTLEMENT])
                    legal = {a.value: i for i, a in enumerate(playable_actions)}
                    node = self.opener.pick(mine, theirs, set(st.board.board_buildable_ids), c,
                                            st.colors[0] == me, legal,
                                            deadline=time.process_time() + (
                                                0.15 if left is None else min(0.15, (left - 0.08) / 2)))
                    if node in legal:
                        return legal[node]
                except Exception:
                    pass
        return self.base.decide(obs, playable_actions)
