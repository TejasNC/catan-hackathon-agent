"""v2: one-ply search on a single sampled world, scored by a hand-built value function in VP units.

Each decision samples one world consistent with the observation and scores every legal action by
applying it to a copy of that world. Four kinds of action get a little more than one ply:

  * BUY_DEVELOPMENT_CARD  the sampled card is replaced by the expected value of the unseen pile
  * MOVE_ROBBER + steal   played without the steal, plus a fixed bonus for one card moving to us
  * trades, Year of Plenty, Monopoly (top 6)   best of "stop here" and "then build" (<= 12 builds)
  * knight, Road Building the forced follow-up (robber move, free roads) is played greedily

When the clock runs low (cpu_left < 50 ms) every lookahead is skipped.
"""
import os
import random
import time

from catanatron.apply_action import apply_action
from catanatron.models.actions import generate_playable_actions
from catanatron.models.enums import Action, ActionType, CITY, SETTLEMENT

RESOURCES = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
RES_INDEX = {r: i for i, r in enumerate(RESOURCES)}
RES_WEIGHT = (1.0, 1.0, 0.8, 1.1, 1.1)
PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}

DEV_DECK = {"KNIGHT": 14, "VICTORY_POINT": 5, "ROAD_BUILDING": 2,
            "YEAR_OF_PLENTY": 2, "MONOPOLY": 2}
# What one unplayed card of each type is worth in V. A VP card's 1.0 lives in the VP term.
DEV_VALUE = {"KNIGHT": 0.25, "VICTORY_POINT": 1.0, "ROAD_BUILDING": 0.20,
             "YEAR_OF_PLENTY": 0.20, "MONOPOLY": 0.20}
OPP_DEV_VALUE = 0.56 * 0.25 + 0.24 * 0.20 + 0.2 * 1.0

OPP_WEIGHT = 0.9
STEAL_BONUS = 0.045 * (1 + OPP_WEIGHT)     # +1 card for me, -1 card for them
WIN_BONUS = 1000.0

AT = ActionType
LOOKAHEAD_TYPES = (AT.MARITIME_TRADE, AT.PLAY_YEAR_OF_PLENTY, AT.PLAY_MONOPOLY)
FOLLOWUP_ORDER = {AT.BUILD_CITY: 0, AT.BUILD_SETTLEMENT: 1, AT.BUY_DEVELOPMENT_CARD: 2,
                  AT.BUILD_ROAD: 3}
TOP_K = 6
MAX_FOLLOWUPS = 12
LOOKAHEAD_GUARD_S = 0.050
# Trade lookahead stops once a decision has used this much CPU, or a quarter of what the clock has
# left above the 50 ms guard. Simulating a road runs the engine's longest-road DFS, which gets slow
# on big road networks: unbounded, 6 trades x 12 road follow-ups cost 150 ms late in some games.
# Trades are examined best first, so the cut drops only the least promising ones.
LOOKAHEAD_BUDGET_S = 0.025
# Below this, even one greedy ply may not fit: a plain greedy decision costs about 0.15-0.3 ms per
# legal action here, and after the 1.5 s ceiling the clock no longer grows with the game.
PANIC_GUARD_S = 0.010
PANIC_PER_ACTION_S = 0.0005

# Set CATAN_AGENT_STRICT=1 to let exceptions escape (testing). Otherwise a failure inside the
# search falls back to a safe move, so a bug costs a move, never a fault.
STRICT = os.environ.get("CATAN_AGENT_STRICT") == "1"


def _clip(x, lim):
    return lim if x > lim else (-lim if x < -lim else x)


def _top2(values):
    a = b = 0.0
    for v in values:
        if v > a:
            a, b = v, a
        elif v > b:
            b = v
    return a + b


