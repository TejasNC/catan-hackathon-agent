"""Benchmark opponent: VF value + a regime correction (expand -> build resource weights, v2 defaults).
Zoo only -- never used for training."""
import random
from catanatron.players.value import DEFAULT_WEIGHTS, get_value_fn
from catanatron.features import build_production_features, reachability_features
from catanatron.models.enums import RESOURCES

F_VALUE = get_value_fn("base_fn", DEFAULT_WEIGHTS)
PROD = build_production_features(True)
ME = {"WOOD": 1.25, "BRICK": 1.25, "SHEEP": 1.0, "WHEAT": 0.9, "ORE": 0.6}
MB = {"WOOD": 0.6, "BRICK": 0.6, "SHEEP": 0.9, "WHEAT": 1.35, "ORE": 1.55}


def regime(game, color):
    st = game.state
    if st.is_initial_build_phase:
        return 0.0
    i = st.color_to_index[color]; ps = st.player_state
    vp = ps[f"P{i}_ACTUAL_VICTORY_POINTS"]
    phi_vp = min(1.0, max(0.0, (vp - 4) / 4.0))
    if ps[f"P{i}_SETTLEMENTS_AVAILABLE"] == 0:
        return 1.0
    b = st.board
    cand = set(b.buildable_node_ids(color))
    for e in b.buildable_edges(color):
        cand.update(e)
    legal = set(b.buildable_node_ids(color, initial_build_phase=True))
    best = 0.0
    for n in cand & legal:
        best = max(best, 36 * sum(b.map.node_production[n].values()))
    phi_space = 1 - min(1.0, best / 10.0)
    return max(phi_vp, phi_space)


def correction(game, color, phi):
    st = game.state; ps = st.player_state; i = st.color_to_index[color]; k = f"P{i}_"
    phip = phi + 0.5 * (1 - phi)
    prod = PROD(game, color)
    c = 0.0
    for r in RESOURCES:
        m = (1 - phip) * ME[r] + phip * MB[r]
        c += (m - 1) * prod[f"EFFECTIVE_P0_{r}_PRODUCTION"] * 1e8
    reach = reachability_features(game, color, 2)
    r1 = sum(reach[f"P0_1_ROAD_REACHABLE_{r}"] for r in RESOURCES)
    nb = len(st.board.buildable_node_ids(color))
    c -= 0.7 * phi * (1e3 * nb + 1e4 * r1)
    h = {r: ps[k + r + "_IN_HAND"] for r in RESOURCES}
    d_set = (max(1 - h["WOOD"], 0) + max(1 - h["BRICK"], 0) + max(1 - h["SHEEP"], 0) + max(1 - h["WHEAT"], 0)) / 4
    d_city = (max(2 - h["WHEAT"], 0) + max(3 - h["ORE"], 0)) / 5
    d_dev = (max(1 - h["SHEEP"], 0) + max(1 - h["WHEAT"], 0) + max(1 - h["ORE"], 0)) / 3
    c -= 1e2 * ((1 - phi) * d_set + phi * (0.6 * d_city + 0.4 * d_dev))
    held = sum(ps[k + d + "_IN_HAND"] for d in ["KNIGHT", "VICTORY_POINT", "ROAD_BUILDING", "YEAR_OF_PLENTY", "MONOPOLY"])
    kp, kh = ps[k + "PLAYED_KNIGHT"], ps[k + "KNIGHT_IN_HAND"]
    c += 3e2 * phi * (0.2 * held + (2 / 3) * min(kp + 0.5 * kh, 3))
    return c


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions):
        world = obs.sample_world(self.rng)
        phi = regime(world, obs.me)
        best_i, best_v = 0, None
        for i, a in enumerate(playable_actions):
            s = world.copy()
            try:
                s.execute(a)
            except Exception:
                continue
            v = F_VALUE(s, obs.me) + correction(s, obs.me, phi)
            if best_v is None or v > best_v:
                best_i, best_v = i, v
        return best_i
