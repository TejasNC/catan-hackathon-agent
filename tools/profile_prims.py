import os, sys, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catan_kit
from catanatron.game import Game
from catanatron.models.player import Color
from catanatron.players.value import ValueFunctionPlayer, base_fn, DEFAULT_WEIGHTS
from catan_kit.obs import Obs
random.seed(1)
ps=[ValueFunctionPlayer(Color.RED), ValueFunctionPlayer(Color.BLUE)]
g=Game(ps, seed=5)
# play to mid game
while g.state.num_turns < 40 and g.winning_color() is None:
    g.play_tick()
print("turn", g.state.num_turns, "vps", [g.state.player_state[f"P{i}_VICTORY_POINTS"] for i in range(2)])
vf=base_fn(DEFAULT_WEIGHTS)
N=500
t=time.perf_counter()
for _ in range(N): c=g.copy()
print("copy ms", (time.perf_counter()-t)/N*1000)
o=Obs(g, Color.RED)
t=time.perf_counter()
for _ in range(N): o.sample_world(random)
print("sample_world ms", (time.perf_counter()-t)/N*1000)
t=time.perf_counter()
for _ in range(N): vf(g, Color.RED)
print("valuefn ms", (time.perf_counter()-t)/N*1000)
from catanatron.models.actions import generate_playable_actions
t=time.perf_counter()
for _ in range(N): generate_playable_actions(g.state)
print("gen actions ms", (time.perf_counter()-t)/N*1000, g.state.current_prompt, len(g.playable_actions))
# copy+execute end turn
from catanatron.models.enums import Action, ActionType
t=time.perf_counter()
for _ in range(N):
    c=g.copy(); c.execute(c.playable_actions[0], validate_action=False)
print("copy+exec ms", (time.perf_counter()-t)/N*1000, c.playable_actions[0] if False else g.playable_actions[0])
# full random playout to end
t=time.perf_counter(); n=0; steps=0
for _ in range(20):
    c=g.copy()
    while c.winning_color() is None and c.state.num_turns<400:
        a=random.choice(c.playable_actions); c.execute(a, validate_action=False); steps+=1
    n+=1
print("random playout ms", (time.perf_counter()-t)/n*1000, "steps/playout", steps/n, "ms/step", (time.perf_counter()-t)/steps*1000)
