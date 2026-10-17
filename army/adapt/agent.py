"""Search extensions on top of bot/agent.py (all behind flags; defaults reproduce v5).

TURN_K   : >0 -> turn-plan lookahead in PLAY_TURN. The top-K first actions (by the base 1-ply/2-step
           score, plus the base choice) are each extended greedily until END_TURN; the first action of
           the best finished plan is played.
REPLY    : True -> each finished plan's end state is scored by an expectimax over the opponent's next
           roll (11 dice sums, prob-weighted; on a 7 the opponent moves the robber to minimise our value).
MIN_CPU  : search only runs while obs.cpu_left (if clocked) is above this many seconds.
"""
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapt_base as _a
from catanatron.models.enums import Action, ActionRecord, ActionType as AT

DICE = [(s, (min(6, s - 1), s - min(6, s - 1)), (6 - abs(7 - s)) / 36.0) for s in range(2, 13)]
PLAN_TYPES = (AT.BUILD_CITY, AT.BUILD_SETTLEMENT, AT.BUY_DEVELOPMENT_CARD, AT.BUILD_ROAD,
              AT.MARITIME_TRADE, AT.PLAY_YEAR_OF_PLENTY, AT.PLAY_MONOPOLY, AT.PLAY_KNIGHT_CARD,
              AT.PLAY_ROAD_BUILDING, AT.MOVE_ROBBER, AT.END_TURN)


class _SearchAgent(_a.Agent):
    TURN_K = 0
    REPLY = False
    MAX_STEPS = 6
    MIN_CPU = 0.45
    MARGIN = 0.0

    def __init__(self, params=None):
        super().__init__(params)

    # greedy continuation of my own turn; returns the state where I end my turn (or None)
    def finish_turn(self, g, me):
        """Returns (end state, correction): correction keeps random outcomes (dev draws, steals) in
        expectation, as eval_action scores them, instead of on the sampled outcome."""
        corr = 0.0
        for _ in range(self.MAX_STEPS):
            st = g.state
            if st.current_color() != me or g.winning_color() is not None:
                return g, corr
            acts = [a for a in g.playable_actions if a.action_type in PLAN_TYPES]
            if not acts:
                return g, corr
            best = None
            for a in acts:
                if a.action_type == AT.END_TURN:
                    v, gb = self.V.value(g, me), None
                else:
                    v, gb = self.eval_action(g, a, me)
                    if gb is None:
                        continue
                if best is None or v > best[0]:
                    best = (v, gb, a)
            if best is None or best[1] is None:
                return g, corr
            g = best[1]
            corr += best[0] - self.V.value(g, me)
        return g, corr

    def reply_value(self, g, me):
        """Expected value over the opponent's roll after I end the turn in state g."""
        if g.winning_color() is not None:
            return self.V.value(g, me)
        try:
            g0 = g.copy()
            if g0.state.current_color() == me:
                g0.execute(Action(me, AT.END_TURN, None), validate_action=False)
            opp = g0.state.current_color()
            if opp == me:
                return self.V.value(g, me)
        except Exception:
            return self.V.value(g, me)
        V = self.V
        tot = 0.0
        for s, d, pr in DICE:
            try:
                g1 = g0.copy()
                ra = Action(opp, AT.ROLL, None)
                g1.execute(ra, validate_action=False, action_record=ActionRecord(ra, d))
                for _ in range(4):           # discards (either side): engine picks the cards
                    if g1.state.current_prompt.name != "DISCARD":
                        break
                    a = g1.playable_actions[0]
                    g1.execute(a, validate_action=False)
                if g1.state.current_prompt.name == "MOVE_ROBBER" and g1.state.current_color() == opp:
                    worst = None
                    for a in g1.playable_actions:
                        if a.action_type != AT.MOVE_ROBBER:
                            continue
                        g2 = g1.copy()
                        g2.execute(Action(opp, AT.MOVE_ROBBER, (a.value[0], None)), validate_action=False)
                        v = V.value(g2, me)
                        if a.value[1] is not None:
                            v -= V.p["card"] * (1 + V.p["opp_k"])
                        if worst is None or v < worst:
                            worst = v
                    v = worst if worst is not None else V.value(g1, me)
                else:
                    v = V.value(g1, me)
            except Exception:
                v = V.value(g0, me)
            tot += pr * v
        return tot

    def decide(self, obs, playable_actions):
        base = super().decide(obs, playable_actions)
        if not self.TURN_K or len(playable_actions) < 2:
            return base
        if obs.cpu_left is not None and obs.cpu_left < self.MIN_CPU:
            return base
        game = obs.sample_world(self.rng)
        st = game.state
        if st.is_initial_build_phase or st.current_prompt.name != "PLAY_TURN" or st.is_road_building:
            return base
        me = obs.me
        scored = []
        for idx, a in enumerate(playable_actions):
            if a.action_type not in PLAN_TYPES:
                continue
            if a.action_type == AT.END_TURN:
                scored.append((self.V.value(game, me), idx, game))
                continue
            v, g2 = self.eval_action(game, a, me)
            if g2 is not None:
                scored.append((v, idx, g2))
        if len(scored) < 2:
            return base
        scored.sort(key=lambda x: -x[0])
        cand = scored[:self.TURN_K]
        if base not in [c[1] for c in cand]:
            cand += [c for c in scored if c[1] == base]
        res = []
        for v, idx, g2 in cand:
            if playable_actions[idx].action_type == AT.END_TURN:
                gend, corr = game, 0.0
            else:
                gend, corr = self.finish_turn(g2, me)
                corr += v - self.V.value(g2, me)
            fv = corr + (self.reply_value(gend, me) if self.REPLY else self.V.value(gend, me))
            res.append((fv, idx))
        bres = [fv for fv, idx in res if idx == base]
        if not bres:
            return base
        bv = bres[0]
        fv, idx = max(res)
        return idx if fv > bv + self.MARGIN else base



