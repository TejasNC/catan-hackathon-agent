import os, sys, time, random, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catan_kit
from catanatron.game import Game
from catanatron.models.player import Color
from catanatron.players.value import ValueFunctionPlayer
from catanatron.models.enums import ActionType
agg=collections.Counter(); n=0
turns=[]
for seed in range(60):
    random.seed(seed)
    g=Game([ValueFunctionPlayer(Color.RED), ValueFunctionPlayer(Color.BLUE)], seed=seed)
    w=g.play()
    turns.append(g.state.num_turns)
    i=g.state.color_to_index[w]; ps=g.state.player_state
    b=g.state.buildings_by_color[w]
    agg['settle']+=len(b['SETTLEMENT']); agg['city']+=len(b['CITY'])
    agg['army']+=ps[f'P{i}_HAS_ARMY']; agg['road']+=ps[f'P{i}_HAS_ROAD']; agg['vpcard']+=ps[f'P{i}_VICTORY_POINT_IN_HAND']
    for r in g.state.action_records:
        agg['A_'+r.action.action_type.name]+=1
    agg['first_wins']+= (i==0)
    n+=1
print("mean turns", sum(turns)/n)
for k,v in sorted(agg.items()): print(k, v/n)
