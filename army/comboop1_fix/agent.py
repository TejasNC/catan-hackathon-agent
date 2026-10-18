"""comboop1 + audit fix (never play Monopoly before rolling) + clock fix (turn-plan only with >= 0.9 s left).

Rollout audit (tools/audit.py, ~950 decisions): playing Monopoly before the roll cost +7.3 ± 5.7
win-rate points vs the alternatives (mostly: roll first). Rolling first only adds information, and a
pre-roll Monopoly swells our hand right before a possible 7. The underlying agent is unchanged.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cop1_agent import Agent as _Comboop1  # noqa: E402
from catanatron.models.enums import ActionType as AT  # noqa: E402


class Agent(_Comboop1):
    # Red-team finding: the turn-plan layer has no time limit and still ran at 0.45 s left (single
    # decisions up to 420 ms), so 2/500 very long games ran out of clock. Only plan with >= 0.9 s left;
    # below that the v5 fast path (worst decision ~120 ms) plays.
    MIN_CPU = 0.9

    def decide(self, obs, playable_actions):
        i = super().decide(obs, playable_actions)
        try:
            if playable_actions[i].action_type == AT.PLAY_MONOPOLY:
                for j, a in enumerate(playable_actions):
                    if a.action_type == AT.ROLL:
                        return j
        except Exception:
            pass
        return i
