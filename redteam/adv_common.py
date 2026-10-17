import random
from catanatron.players.value import DEFAULT_WEIGHTS, get_value_fn
from catanatron.models.enums import ActionType as AT
VALUE_FN = get_value_fn("base_fn", DEFAULT_WEIGHTS)

def f_pick(obs, acts, rng, cand=None):
    world = obs.sample_world(rng)
    bi, bv = None, None
    for i in (cand if cand is not None else range(len(acts))):
        s = world.copy()
        try:
            s.execute(acts[i])
        except Exception:
            continue
        v = VALUE_FN(s, obs.me)
        if bv is None or v > bv:
            bi, bv = i, v
    return 0 if bi is None else bi

def opp_of(obs):
    st = obs._game.state
    return st.colors[1 - st.color_to_index[obs.me]]

def tile_prod_for(obs, coord, color):
    """pips the given color collects on the tile at coord"""
    g = obs._game; b = g.state.board
    t = b.map.land_tiles.get(coord)
    if t is None or t.number is None: return 0
    pips = 6 - abs(7 - t.number)
    tot = 0
    for n in t.nodes.values():
        bld = b.buildings.get(n)
        if bld and bld[0] == color:
            tot += pips * (2 if bld[1] == "CITY" else 1)
    return tot
