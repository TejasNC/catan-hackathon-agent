import sys, os; sys.path.insert(0,'.')
from catan_kit._patch import ensure_hash_seed; ensure_hash_seed()
from tools.selfplay import load_agent_class, play
from catanatron.models.enums import ActionType as AT
from catanatron.models.player import Color
seed, opp = int(sys.argv[1]), sys.argv[2]
A = load_agent_class("army/comboop1/agent.py")(); B = load_agent_class(opp)()
def hook(game, color, acts, i):
    if color != Color.RED: return
    st = game.state; types = {x.action_type for x in acts}
    if acts[i].action_type == AT.END_TURN and AT.BUILD_SETTLEMENT in types:
        idx = st.color_to_index[color]; ps = st.player_state
        hand = {r: ps[f"P{idx}_{r}_IN_HAND"] for r in ["WOOD","BRICK","SHEEP","WHEAT","ORE"]}
        print("turn", st.num_turns, "VP", ps[f"P{idx}_ACTUAL_VICTORY_POINTS"], "oppVP", ps[f"P{1-idx}_ACTUAL_VICTORY_POINTS"], hand, "settles left", ps[f"P{idx}_SETTLEMENTS_AVAILABLE"], "cities left", ps[f"P{idx}_CITIES_AVAILABLE"])
        print("   actions:", sorted({x.action_type.name for x in acts}), [x.value for x in acts if x.action_type==AT.BUILD_SETTLEMENT])
        o = A
        from catan_kit.obs import Obs
        g = game.copy()
        sc = []
        for a in acts:
            if a.action_type == AT.END_TURN: v = o.V.value(g, color)
            else: v, _ = o.eval_action(g, a, color)
            sc.append((round(v,3), a.action_type.name, a.value))
        for s in sorted(sc, key=lambda x: -x[0])[:6]: print("     ", s)
res, g = play(A, B, seed, False, hook=hook)
print("result", res)
