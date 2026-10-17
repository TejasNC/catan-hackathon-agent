import os, sys, collections, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.selfplay import load_agent_class, play
from catanatron.models.player import Color
A = load_agent_class(sys.argv[1]); B = load_agent_class(sys.argv[2]); n = int(sys.argv[3])
agg = {True: collections.Counter(), False: collections.Counter()}
wins = 0
for k in range(n):
    res, g = play(A(), B(), 5000 + k // 2, k % 2 == 0)
    wins += bool(res)
    st = g.state; ps = st.player_state
    for col, tag in ((Color.RED, "A"), (Color.BLUE, "B")):
        i = st.color_to_index[col]; b = st.buildings_by_color[col]
        c = agg[res]
        c[tag+"_settle"] += len(b['SETTLEMENT']); c[tag+"_city"] += len(b['CITY']); c[tag+"_roads"] += len(b['ROAD'])
        c[tag+"_army"] += ps[f'P{i}_HAS_ARMY']; c[tag+"_lroad"] += ps[f'P{i}_HAS_ROAD']
        c[tag+"_vpcard"] += ps[f'P{i}_VICTORY_POINT_IN_HAND']; c[tag+"_knights"] += ps[f'P{i}_PLAYED_KNIGHT']
        c[tag+"_knight_unplayed"] += ps[f'P{i}_KNIGHT_IN_HAND']
        c[tag+"_vp"] += ps[f'P{i}_ACTUAL_VICTORY_POINTS']
    for r in st.action_records:
        tag = "A" if r.action.color == Color.RED else "B"
        agg[res][tag + "_" + r.action.action_type.name] += 1
    agg[res]["n"] += 1; agg[res]["turns"] += st.num_turns
print("A win rate", wins / n)
for res in (True, False):
    c = agg[res]; m = max(1, c["n"])
    print("== games A", "WON" if res else "LOST", c["n"])
    keys = sorted(set(k[2:] for k in c if k[:2] in ("A_", "B_")))
    for k in keys:
        print(f"  {k:28s} A {c['A_'+k]/m:6.2f}   B {c['B_'+k]/m:6.2f}")
    print("  turns", c["turns"] / m)
