import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.selfplay import load_agent_class, play
from catanatron.models.player import Color
PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
A = load_agent_class(sys.argv[1]); B = load_agent_class(sys.argv[2]); n = int(sys.argv[3])
acc = collections.defaultdict(list)
for k in range(n):
    res, g = play(A(), B(), 9000 + k // 2, k % 2 == 0)
    st = g.state; m = st.board.map
    firsts = [r.action for r in st.action_records if r.action.action_type.name == "BUILD_SETTLEMENT"][:4]
    for col, tag in ((Color.RED, "A"), (Color.BLUE, "B")):
        nodes = [a.value for a in firsts if a.color == col]
        pips = sum(PIPS.get(t.number, 0) for nd in nodes for t in m.adjacent_tiles[nd] if t.resource)
        res_set = set(t.resource for nd in nodes for t in m.adjacent_tiles[nd] if t.resource)
        acc[tag + "_pips"].append(pips); acc[tag + "_div"].append(len(res_set))
        won = res if tag == "A" else (not res)
        acc[tag + "_pips_won" if won else tag + "_pips_lost"].append(pips)
for k, v in sorted(acc.items()):
    print(k, round(sum(v) / len(v), 2), len(v))