REG = dict(regime=0.5, reg_fade=0.35, reg_dev=0.25)
#: Strategy arms. All are within noise of each other against F and in self-play; which one is best
#: depends on the opponent, so the agent learns it online (Thompson sampling, one arm per game).
ARMS = [
    ("combo", 3, dict(REG)),                                                   # regime B + turn plan
    ("v5", 0, {}),                                                             # submission #1
    ("block", 3, dict(REG, opp_k=1.0)),                                        # deny the opponent more
    ("race", 3, dict(REG, opp_k=0.55, knight_hand=0.2, army_lead=0.35)),      # race, contest army
]
PRIOR = [(4.0, 3.0), (2.0, 2.0), (2.0, 2.0), (2.0, 2.0)]   # Beta(wins, losses) pseudo-counts


class Agent(_SearchAgent):
    """Submission: opponent-adaptive. One process plays many games against the same opponent, so each
    game picks a strategy arm by Thompson sampling on that opponent's past results."""
    MARGIN = 0.05

    def __init__(self):
        super().__init__(dict(REG))
        self._base_p = dict(_a.DEFAULT)
        self._brng = random.Random(20261017)
        self._stats = [list(x) for x in PRIOR]
        self._arm = None
        self._sig = None
        self._nrec = 0
        self._won_last = False
        self._start_game()

    def _start_game(self):
        draws = [self._brng.betavariate(a, b) for a, b in self._stats]
        self._arm = max(range(len(ARMS)), key=lambda i: draws[i])
        name, k, params = ARMS[self._arm]
        self.TURN_K = k
        p = dict(self._base_p)
        p.update(params)
        self.V.p = p
        self._won_last = False

    def _check_new_game(self, obs):
        st = obs._game.state
        sig = tuple((t.resource, t.number) for t in st.board.map.land_tiles.values())
        n = len(st.action_records)
        if self._sig is not None and (sig != self._sig or n < self._nrec):
            w, l = self._stats[self._arm]
            self._stats[self._arm] = [w + (1 if self._won_last else 0), l + (0 if self._won_last else 1)]
            self._start_game()
        self._sig = sig
        self._nrec = n

    def decide(self, obs, playable_actions):
        try:
            self._check_new_game(obs)
        except Exception:
            pass
        idx = super().decide(obs, playable_actions)
        try:
            ps = obs._game.state.player_state
            if obs.my_actual_vps >= 7:
                g = obs.sample_world(self._brng)
                g.execute(playable_actions[idx], validate_action=False)
                i = g.state.color_to_index[obs.me]
                if g.state.player_state[f"P{i}_ACTUAL_VICTORY_POINTS"] >= 10:
                    self._won_last = True
        except Exception:
            pass
        return idx
