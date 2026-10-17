"""Tests for agent_v2.

    PYTHONHASHSEED=0 python -m unittest tests.test_agent_v2 -v

1. A slow reference implementation of the spec's S(p), written independently of the agent through
   different engine APIs, is compared with the agent's fast one on states from real games.
2. Each decision rule of the spec (dev-card expectation, robber steal, trade lookahead, knight and
   Road Building follow-ups, clock guard) is checked on a constructed position.
3. A fuzz run calls decide() at every decision of many games and checks the index is legal.
"""
import os
import random
import sys
import unittest

os.environ["CATAN_AGENT_STRICT"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent_v2"))

import catan_kit  # noqa: F401,E402  determinism patch
from catan_kit.obs import Obs, masked_copy  # noqa: E402
from catanatron.game import Game  # noqa: E402
from catanatron.models.board import STATIC_GRAPH  # noqa: E402
from catanatron.models.enums import Action, ActionType, CITY, SETTLEMENT  # noqa: E402
from catanatron.models.map import number_probability  # noqa: E402
from catanatron.models.player import Color, RandomPlayer  # noqa: E402

import agent as agent_mod  # noqa: E402

AT = ActionType
RES = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
W = dict(zip(RES, (1.0, 1.0, 0.8, 1.1, 1.1)))


# --------------------------------------------------------------------------- reference S(p)
def ref_pips(tile):
    return round(number_probability(tile.number) * 36)


def ref_spot_pips(m, node):
    return sum(ref_pips(t) for t in m.adjacent_tiles[node] if t.resource is not None)


def ref_side(state, color, mine, phi):
    """S(p), term by term from the spec, deliberately using other engine paths than the agent."""
    ps = state.player_state
    i = state.color_to_index[color]
    k = f"P{i}_"
    board = state.board
    m = board.map
    robber_tile = m.land_tiles[board.robber_coordinate]
    settles = list(state.buildings_by_color[color][SETTLEMENT])
    cities = list(state.buildings_by_color[color][CITY])
    terms = {}

    terms["vp"] = ps[k + "ACTUAL_VICTORY_POINTS"] if mine else ps[k + "VICTORY_POINTS"]

    prod = {r: 0 for r in RES}
    for mult, nodes in ((1, settles), (2, cities)):
        for n in nodes:
            for t in m.adjacent_tiles[n]:
                if t.resource is not None and t is not robber_tile:
                    prod[t.resource] += mult * ref_pips(t)
    w_prod = 0.11 * (1 - phi) + 0.04 * phi
    terms["production"] = w_prod * sum(prod[r] * W[r] for r in RES)
    terms["diversity"] = 0.12 * (1 - phi) * sum(1 for r in RES if prod[r] > 0)

    # Expansion, by explicit BFS over the static graph.
    legal = set(board.buildable_node_ids(color, initial_build_phase=True))  # distance rule only
    network = set()
    for comp in board.connected_components[color]:
        network |= comp
    spots_now = [n for n in network if n in legal]
    left = ps[k + "SETTLEMENTS_AVAILABLE"] > 0
    if left:
        def passable(n):
            b = board.buildings.get(n)
            return b is None or b[0] == color

        def step(frontier, seen):
            out = set()
            for n in frontier:
                if not passable(n):
                    continue
                for nb in STATIC_GRAPH.neighbors(n):
                    if nb not in m.land_nodes or nb in seen:
                        continue
                    if board.roads.get((n, nb)) is not None:
                        continue
                    out.add(nb)
            return out
        one = step(network, network)
        two = step(one, network | one)
        e1_vals = [ref_spot_pips(m, n) for n in spots_now] + \
                  [0.8 * ref_spot_pips(m, n) for n in one if n in legal]
        e2_vals = [ref_spot_pips(m, n) for n in two if n in legal]
        e1 = sum(sorted(e1_vals, reverse=True)[:2])
        e2 = sum(sorted(e2_vals, reverse=True)[:2])
        terms["expansion"] = (1 - 0.5 * phi) * (0.020 * e1 + 0.008 * e2
                                                + 0.06 * min(len(spots_now), 2))

    hand = {r: ps[f"{k}{r}_IN_HAND"] for r in RES}
    cards = sum(hand.values())
    terms["hand"] = 0.045 * min(cards, 8) - (0.18 * (cards // 2) if cards > 7 else 0)

    ready = 0.0
    if all(hand[r] >= 1 for r in ("WOOD", "BRICK", "SHEEP", "WHEAT")) and spots_now and left:
        ready += 0.30
    if hand["WHEAT"] >= 2 and hand["ORE"] >= 3 and settles and ps[k + "CITIES_AVAILABLE"] > 0:
        ready += 0.35
    if hand["SHEEP"] >= 1 and hand["WHEAT"] >= 1 and hand["ORE"] >= 1 \
            and len(state.development_listdeck) > 0:
        ready += 0.10
    terms["ready"] = ready

    d_city = (max(2 - hand["WHEAT"], 0) + max(3 - hand["ORE"], 0)) / 5
    d_settle = sum(max(1 - hand[r], 0) for r in ("WOOD", "BRICK", "SHEEP", "WHEAT")) / 4
    terms["partial"] = 0.10 * (2 - d_city - d_settle) / 2

    devs = {d: ps[f"{k}{d}_IN_HAND"] for d in agent_mod.DEV_DECK}
    if mine:
        terms["devs"] = 0.25 * devs["KNIGHT"] + 0.20 * (
            devs["ROAD_BUILDING"] + devs["YEAR_OF_PLENTY"] + devs["MONOPOLY"])
    else:
        terms["devs"] = (0.56 * 0.25 + 0.24 * 0.20 + 0.2 * 1.0) * sum(devs.values())

    knights = ps[k + "PLAYED_KNIGHT"]
    terms["knights"] = 0.22 * min(knights, 4)

    ports = board.get_player_port_resources(color)
    terms["ports"] = (0.20 * (1 - 0.5 * phi) if None in ports else 0.0) + \
        sum(0.012 * prod[r] for r in ports if r is not None)

    road = ps[k + "LONGEST_ROAD_LENGTH"]
    terms["road"] = 0.05 * min(road, 10)
    return sum(terms.values()), knights, road, terms


def ref_value(state, me, phi):
    opp = [c for c in state.colors if c != me][0]
    s_me, k_me, r_me, _ = ref_side(state, me, True, phi)
    s_op, k_op, r_op, _ = ref_side(state, opp, False, phi)
    clip = lambda x: max(-2, min(2, x))  # noqa: E731
    return s_me - 0.9 * s_op + 0.15 * clip(k_me - k_op) + 0.25 * clip(r_me - r_op) / 2


# --------------------------------------------------------------------------- helpers
def new_game(seed):
    random.seed(seed)
    return Game([RandomPlayer(Color.RED), RandomPlayer(Color.BLUE)], seed=seed)


def ready_agent(game, color, cpu_left=None):
    """An agent primed on `game` from `color`'s seat, and the Obs it would see."""
    obs = Obs(game, color)
    obs.cpu_left = cpu_left
    a = agent_mod.Agent()
    world = obs.sample_world(a.rng)
    phi = a.setup(obs, world)
    return a, obs, phi


def random_states(n_games=12, every=7, seed0=500):
    """(game, color) pairs from random play, sampled every few plies, initial phase included."""
    out = []
    for g in range(n_games):
        game = new_game(seed0 + g)
        ply = 0
        while game.winning_color() is None and game.state.num_turns < 400:
            if ply % every == 0:
                out.append((game.copy(), game.state.current_color()))
            game.play_tick()
            ply += 1
    return out


def to_play_turn(game):
    """Advance a game with random play until it is someone's post-roll main phase."""
    while not (not game.state.is_initial_build_phase and game.state.current_prompt.name == "PLAY_TURN"
               and game.state.player_state[f"P{game.state.current_player_index}_HAS_ROLLED"]):
        game.play_tick()
    return game


def set_hand(state, color, **cards):
    k = f"P{state.color_to_index[color]}_"
    for r in RES:
        n = cards.get(r, 0)
        delta = n - state.player_state[f"{k}{r}_IN_HAND"]
        state.player_state[f"{k}{r}_IN_HAND"] = n
        state.resource_freqdeck[RES.index(r)] -= delta


# --------------------------------------------------------------------------- tests
class ValueFunctionTests(unittest.TestCase):
    def test_matches_reference_on_real_states(self):
        """Fast S(p) == reference S(p), both seats, every phase, many states."""
        states = random_states()
        self.assertGreater(len(states), 300)
        for game, color in states:
            a, obs, phi = ready_agent(game, color)
            st = game.state
            for c in st.colors:
                for mine in (True, False):
                    fast = a.side(st, c, mine, phi)
                    ref = ref_side(st, c, mine, phi)
                    self.assertAlmostEqual(fast[0], ref[0], places=9, msg=str(ref[3]))
                    self.assertEqual(fast[1:], ref[1:3])
            a.me, a.opp = color, [c for c in st.colors if c != color][0]
            self.assertAlmostEqual(a.value(st, phi, win_bonus=False),
                                   ref_value(st, color, phi), places=9)

    def test_hand_penalty(self):
        """7 -> 8 cards: +0.045 for the card, -0.18*4 for the discard risk."""
        game = to_play_turn(new_game(7))
        me = game.state.current_color()
        a, _, phi = ready_agent(game, me)
        set_hand(game.state, me, WOOD=7)
        v7 = a.side(game.state, me, True, phi)[0]
        set_hand(game.state, me, WOOD=8)
        v8 = a.side(game.state, me, True, phi)[0]
        self.assertAlmostEqual(v8 - v7, 0.045 - 0.18 * 4)

    def test_phase(self):
        game = new_game(3)
        me = game.state.colors[0]
        _, _, phi = ready_agent(game, me)
        self.assertEqual(phi, 0.0)
        game.state.player_state["P1_VICTORY_POINTS"] = 9
        _, _, phi = ready_agent(game, me)
        self.assertEqual(phi, 1.0)
        game.state.player_state["P1_VICTORY_POINTS"] = 5
        _, _, phi = ready_agent(game, me)
        self.assertAlmostEqual(phi, 3 / 7)

    def test_production_excludes_robber_and_doubles_cities(self):
        game = to_play_turn(new_game(11))
        st = game.state
        me = st.current_color()
        a, _, phi = ready_agent(game, me)
        node = st.buildings_by_color[me][SETTLEMENT][0]
        base = a.side(st, me, True, phi)[0]
        # Robber onto a producing tile of that settlement lowers S.
        tile = next(t for t in st.board.map.adjacent_tiles[node] if t.resource is not None)
        coord = next(c for c, t in st.board.map.land_tiles.items() if t is tile)
        old = st.board.robber_coordinate
        st.board.robber_coordinate = coord
        self.assertLess(a.side(st, me, True, phi)[0], base)
        st.board.robber_coordinate = old
        self.assertAlmostEqual(a.side(st, me, True, phi)[0], base)


class DecisionRuleTests(unittest.TestCase):
    def test_dev_ev_fresh_deck(self):
        a, _, _ = ready_agent(new_game(1), Color.RED)
        self.assertAlmostEqual(a.dev_ev, (14 * 0.25 + 5 * 1.0 + 6 * 0.20) / 25)

    def test_dev_buy_score_does_not_depend_on_sampled_card(self):
        game = to_play_turn(new_game(21))
        st = game.state
        me = st.current_color()
        set_hand(st, me, SHEEP=1, WHEAT=1, ORE=1)
        a, _, phi = ready_agent(game, me)
        a.me, a.opp = me, [c for c in st.colors if c != me][0]
        buy = Action(me, AT.BUY_DEVELOPMENT_CARD, None)
        scores = set()
        for card in agent_mod.DEV_DECK:
            s = st.copy()
            s.development_listdeck[-1] = card
            scores.add(round(a.score(s, buy, phi)[0], 9))
        self.assertEqual(len(scores), 1)

    def test_steal_bonus(self):
        game = new_game(5)
        while game.state.is_initial_build_phase:
            game.play_tick()
        st = game.state
        me = st.current_color()
        opp = [c for c in st.colors if c != me][0]
        a, _, phi = ready_agent(game, me)
        node = st.buildings_by_color[opp][SETTLEMENT][0]
        tile = next(t for t in st.board.map.adjacent_tiles[node] if t.resource is not None)
        coord = next(c for c, t in st.board.map.land_tiles.items() if t is tile)
        with_steal = a.score(st, Action(me, AT.MOVE_ROBBER, (coord, opp)), phi)[0]
        without = a.score(st, Action(me, AT.MOVE_ROBBER, (coord, None)), phi)[0]
        self.assertAlmostEqual(with_steal - without, 0.045 * 1.9)

    def test_trade_lookahead_finds_city(self):
        """4 wood -> 1 ore completes a city; the trade should be taken over ending the turn."""
        game = to_play_turn(new_game(31))
        st = game.state
        me = st.current_color()
        set_hand(st, me, WOOD=4, WHEAT=2, ORE=2)
        game.playable_actions = __import__(
            "catanatron.models.actions", fromlist=["x"]).generate_playable_actions(st)
        acts = game.playable_actions
        a, obs, _ = ready_agent(game, me)
        i = a.decide(obs, acts)
        self.assertEqual(acts[i].action_type, AT.MARITIME_TRADE, acts)
        self.assertEqual(acts[i].value[-1], "ORE")

    def test_road_building_follow_up_places_two_roads(self):
        game = to_play_turn(new_game(41))
        st = game.state
        me = st.current_color()
        k = f"P{st.color_to_index[me]}_"
        a, _, phi = ready_agent(game, me)
        s = st.copy()
        s.player_state[k + "ROAD_BUILDING_IN_HAND"] = 1
        s.player_state[k + "ROAD_BUILDING_OWNED_AT_START"] = True
        roads_before = s.player_state[k + "ROADS_AVAILABLE"]
        v, s2 = a.score(s, Action(me, AT.PLAY_ROAD_BUILDING, None), phi)
        captured = {}
        orig = a.best_of

        def spy(state, actions, phi_):
            r = orig(state, actions, phi_)
            captured["last"] = r[1]
            return r
        a.best_of = spy
        a.after_road_building(s2, phi)
        self.assertEqual(captured["last"].player_state[k + "ROADS_AVAILABLE"], roads_before - 2)

    def test_knight_follow_up_moves_robber_off_own_tile(self):
        game = new_game(51)
        while game.state.is_initial_build_phase:
            game.play_tick()
        st = game.state
        me = st.current_color()
        k = f"P{st.color_to_index[me]}_"
        node = st.buildings_by_color[me][SETTLEMENT][0]
        best_tile = max((t for t in st.board.map.adjacent_tiles[node] if t.resource),
                        key=ref_pips)
        st.board.robber_coordinate = next(c for c, t in st.board.map.land_tiles.items()
                                          if t is best_tile)
        st.player_state[k + "KNIGHT_IN_HAND"] = 1
        st.player_state[k + "KNIGHT_OWNED_AT_START"] = True
        from catanatron.models.actions import generate_playable_actions
        game.playable_actions = generate_playable_actions(st)
        acts = game.playable_actions
        types = [x.action_type for x in acts]
        self.assertIn(AT.PLAY_KNIGHT_CARD, types)
        a, obs, phi = ready_agent(game, me)
        i = a.decide(obs, acts)
        self.assertEqual(acts[i].action_type, AT.PLAY_KNIGHT_CARD)
        # The knight's score is the best robber move after it, which beats rolling.
        _, s_after = a.score(st, acts[i], phi)
        self.assertGreater(a.after_knight(s_after, phi), a.value(st, phi))

    def test_takes_the_win(self):
        game = to_play_turn(new_game(61))
        st = game.state
        me = st.current_color()
        k = f"P{st.color_to_index[me]}_"
        st.player_state[k + "VICTORY_POINTS"] += 7
        st.player_state[k + "ACTUAL_VICTORY_POINTS"] += 7
        set_hand(st, me, WHEAT=2, ORE=3)
        from catanatron.models.actions import generate_playable_actions
        acts = generate_playable_actions(st)
        a, obs, _ = ready_agent(game, me)
        self.assertEqual(acts[a.decide(obs, acts)].action_type, AT.BUILD_CITY)

    def test_clock_guards(self):
        game = to_play_turn(new_game(71))
        st = game.state
        me = st.current_color()
        set_hand(st, me, WOOD=4, WHEAT=2, ORE=2)
        from catanatron.models.actions import generate_playable_actions
        acts = generate_playable_actions(st)

        calls = []
        a, obs, _ = ready_agent(game, me, cpu_left=0.030)
        a.after_build = lambda *x: calls.append(1)
        a.decide(obs, acts)
        self.assertEqual(calls, [])                    # below 50 ms: no lookahead

        a, obs, _ = ready_agent(game, me, cpu_left=0.200)
        a.after_build = lambda *x: calls.append(1)
        a.decide(obs, acts)
        self.assertTrue(calls)                         # above: lookahead runs

        a, obs, _ = ready_agent(game, me, cpu_left=0.004)
        obs.sample_world = None                        # panic path must not search
        i = a.decide(obs, acts)
        self.assertIn(acts[i].action_type, (AT.BUILD_CITY, AT.BUILD_SETTLEMENT, AT.END_TURN))


class FuzzTests(unittest.TestCase):
    def test_every_decision_is_legal(self):
        """Agent plays one seat of many games against random play; every reply must be legal."""
        rng = random.Random(0)
        n_decisions = 0
        for g in range(30):
            game = new_game(9000 + g)
            agent = agent_mod.Agent()
            me = game.state.colors[g % 2]
            mask_rng = random.Random(g)
            while game.winning_color() is None and game.state.num_turns < 500:
                acts = game.playable_actions
                if game.state.current_color() == me and len(acts) > 1:
                    view = masked_copy(game, me, mask_rng)
                    obs = Obs(view, me)
                    obs.cpu_left = rng.choice([None, 1.0, 0.04, 0.005])
                    i = agent.decide(obs, list(acts))
                    self.assertIs(type(i), int)
                    self.assertTrue(0 <= i < len(acts))
                    game.execute(acts[i])
                    n_decisions += 1
                else:
                    game.play_tick()
        self.assertGreater(n_decisions, 1000)


if __name__ == "__main__":
    unittest.main()