class MapInfo:
    """Static per-board lookups: tile production per node, node adjacency, ports."""

    def __init__(self, board):
        m = board.map
        coord_of = {id(t): c for c, t in m.land_tiles.items()}
        self.node_tiles = {}
        self.node_pips = {}
        for node, tiles in m.adjacent_tiles.items():
            lst = [(RES_INDEX[t.resource], PIPS[t.number], coord_of[id(t)])
                   for t in tiles if t.resource is not None]
            self.node_tiles[node] = lst
            self.node_pips[node] = sum(p for _, p, _ in lst)
        g = board.buildable_subgraph
        self.nbrs = {n: tuple(g.neighbors(n)) for n in g.nodes}
        self.port_of = {}                       # node -> resource index, or -1 for 3:1
        for res, nodes in m.port_nodes.items():
            for n in nodes:
                self.port_of[n] = -1 if res is None else RES_INDEX[res]


class Agent:
    def __init__(self):
        self.rng = random.Random(0)
        self.info = None
        self.info_key = None

    # ----------------------------------------------------------------------------- value
    def side(self, state, color, mine, phi):
        """S(p) of the spec. Returns (S, knights played, longest road length)."""
        info = self.info
        ps = state.player_state
        k = "P%d_" % state.color_to_index[color]
        board = state.board
        bld = state.buildings_by_color.get(color)
        settles = bld.get(SETTLEMENT, ()) if bld else ()
        cities = bld.get(CITY, ()) if bld else ()
        robber = board.robber_coordinate
        node_tiles = info.node_tiles

        # Production, robber tile excluded, cities double.
        prod = [0, 0, 0, 0, 0]
        for n in settles:
            for r, p, c in node_tiles[n]:
                if c != robber:
                    prod[r] += p
        for n in cities:
            for r, p, c in node_tiles[n]:
                if c != robber:
                    prod[r] += 2 * p
        w_prod = 0.11 * (1 - phi) + 0.04 * phi
        s = ps[k + "ACTUAL_VICTORY_POINTS"] if mine else ps[k + "VICTORY_POINTS"]
        s += w_prod * (prod[0] * RES_WEIGHT[0] + prod[1] * RES_WEIGHT[1] + prod[2] * RES_WEIGHT[2]
                       + prod[3] * RES_WEIGHT[3] + prod[4] * RES_WEIGHT[4])
        s += 0.12 * (1 - phi) * ((prod[0] > 0) + (prod[1] > 0) + (prod[2] > 0)
                                 + (prod[3] > 0) + (prod[4] > 0))

        # Expansion: spots on the network now (zero), one road away (l1), two roads away (l2).
        buildable = board.board_buildable_ids
        comps = board.connected_components.get(color)
        zero = set().union(*comps) if comps else set()
        node_pips = info.node_pips
        spots0 = [node_pips[n] for n in zero if n in buildable]
        n_spots = len(spots0)
        settlements_left = ps[k + "SETTLEMENTS_AVAILABLE"] > 0
        if settlements_left:
            roads = board.roads
            buildings = board.buildings
            nbrs = info.nbrs
            l1 = set()
            for n in zero:
                b = buildings.get(n)
                if b is not None and b[0] != color:
                    continue                    # an enemy building cuts the path
                for nb in nbrs[n]:
                    if nb not in zero and (n, nb) not in roads:
                        l1.add(nb)
            l2 = set()
            for n in l1:
                b = buildings.get(n)
                if b is not None and b[0] != color:
                    continue
                for nb in nbrs[n]:
                    if nb not in zero and nb not in l1 and (n, nb) not in roads:
                        l2.add(nb)
            e1 = _top2(spots0 + [0.8 * node_pips[n] for n in l1 if n in buildable])
            e2 = _top2([node_pips[n] for n in l2 if n in buildable])
            s += (1 - 0.5 * phi) * (0.020 * e1 + 0.008 * e2 + 0.06 * min(n_spots, 2))

        # Hand.
        wood = ps[k + "WOOD_IN_HAND"]
        brick = ps[k + "BRICK_IN_HAND"]
        sheep = ps[k + "SHEEP_IN_HAND"]
        wheat = ps[k + "WHEAT_IN_HAND"]
        ore = ps[k + "ORE_IN_HAND"]
        cards = wood + brick + sheep + wheat + ore
        s += 0.045 * min(cards, 8)
        if cards > 7:
            s -= 0.18 * (cards // 2)

        # Build readiness.
        if wood and brick and sheep and wheat and n_spots and settlements_left:
            s += 0.30
        if wheat >= 2 and ore >= 3 and settles and ps[k + "CITIES_AVAILABLE"] > 0:
            s += 0.35
        if sheep and wheat and ore and state.development_listdeck:
            s += 0.10

        # Partial progress, as in F.
        d_city = (max(2 - wheat, 0) + max(3 - ore, 0)) / 5.0
        d_settle = ((wood < 1) + (brick < 1) + (sheep < 1) + (wheat < 1)) / 4.0
        s += 0.10 * (2 - d_city - d_settle) / 2

        # Unplayed development cards.
        if mine:
            s += 0.25 * ps[k + "KNIGHT_IN_HAND"] + 0.20 * (
                ps[k + "ROAD_BUILDING_IN_HAND"] + ps[k + "YEAR_OF_PLENTY_IN_HAND"]
                + ps[k + "MONOPOLY_IN_HAND"])
        else:
            s += OPP_DEV_VALUE * (
                ps[k + "KNIGHT_IN_HAND"] + ps[k + "VICTORY_POINT_IN_HAND"]
                + ps[k + "ROAD_BUILDING_IN_HAND"] + ps[k + "YEAR_OF_PLENTY_IN_HAND"]
                + ps[k + "MONOPOLY_IN_HAND"])

        knights = ps[k + "PLAYED_KNIGHT"]
        s += 0.22 * min(knights, 4)

        # Ports.
        port_of = info.port_of
        has_generic = False
        port_res = set()
        for n in settles:
            r = port_of.get(n)
            if r is not None:
                if r < 0:
                    has_generic = True
                else:
                    port_res.add(r)
        for n in cities:
            r = port_of.get(n)
            if r is not None:
                if r < 0:
                    has_generic = True
                else:
                    port_res.add(r)
        if has_generic:
            s += 0.20 * (1 - 0.5 * phi)
        for r in port_res:
            s += 0.012 * prod[r]

        road = ps[k + "LONGEST_ROAD_LENGTH"]
        s += 0.05 * min(road, 10)
        return s, knights, road

    def value(self, state, phi, win_bonus=True):
        s_me, k_me, r_me = self.side(state, self.me, True, phi)
        s_op, k_op, r_op = self.side(state, self.opp, False, phi)
        v = (s_me - OPP_WEIGHT * s_op + 0.15 * _clip(k_me - k_op, 2)
             + 0.25 * _clip(r_me - r_op, 2) / 2)
        if win_bonus and state.player_state[self.me_key + "ACTUAL_VICTORY_POINTS"] >= self.vps:
            v += WIN_BONUS
        return v

    # ----------------------------------------------------------------------------- scoring
    def score(self, state, action, phi):
        """Value of one action, with the dev-card and robber-steal rules. Returns (v, state)."""
        t = action.action_type
        if t == AT.ROLL:
            return self.value(state, phi), None
        s = state.copy()
        if t == AT.BUY_DEVELOPMENT_CARD:
            card = s.development_listdeck[-1]       # apply_action pops the top card
            apply_action(s, action)
            return self.value(s, phi, win_bonus=False) - DEV_VALUE[card] + self.dev_ev, s
        if t == AT.MOVE_ROBBER:
            coord, victim = action.value
            apply_action(s, Action(action.color, AT.MOVE_ROBBER, (coord, None)))
            return self.value(s, phi) + (STEAL_BONUS if victim is not None else 0.0), s
        apply_action(s, action)
        return self.value(s, phi), s

    def best_of(self, state, actions, phi, deadline=None):
        best_v, best_s = None, None
        for a in actions:
            if deadline is not None and best_v is not None and time.process_time() > deadline:
                break
            v, s = self.score(state, a, phi)
            if best_v is None or v > best_v:
                best_v, best_s = v, s
        return best_v, best_s

    def after_knight(self, s, phi):
        """The knight's forced robber move, played greedily."""
        if s.current_prompt.name != "MOVE_ROBBER":
            return None
        v, _ = self.best_of(s, generate_playable_actions(s), phi)
        return v

    def after_road_building(self, s, phi):
        """Up to two free roads, each chosen greedily."""
        for _ in range(2):
            if not s.is_road_building:
                break
            roads = [a for a in generate_playable_actions(s) if a.action_type == AT.BUILD_ROAD]
            if not roads:
                break
            _, s = self.best_of(s, roads, phi)
        return self.value(s, phi)

    def after_build(self, s, phi, deadline=None):
        """Best value after one follow-up build (city, settlement, dev card or road)."""
        follow = [a for a in generate_playable_actions(s) if a.action_type in FOLLOWUP_ORDER]
        if not follow:
            return None
        follow.sort(key=lambda a: FOLLOWUP_ORDER[a.action_type])
        v, _ = self.best_of(s, follow[:MAX_FOLLOWUPS], phi, deadline)
        return v

    # ----------------------------------------------------------------------------- decide
    def setup(self, obs, world):
        st = world.state
        self.me = obs.me
        self.opp = st.colors[1 - st.color_to_index[obs.me]]
        self.me_key = "P%d_" % st.color_to_index[obs.me]
        self.vps = world.vps_to_win
        key = tuple((c, t.resource, t.number) for c, t in st.board.map.land_tiles.items())
        if key != self.info_key:
            self.info = MapInfo(st.board)
            self.info_key = key
        unseen = {d: DEV_DECK[d] - obs.my_devs[d] - obs.played_devs["me"][d]
                  - obs.played_devs["opp"][d] for d in DEV_DECK}
        total = sum(unseen.values())
        self.dev_ev = (sum(unseen[d] * DEV_VALUE[d] for d in DEV_DECK) / total) if total > 0 else 0.0
        vp = max(obs.my_public_vps, obs.opp_public_vps)
        return min(max((vp - 2) / 7.0, 0.0), 1.0)

    def decide(self, obs, playable_actions):
        t0 = time.process_time()
        cpu_left = obs.cpu_left
        n = len(playable_actions)
        if cpu_left is not None and cpu_left < PANIC_GUARD_S + PANIC_PER_ACTION_S * n:
            return self.panic(playable_actions)
        if cpu_left is None:
            deadline = t0 + LOOKAHEAD_BUDGET_S
        else:
            deadline = t0 + min(LOOKAHEAD_BUDGET_S, (cpu_left - LOOKAHEAD_GUARD_S) / 4)
        try:
            return self.search(obs, playable_actions,
                               lookahead=cpu_left is None or cpu_left >= LOOKAHEAD_GUARD_S,
                               deadline=deadline)
        except Exception:
            if STRICT:
                raise
            return self.panic(playable_actions)

    def search(self, obs, actions, lookahead, deadline=None):
        world = obs.sample_world(self.rng)
        phi = self.setup(obs, world)
        root = world.state

        scores = []
        states = []
        for a in actions:
            try:
                v, s = self.score(root, a, phi)
            except Exception:
                if STRICT:
                    raise
                v, s = float("-inf"), None
            scores.append(v)
            states.append(s)

        if lookahead:
            # Forced follow-ups first: they are cheap and must never be cut by the budget.
            for i, a in enumerate(actions):
                if states[i] is None:
                    continue
                if a.action_type == AT.PLAY_KNIGHT_CARD:
                    v = self.after_knight(states[i], phi)
                    if v is not None:
                        scores[i] = v
                elif a.action_type == AT.PLAY_ROAD_BUILDING:
                    scores[i] = self.after_road_building(states[i], phi)
            cand = [i for i, a in enumerate(actions)
                    if a.action_type in LOOKAHEAD_TYPES and states[i] is not None]
            cand.sort(key=lambda i: -scores[i])
            for i in cand[:TOP_K]:
                if deadline is not None and time.process_time() > deadline:
                    break
                v = self.after_build(states[i], phi, deadline)
                if v is not None and v > scores[i]:
                    scores[i] = v

        best = 0
        for i in range(1, len(scores)):
            if scores[i] > scores[best]:
                best = i
        return best

    @staticmethod
    def panic(actions):
        """Almost free: roll, then build the obvious thing, then end the turn."""
        order = (AT.ROLL, AT.BUILD_CITY, AT.BUILD_SETTLEMENT, AT.END_TURN)
        for t in order:
            for i, a in enumerate(actions):
                if a.action_type == t:
                    return i
        return 0
