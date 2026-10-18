"""Self-play data: (diff features from the mover's seat, did the mover win). The VF benchmark is not involved."""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp
import numpy as np

def work(args):
    path, seeds, eps, out = args
    os.environ["PYTHONHASHSEED"] = "0"
    from tools.selfplay import load_agent_class, play
    from tools.feats import diff_feats
    A = load_agent_class(path)
    X, Y, T = [], [], []
    for s in seeds:
        rows = []
        rng = random.Random(s)
        class Eps:
            def __init__(self): self.a = A()
            def decide(self, obs, acts):
                if rng.random() < eps:
                    return rng.randrange(len(acts))
                return self.a.decide(obs, acts)
        def hook(game, color, acts, i):
            if game.state.is_initial_build_phase or rng.random() < 0.5:
                return
            rows.append((diff_feats(game, color), color, game.state.num_turns))
        res, g = play(Eps(), Eps(), s, s % 2 == 0, hook=hook)
        w = g.winning_color()
        if w is None:
            continue
        for f, col, t in rows:
            X.append(f); Y.append(1 if col == w else 0); T.append(t)
    np.savez(out, X=np.array(X, dtype=np.float32), Y=np.array(Y, dtype=np.int8), T=np.array(T))

if __name__ == "__main__":
    path, n, procs, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    eps = float(sys.argv[5]) if len(sys.argv) > 5 else 0.03
    s0 = int(sys.argv[6]) if len(sys.argv) > 6 else 200000
    seeds = list(range(s0, s0 + n))
    jobs = [(path, seeds[k::procs], eps, f"{outp}_{k}.npz") for k in range(procs)]
    ctx = mp.get_context("spawn")
    ps = [ctx.Process(target=work, args=(j,)) for j in jobs]
    [p.start() for p in ps]; [p.join() for p in ps]
    print("done")
