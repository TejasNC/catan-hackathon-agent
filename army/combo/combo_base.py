"""Strategic Catan agent: hand-built value function in VP units + shallow within-turn planning.

Structure
  * value(): V(state) = Score(me) - Score(opp), every term expressed in victory-point units.
  * decide(): one sampled world per decision; every legal action is simulated on a copy and scored.
    Resource-changing actions (bank trades, year of plenty, monopoly) get a second step: their score
    is the best build reachable after them this turn. Random outcomes (dev-card draw, robber steal)
    are scored in expectation instead of on the sampled outcome.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catanatron.models.enums import Action, ActionType, SETTLEMENT, CITY, ROAD
from catanatron.models.board import STATIC_GRAPH

RES = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
DEVS = ["KNIGHT", "VICTORY_POINT", "ROAD_BUILDING", "YEAR_OF_PLENTY", "MONOPOLY"]
PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
NEIGH = {n: tuple(STATIC_GRAPH.neighbors(n)) for n in STATIC_GRAPH.nodes}
AT = ActionType

DEFAULT = dict(
    # SPSA self-play tuned (93 iterations x 64 games, theta+ vs theta-; F never used).
    # Hand-set starting values are kept in docs/INSIGHTS.md.
    prod=0.0550,
    prod_late=0.0495,
    div=0.2736,
    res_w=(1.0617, 1.3017, 1.1478, 1.6027, 1.5802),
    opp_k=0.7374,
    exp1=0.0192,
    exp2=0.0100,
    exp_n=0.0502,
    card=0.0608,
    ready_settle=0.3021,
    ready_city=0.4661,
    ready_dev=0.1179,
    partial=0.0586,
    discard=0.1765,
    knight_hand=0.0945,
    dev_other=0.1800,
    knight_played=0.1565,
    army_lead=0.2015,
    road_len=0.0395,
    road_lead=0.2572,
    port2=0.0100,
    port3=0.1932,
    settle_spot=0.0000,
    prog_city=0.0, prog_settle=0.0, prog_dev=0.0,   # convex progress toward a build target (tested: worse)
    draft=1.0,                                      # snake-draft lookahead for the opening
    # regime (expand -> build): phi in [0,1] computed once per decision at the root, 0 = off
    regime=0.0,       # strength of the resource-multiplier interpolation (1 = full multipliers)
    reg_fade=0.0,     # expansion terms scaled by (1 - reg_fade * phi)
    reg_dev=0.0,      # dev-card terms scaled by (1 + reg_dev * phi)
    reg_reach=1,      # roads of reach for the best open spot (1 = spec; 2 also counts two-road spots)
)
REG_EXPAND = (1.25, 1.25, 1.0, 0.9, 0.6)
REG_BUILD = (0.6, 0.6, 0.9, 1.35, 1.55)


class Ctx:
    """Per-map precomputation (cached by map signature)."""

    def __init__(self, m):
        self.node_tiles = {}
        for n, tiles in m.adjacent_tiles.items():
            self.node_tiles[n] = [(t.resource, PIPS.get(t.number, 0), t) for t in tiles if t.resource]
        self.node_pips = {n: sum(p for _, p, _ in v) for n, v in self.node_tiles.items()}
        self.port_of = {}
        for r, nodes in m.port_nodes.items():
            for n in nodes:
                self.port_of[n] = r
        self.land = set(m.land_nodes)


_CTX = {}


def ctx_for(game):
    m = game.state.board.map
    key = id(m)
    c = _CTX.get(key)
    if c is None:
        if len(_CTX) > 8:
            _CTX.clear()
        c = Ctx(m)
        _CTX[key] = c
    return c


class Valuer:
    def __init__(self, params=None):
        self.p = dict(DEFAULT)
        if params:
            self.p.update(params)
        self.phi = {}     # color -> regime phi, fixed for the current decision

    def regime_on(self):
        p = self.p
        return bool(p["regime"] or p["reg_fade"] or p["reg_dev"])

    def set_regime(self, game):
        """phi = max(phi_VP, phi_space) per color, from the root world of this decision."""
        self.phi = {}
        if not self.regime_on():
            return
        st = game.state
        ps = st.player_state
        c = ctx_for(game)
        for color in st.colors:
            k = f"P{st.color_to_index[color]}_"
            phi_vp = min(1.0, max(0.0, (ps[k + "ACTUAL_VICTORY_POINTS"] - 4) / 4.0))
            if st.is_initial_build_phase:
                phi_sp = 0.0
            elif ps[k + "SETTLEMENTS_AVAILABLE"] <= 0:
                phi_sp = 1.0
            else:
                if self.p["reg_reach"] >= 2:
                    e1, e2, nb = self.expansion(st, c, color)
                    spot = max(self.best_open_spot(st, c, color), 0.8 * e2 / 2 if e2 else 0)
                else:
                    spot = self.best_open_spot(st, c, color)
                phi_sp = 1.0 - min(1.0, spot / 10.0)
            self.phi[color] = max(phi_vp, phi_sp)

    def best_open_spot(self, st, c, color):
        """Highest-pip legal settlement spot reachable now or with one more road."""
        board = st.board
        buildable = board.board_buildable_ids
        comps = board.connected_components[color]
        if not comps:
            return 0
        frontier = set().union(*comps)
        roads = board.roads
        bld = board.buildings
        np_ = c.node_pips
        best = 0
        for n in frontier:
            if n in buildable:
                best = max(best, np_.get(n, 0))
            o = bld.get(n)
            if o is not None and o[0] != color:
                continue
            for nb in NEIGH[n]:
                rc = roads.get((n, nb))
                if rc is not None and rc != color:
                    continue
                if nb in buildable:
                    best = max(best, np_.get(nb, 0))
        return best

    # ---- per player pieces -------------------------------------------------------------------
    def production(self, st, c, color, robber_tile):
        prod = [0.0] * 5
        b = st.buildings_by_color[color]
        for mult, kind in ((1, SETTLEMENT), (2, CITY)):
            for n in b[kind]:
                for r, p, t in c.node_tiles[n]:
                    if t is not robber_tile:
                        prod[RIDX[r]] += mult * p
        return prod

    def expansion(self, st, c, color):
        """Pips of the best settlement spots reachable with 0/1/2 more roads."""
        board = st.board
        buildable = board.board_buildable_ids
        comps = board.connected_components[color]
        if not comps:
            return 0.0, 0.0, 0
        frontier = set().union(*comps)
        roads = board.roads
        bld = board.buildings
        d0 = [n for n in frontier if n in buildable]
        seen = set(frontier)
        lvl1 = set()
        for n in frontier:
            o = bld.get(n)
            if o is not None and o[0] != color:
                continue
            for nb in NEIGH[n]:
                if nb in seen:
                    continue
                rc = roads.get((n, nb))
                if rc is not None and rc != color:
                    continue
                lvl1.add(nb)
        seen |= lvl1
        lvl2 = set()
        for n in lvl1:
            if n in bld:
                continue
            for nb in NEIGH[n]:
                if nb in seen:
                    continue
                if roads.get((n, nb)) is not None:
                    continue
                lvl2.add(nb)
        np_ = c.node_pips
        best1 = sorted([np_.get(n, 0) for n in d0] + [0.8 * np_.get(n, 0) for n in lvl1 if n in buildable],
                       reverse=True)[:2]
        best2 = sorted([np_.get(n, 0) for n in lvl2 if n in buildable], reverse=True)[:2]
        return sum(best1), sum(best2), len(d0)

    def score(self, game, color, me, c, robber_tile):
        p = self.p
        st = game.state
        ps = st.player_state
        i = st.color_to_index[color]
        k = f"P{i}_"
        if me:
            vp = ps[k + "ACTUAL_VICTORY_POINTS"]
        else:
            vp = ps[k + "VICTORY_POINTS"]
        # phase: production matters less as the end approaches
        lead_vp = max(ps["P0_VICTORY_POINTS"], ps["P1_VICTORY_POINTS"])
        phase = min(1.0, max(0.0, (lead_vp - 2) / 7.0))
        wprod = p["prod"] * (1 - phase) + p["prod_late"] * phase

        prod = self.production(st, c, color, robber_tile)
        rw = p["res_w"]
        phi = self.phi.get(color, 0.0)
        if phi and p["regime"]:
            q = phi + 0.5 * (1 - phi)
            a = p["regime"]
            rw = [w * (1 + a * ((1 - q) * e + q * b - 1)) for w, e, b in zip(rw, REG_EXPAND, REG_BUILD)]
        fade = 1 - p["reg_fade"] * phi
        dmul = 1 + p["reg_dev"] * phi
        s = vp
        s += wprod * sum(prod[r] * rw[r] for r in range(5))
        s += p["div"] * (1 - phase) * sum(1 for x in prod if x > 0)

        e1, e2, nb = self.expansion(st, c, color)
        settle_left = ps[k + "SETTLEMENTS_AVAILABLE"]
        if settle_left > 0:
            s += fade * (1 - phase * 0.5) * (p["exp1"] * e1 + p["exp2"] * e2 + p["exp_n"] * min(nb, 2))

        # hand
        hand = [ps[k + r + "_IN_HAND"] for r in RES]
        n_hand = sum(hand)
        s += p["card"] * min(n_hand, 8)
        if n_hand > 7:
            s -= p["discard"] * (n_hand // 2)
        wd, br, sh, wh, ore = hand
        if wd >= 1 and br >= 1 and sh >= 1 and wh >= 1 and nb > 0 and settle_left > 0:
            s += p["ready_settle"]
        if wh >= 2 and ore >= 3 and st.buildings_by_color[color][SETTLEMENT] and ps[k + "CITIES_AVAILABLE"] > 0:
            s += p["ready_city"]
        if sh >= 1 and wh >= 1 and ore >= 1:
            s += p["ready_dev"]
        dist_city = (max(2 - wh, 0) + max(3 - ore, 0)) / 5.0
        dist_set = (max(1 - wd, 0) + max(1 - br, 0) + max(1 - sh, 0) + max(1 - wh, 0)) / 4.0
        s += p["partial"] * (2 - dist_city - dist_set) / 2
        if p["prog_city"] and st.buildings_by_color[color][SETTLEMENT] and ps[k + "CITIES_AVAILABLE"] > 0:
            s += p["prog_city"] * ((min(wh, 2) + min(ore, 3)) / 5.0) ** 2
        if p["prog_settle"] and settle_left > 0 and (nb > 0 or e1 > 0):
            s += p["prog_settle"] * ((min(wd, 1) + min(br, 1) + min(sh, 1) + min(wh, 1)) / 4.0) ** 2
        if p["prog_dev"]:
            s += p["prog_dev"] * ((min(sh, 1) + min(wh, 1) + min(ore, 1)) / 3.0) ** 2

        # dev cards / army
        knights_played = ps[k + "PLAYED_KNIGHT"]
        if me:
            kh = ps[k + "KNIGHT_IN_HAND"]
            other = ps[k + "ROAD_BUILDING_IN_HAND"] + ps[k + "YEAR_OF_PLENTY_IN_HAND"] + ps[k + "MONOPOLY_IN_HAND"]
            s += dmul * (p["knight_hand"] * kh + p["dev_other"] * other)
        else:
            ndev = sum(ps[k + d + "_IN_HAND"] for d in DEVS)
            s += ndev * (dmul * (0.56 * p["knight_hand"] + 0.24 * p["dev_other"]) + 0.2 * 1.0)
        s += dmul * p["knight_played"] * min(knights_played, 4)
        # ports
        ports = st.board.get_player_port_resources(color)
        for r in ports:
            if r is None:
                s += p["port3"] * (1 - phase * 0.5)
            else:
                s += p["port2"] * prod[RIDX[r]]
        s += p["road_len"] * min(ps[k + "LONGEST_ROAD_LENGTH"], 10)
        return s, knights_played, ps[k + "LONGEST_ROAD_LENGTH"]

    def lin_feats(self, game, color, me, c, robber_tile, phase):
        """Raw features (same formulas as tools/feats.py) for the learned linear evaluation."""
        st = game.state; ps = st.player_state
        k = f"P{st.color_to_index[color]}_"
        prod = self.production(st, c, color, robber_tile)
        ndev = sum(ps[k + d + "_IN_HAND"] for d in DEVS)
        if me:
            f = [ps[k + "ACTUAL_VICTORY_POINTS"]]
        else:
            f = [ps[k + "VICTORY_POINTS"] + 0.2 * ndev]
        f += [x * (1 - phase) for x in prod] + [x * phase for x in prod]
        f.append((1 - phase) * sum(1 for x in prod if x > 0))
        e1, e2, nb = self.expansion(st, c, color)
        sl = ps[k + "SETTLEMENTS_AVAILABLE"] > 0
        m = (1 - phase * 0.5) * sl
        f += [m * e1, m * e2, m * min(nb, 2)]
        hand = [ps[k + r + "_IN_HAND"] for r in RES]; n = sum(hand)
        f += [min(n, 8), (n // 2) if n > 7 else 0]
        wd, br, sh, wh, ore = hand
        f.append(1.0 if (wd and br and sh and wh and nb > 0 and sl) else 0.0)
        f.append(1.0 if (wh >= 2 and ore >= 3 and st.buildings_by_color[color][SETTLEMENT]
                         and ps[k + "CITIES_AVAILABLE"] > 0) else 0.0)
        f.append(1.0 if (sh and wh and ore) else 0.0)
        dc = (max(2 - wh, 0) + max(3 - ore, 0)) / 5.0
        ds = (max(1 - wd, 0) + max(1 - br, 0) + max(1 - sh, 0) + max(1 - wh, 0)) / 4.0
        f.append((2 - dc - ds) / 2)
        if me:
            f.append(ps[k + "KNIGHT_IN_HAND"])
            f.append(ps[k + "ROAD_BUILDING_IN_HAND"] + ps[k + "YEAR_OF_PLENTY_IN_HAND"] + ps[k + "MONOPOLY_IN_HAND"])
        else:
            f.append(0.56 * ndev)
            f.append(0.24 * ndev)
        kp = ps[k + "PLAYED_KNIGHT"]
        f.append(min(kp, 4))
        ports = st.board.get_player_port_resources(color)
        f.append(sum((1 - phase * 0.5) for r in ports if r is None))
        f.append(sum(prod[RIDX[r]] for r in ports if r is not None))
        rl = ps[k + "LONGEST_ROAD_LENGTH"]
        f.append(min(rl, 10))
        return f, kp, rl

    def lin_value(self, game, me_color):
        st = game.state; ps = st.player_state
        c = ctx_for(game)
        robber_tile = st.board.map.land_tiles.get(st.board.robber_coordinate)
        lead_vp = max(ps["P0_VICTORY_POINTS"], ps["P1_VICTORY_POINTS"])
        phase = min(1.0, max(0.0, (lead_vp - 2) / 7.0))
        opp = st.colors[1 - st.color_to_index[me_color]]
        a, k1, r1 = self.lin_feats(game, me_color, True, c, robber_tile, phase)
        b, k2, r2 = self.lin_feats(game, opp, False, c, robber_tile, phase)
        w = self.p["lin"]
        v = sum(wi * (x - y) for wi, x, y in zip(w, a, b))
        v += w[-2] * max(-2, min(2, k1 - k2)) + w[-1] * max(-2, min(2, r1 - r2)) / 2
        return v

    def value(self, game, me_color):
        if "lin" in self.p:
            return self.lin_value(game, me_color)
        st = game.state
        c = ctx_for(game)
        robber_tile = st.board.map.land_tiles.get(st.board.robber_coordinate)
        opp_color = st.colors[1 - st.color_to_index[me_color]]
        s1, k1, r1 = self.score(game, me_color, True, c, robber_tile)
        s2, k2, r2 = self.score(game, opp_color, False, c, robber_tile)
        p = self.p
        ok = p["opp_k"]
        if p.get("danger"):
            ovp = st.player_state[f"P{st.color_to_index[opp_color]}_VICTORY_POINTS"]
            ok += p["danger"] * max(0, ovp - 6) / 3.0
        v = s1 - ok * s2
        v += p["army_lead"] * max(-2, min(2, k1 - k2))
        v += p["road_lead"] * max(-2, min(2, r1 - r2)) / 2
        return v


RIDX = {r: i for i, r in enumerate(RES)}


class Agent:
    def __init__(self, params=None):
        self.rng = random.Random(0)
        self.V = Valuer(params)

    # expected value of one unknown development card for me (VP units, matching Valuer.score)
    def dev_ev(self, game, me):
        p = self.V.p
        st = game.state
        ps = st.player_state
        i = st.color_to_index[me]
        # unseen pile composition from my seat
        counts = {"KNIGHT": 14, "VICTORY_POINT": 5, "ROAD_BUILDING": 2, "YEAR_OF_PLENTY": 2, "MONOPOLY": 2}
        for d in DEVS:
            counts[d] -= ps[f"P{i}_{d}_IN_HAND"] + ps.get(f"P{i}_PLAYED_{d}", 0) + ps.get(f"P{1-i}_PLAYED_{d}", 0)
        tot = sum(max(0, x) for x in counts.values())
        if tot <= 0:
            return 0.0
        dm = 1 + p["reg_dev"] * self.V.phi.get(me, 0.0)
        ev = (max(0, counts["KNIGHT"]) * p["knight_hand"] * dm + max(0, counts["VICTORY_POINT"]) * 1.0 +
              (max(0, counts["ROAD_BUILDING"]) + max(0, counts["YEAR_OF_PLENTY"]) + max(0, counts["MONOPOLY"]))
              * p["dev_other"] * dm) / tot
        return ev

    def dev_val(self, card, me=None):
        p = self.V.p
        dm = 1 + p["reg_dev"] * self.V.phi.get(me, 0.0)
        if card == "KNIGHT":
            return p["knight_hand"] * dm
        if card == "VICTORY_POINT":
            return 1.0
        return p["dev_other"] * dm

    def eval_action(self, game, action, me):
        """Score of the state after `action` (expected over its random outcome where cheap)."""
        at = action.action_type
        if at == AT.MOVE_ROBBER and action.value[1] is not None:
            g = game.copy()
            g.execute(Action(action.color, at, (action.value[0], None)), validate_action=False)
            # a steal: +1 random card for me, -1 for them
            return self.V.value(g, me) + self.V.p["card"] * (1 + self.V.p["opp_k"]), g
        g = game.copy()
        try:
            if at == AT.BUY_DEVELOPMENT_CARD:
                i = g.state.color_to_index[me]
                before = {d: g.state.player_state[f"P{i}_{d}_IN_HAND"] for d in DEVS}
                g.execute(action, validate_action=False)
                drawn = [d for d in DEVS if g.state.player_state[f"P{i}_{d}_IN_HAND"] > before[d]]
                v = self.V.value(g, me)
                if drawn:
                    v += self.dev_ev(game, me) - self.dev_val(drawn[0], me)
                return v, g
            g.execute(action, validate_action=False)
        except Exception:
            return -1e9, None
        return self.V.value(g, me), g

    def greedy_followup(self, g, me, steps):
        """Play `steps` greedy forced-phase decisions (robber placement, free roads) and score."""
        v = self.V.value(g, me)
        for _ in range(steps):
            if g.state.current_color() != me:
                break
            acts = g.playable_actions
            if not acts:
                break
            best = None
            for b in acts:
                if b.action_type not in (AT.MOVE_ROBBER, AT.BUILD_ROAD):
                    continue
                vb, gb = self.eval_action(g, b, me)
                if best is None or vb > best[0]:
                    best = (vb, gb)
            if best is None or best[1] is None:
                break
            v, g = best
        return v

    # ---- opening: snake-draft lookahead on a static pair value ---------------------------------
    def pair_value(self, nodes, c):
        p = self.V.p
        rw = p["res_w"]
        prod = [0.0] * 5
        ports = set()
        for n in nodes:
            for r, pp, _ in c.node_tiles[n]:
                prod[RIDX[r]] += pp
            if n in c.port_of:
                ports.add(c.port_of[n])
        v = p["prod"] * sum(prod[r] * rw[r] for r in range(5)) + p["div"] * sum(1 for x in prod if x > 0)
        for r in ports:
            v += p["port3"] if r is None else p["port2"] * prod[RIDX[r]]
        return v

    def draft_pick(self, game, me, candidates):
        st = game.state
        c = ctx_for(game)
        opp = st.colors[1 - st.color_to_index[me]]
        mine = list(st.buildings_by_color[me][SETTLEMENT])
        theirs = list(st.buildings_by_color[opp][SETTLEMENT])
        lam = self.V.p["opp_k"]
        free0 = set(st.board.board_buildable_ids)

        def block(free, n):
            f = set(free)
            f.discard(n)
            for nb in NEIGH[n]:
                f.discard(nb)
            return f

        def best_completion(base, free):
            best, bn = -1e9, None
            for n in free:
                v = self.pair_value(base + [n], c)
                if v > best:
                    best, bn = v, n
            return best, bn

        single = sorted(free0, key=lambda n: -self.pair_value([n], c))
        if len(mine) == 0 and len(theirs) == 0:          # first pick of the game
            best, choice = -1e9, None
            for a1 in single[:15]:
                f = block(free0, a1)
                b1 = max(f, key=lambda n: self.pair_value([n], c))
                f = block(f, b1)
                vb, b2 = best_completion([b1], f)
                f = block(f, b2)
                va, _ = best_completion([a1], f)
                sc = va - lam * vb
                if sc > best:
                    best, choice = sc, a1
            return choice
        if len(mine) == 0 and len(theirs) == 1:          # second seat, two picks in a row
            best, choice = -1e9, None
            top = single[:14]
            for x in top:
                fx = block(free0, x)
                for y in top:
                    if y == x or y not in fx:
                        continue
                    f = block(fx, y)
                    vo, _ = best_completion(theirs, f)
                    sc = self.pair_value([x, y], c) - lam * vo
                    if sc > best:
                        best, choice = sc, x
            return choice
        if len(mine) == 1 and len(theirs) == 1:          # second seat, second pick
            best, choice = -1e9, None
            for y in single[:25]:
                f = block(free0, y)
                vo, _ = best_completion(theirs, f)
                sc = self.pair_value(mine + [y], c) - lam * vo
                if sc > best:
                    best, choice = sc, y
            return choice
        return best_completion(mine, free0)[1]

    PANIC = {AT.BUILD_CITY: 0, AT.BUILD_SETTLEMENT: 1, AT.PLAY_KNIGHT_CARD: 2, AT.BUY_DEVELOPMENT_CARD: 3,
             AT.ROLL: 4, AT.END_TURN: 5}

    def panic(self, actions):
        best, bi = 99, 0
        for idx, a in enumerate(actions):
            r = self.PANIC.get(a.action_type, 9)
            if r < best:
                best, bi = r, idx
        return bi

    def decide(self, obs, playable_actions):
        me = obs.me
        if obs.cpu_left is not None and obs.cpu_left < 0.10:
            # nearly out of clock (only very long games): no simulation, fixed priorities
            return self.panic(playable_actions)
        game = obs.sample_world(self.rng)
        actions = playable_actions
        n = len(actions)
        if n == 1:
            return 0
        cheap = obs.cpu_left is not None and obs.cpu_left < 0.25
        st = game.state
        self.V.set_regime(game)

        if self.V.p["draft"] and st.is_initial_build_phase and st.current_prompt.name == "BUILD_INITIAL_SETTLEMENT":
            try:
                node = self.draft_pick(game, me, [a.value for a in actions])
                for idx, a in enumerate(actions):
                    if a.value == node:
                        return idx
            except Exception:
                pass
        # fast paths
        if all(a.action_type == AT.ROLL or a.action_type == AT.PLAY_KNIGHT_CARD for a in actions):
            pass

        best_i, best_v = 0, -1e18
        scored = []
        for idx, a in enumerate(actions):
            at = a.action_type
            if at == AT.ROLL:
                v = self.V.value(game, me) + 0.0
                g2 = None
            else:
                v, g2 = self.eval_action(game, a, me)
            scored.append((v, idx, g2))
            if v > best_v:
                best_v, best_i = v, idx

        if cheap or st.is_initial_build_phase:
            return best_i

        # dev cards whose payoff comes from the follow-up decisions (robber move, free roads)
        for v, idx, g2 in scored:
            at = actions[idx].action_type
            if g2 is None or at not in (AT.PLAY_KNIGHT_CARD, AT.PLAY_ROAD_BUILDING):
                continue
            bv = self.greedy_followup(g2, me, 2 if at == AT.PLAY_ROAD_BUILDING else 1)
            if bv > best_v + 1e-9:
                best_v, best_i = bv, idx

        # second step for resource-changing actions: value = best build reachable afterwards
        if st.current_prompt.name == "PLAY_TURN" and not st.is_road_building:
            trade_like = [(v, idx, g2) for (v, idx, g2) in scored if g2 is not None and actions[idx].action_type in
                          (AT.MARITIME_TRADE, AT.PLAY_YEAR_OF_PLENTY, AT.PLAY_MONOPOLY)]
            trade_like.sort(key=lambda x: -x[0])
            for v, idx, g2 in trade_like[:6]:
                follow = [b for b in g2.playable_actions if b.action_type in
                          (AT.BUILD_CITY, AT.BUILD_SETTLEMENT, AT.BUY_DEVELOPMENT_CARD, AT.BUILD_ROAD)]
                bv = v
                for b in follow[:12]:
                    vb, _ = self.eval_action(g2, b, me)
                    if vb > bv:
                        bv = vb
                if bv > best_v + 1e-9:
                    best_v, best_i = bv, idx
        return best_i
