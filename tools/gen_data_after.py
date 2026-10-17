"""After-state self-play data (TD-Gammon style): features of the state right after a player's END_TURN,
recorded at the next decision (usually the opponent's forced ROLL), from the perspective of the player
who just ended (diff_feats(game, that_player)), labelled with whether that player won.
python tools/gen_data_after.py AGENT.py N PROCS OUT [eps] [seed0]"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp
import numpy as np


def work(args):
    path, seeds, eps, out = args
    os.environ["PYTHONHASHSEED"] = "0"
    from tools import selfplay
    from tools.selfplay import load_agent_class, play
    from tools.feats import diff_feats
    from catanatron.models.enums import ActionType
    A = load_agent_class(path)
    orig = selfplay.Wrap.decide
    rec = {"rows": None}

    def decide(self, game, playable_actions):
        # called on every decision, forced ones included (the base Wrap only hooks non-forced)
        st = game.state
        if rec["rows"] is not None and not st.is_initial_build_phase and st.action_records:
            last = st.action_records[-1].action
            if last.action_type == ActionType.END_TURN and last.color != self.color:
                rec["rows"].append((diff_feats(game, last.color), last.color, st.num_turns))
        return orig(self, game, playable_actions)
    selfplay.Wrap.decide = decide

    X, Y, T = [], [], []
    for s in seeds:
        rows = []; rec["rows"] = rows
        rng = random.Random(s)
        class Eps:
            def __init__(self): self.a = A()
            def decide(self, obs, acts):
                if rng.random() < eps:
                    return rng.randrange(len(acts))
                return self.a.decide(obs, acts)
        res, g = play(Eps(), Eps(), s, s % 2 == 0)
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
