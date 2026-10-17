"""Quick in-process matches between catanatron Player objects (perfect info, no clock).
usage: python tools/lib_match.py AB2 F 40"""
import os, sys, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catan_kit
from catanatron.game import Game
from catanatron.models.player import Color
from catanatron.players.value import ValueFunctionPlayer
from catanatron.players.minimax import AlphaBetaPlayer, SameTurnAlphaBetaPlayer

def make(name, color):
    if name == "F": return ValueFunctionPlayer(color)
    if name.startswith("ABP"): return AlphaBetaPlayer(color, depth=int(name[3:]), prunning=True)
    if name.startswith("AB"): return AlphaBetaPlayer(color, depth=int(name[2:]))
    if name.startswith("ST"): return SameTurnAlphaBetaPlayer(color, depth=int(name[2:]))
    raise ValueError(name)

def run(na, nb, n, seed0=0):
    wins = 0; tA = 0.0; t0=time.time()
    for k in range(n):
        seed = seed0 + k // 2
        a = make(na, Color.RED); b = make(nb, Color.BLUE)
        order = [a, b] if k % 2 == 0 else [b, a]
        random.seed(seed)
        g = Game(order, seed=seed)
        # Game() randomizes seating via random.sample; force order
        g.state.players = order; g.state.colors = tuple(p.color for p in order)
        g.state.color_to_index = {c: i for i, c in enumerate(g.state.colors)}
        from catanatron.models.actions import generate_playable_actions
        g.playable_actions = generate_playable_actions(g.state)
        random.seed(seed * 7 + 1)
        w = g.play()
        wins += (w == Color.RED)
    return wins / n, time.time()-t0

if __name__ == "__main__":
    na, nb, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    s0 = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    r, t = run(na, nb, n, s0)
    print(f"{na} vs {nb}: {r:.3f} over {n} games, {t:.1f}s")
