"""Raw (unweighted) features mirroring bot/agent.py Valuer.score, for regression on outcomes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.agent import Valuer, ctx_for, RES, DEVS, RIDX
from catanatron.models.enums import SETTLEMENT, CITY

NAMES = (["vp"] + [f"prodE_{r}" for r in RES] + [f"prodL_{r}" for r in RES] +
         ["div", "exp1", "exp2", "expn", "card", "discard", "ready_settle", "ready_city", "ready_dev",
          "partial", "knight_hand", "dev_other", "knights_played", "port3", "port2", "road_len",
          "army_lead", "road_lead"])
_V = Valuer()


def player_feats(game, color, c, robber_tile, phase):
    st = game.state; ps = st.player_state
    i = st.color_to_index[color]; k = f"P{i}_"
    prod = _V.production(st, c, color, robber_tile)
    f = [ps[k + "ACTUAL_VICTORY_POINTS"]]
    f += [x * (1 - phase) for x in prod] + [x * phase for x in prod]
    f.append((1 - phase) * sum(1 for x in prod if x > 0))
    e1, e2, nb = _V.expansion(st, c, color)
    sl = ps[k + "SETTLEMENTS_AVAILABLE"] > 0
    m = (1 - phase * 0.5) * sl
    f += [m * e1, m * e2, m * min(nb, 2)]
    hand = [ps[k + r + "_IN_HAND"] for r in RES]; n = sum(hand)
    f += [min(n, 8), (n // 2) if n > 7 else 0]
    wd, br, sh, wh, ore = hand
    f.append(1.0 if (wd and br and sh and wh and nb > 0 and sl) else 0.0)
    f.append(1.0 if (wh >= 2 and ore >= 3 and st.buildings_by_color[color][SETTLEMENT] and ps[k + "CITIES_AVAILABLE"] > 0) else 0.0)
    f.append(1.0 if (sh and wh and ore) else 0.0)
    dc = (max(2 - wh, 0) + max(3 - ore, 0)) / 5.0
    ds = (max(1 - wd, 0) + max(1 - br, 0) + max(1 - sh, 0) + max(1 - wh, 0)) / 4.0
    f.append((2 - dc - ds) / 2)
    f.append(ps[k + "KNIGHT_IN_HAND"])
    f.append(ps[k + "ROAD_BUILDING_IN_HAND"] + ps[k + "YEAR_OF_PLENTY_IN_HAND"] + ps[k + "MONOPOLY_IN_HAND"])
    kp = ps[k + "PLAYED_KNIGHT"]
    f.append(min(kp, 4))
    ports = st.board.get_player_port_resources(color)
    f.append(sum((1 - phase * 0.5) for r in ports if r is None))
    f.append(sum(prod[RIDX[r]] for r in ports if r is not None))
    rl = ps[k + "LONGEST_ROAD_LENGTH"]
    f.append(min(rl, 10))
    return f, kp, rl


def diff_feats(game, color):
    st = game.state; ps = st.player_state
    c = ctx_for(game)
    robber_tile = st.board.map.land_tiles.get(st.board.robber_coordinate)
    lead_vp = max(ps["P0_VICTORY_POINTS"], ps["P1_VICTORY_POINTS"])
    phase = min(1.0, max(0.0, (lead_vp - 2) / 7.0))
    opp = st.colors[1 - st.color_to_index[color]]
    a, k1, r1 = player_feats(game, color, c, robber_tile, phase)
    b, k2, r2 = player_feats(game, opp, c, robber_tile, phase)
    d = [x - y for x, y in zip(a, b)]
    d.append(max(-2, min(2, k1 - k2)))
    d.append(max(-2, min(2, r1 - r2)) / 2)
    return d
