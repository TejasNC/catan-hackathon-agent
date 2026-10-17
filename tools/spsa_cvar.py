"""SPSA on the grading objective J = 0.5*mean(w) + 0.5*mean(worst half of w), where w are win rates
against a fixed archetype gauntlet (fregime_agent and F are held out). theta+ and theta- play the
same seeds against every opponent. Only the v5-tuned weights are perturbed (log space).
python tools/spsa_cvar.py ITERS GAMES_PER_OPP OUT"""
import os, sys, json, math, random, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp
from tools.spsa import to_params

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(ROOT, "bot", "agent.py")
OPPS = ["zoo/arch/ows_zealot.py", "zoo/arch/road_plower.py", "zoo/arch/port_trader.py",
        "zoo/arch/blocker.py", "zoo/arch/greedy.py", "zoo/v3_agent.py", "zoo/v5_final.py"]
_C = None


def _init():
    global _C
    from tools.selfplay import load_agent_class
    _C = {o: load_agent_class(os.path.join(ROOT, o)) for o in OPPS}
    _C["X"] = load_agent_class(BOT)


def _game(args):
    params, o, seed, a_first, tag = args
    from tools.selfplay import play
    res, g = play(_C["X"](params), _C[o](), seed, a_first)
    return tag, o, (1.0 if res else (0.5 if res is None else 0.0))


def J(w):
    ws = sorted(w)
    h = len(ws) // 2
    return 0.5 * sum(ws) / len(ws) + 0.5 * sum(ws[:h]) / h


def main():
    from catan_kit._patch import ensure_hash_seed
    ensure_hash_seed()
    import importlib.util
    spec = importlib.util.spec_from_file_location("v5", os.path.join(ROOT, "zoo", "v5_final.py"))
    v5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v5)
    default = dict(v5.DEFAULT)
    ks = []
    for k, v in default.items():
        if isinstance(v, tuple):
            ks += [(k, j) for j in range(len(v))]
        elif isinstance(v, float) and v != 0:
            ks.append((k, None))
    d = len(ks)
    iters, m, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    c, a = 0.25, 1.2          # J differences are ~half of the self-play score differences
    x = [0.0] * d
    rng = random.Random(777)
    pool = mp.get_context("spawn").Pool(4, initializer=_init)
    t0 = time.time()
    for it in range(iters):
        D = [rng.choice((-1, 1)) for _ in range(d)]
        pp = to_params(default, ks, [xi + c * di for xi, di in zip(x, D)])
        pm = to_params(default, ks, [xi - c * di for xi, di in zip(x, D)])
        jobs = []
        for o in OPPS:
            for g in range(m):
                seed = 3100000 + it * 1000 + g // 2
                jobs += [(pp, o, seed, g % 2 == 0, "+"), (pm, o, seed, g % 2 == 0, "-")]
        res = pool.map(_game, jobs, chunksize=4)
        wp = [sum(r for t, oo, r in res if t == "+" and oo == o) / m for o in OPPS]
        wm = [sum(r for t, oo, r in res if t == "-" and oo == o) / m for o in OPPS]
        jp, jm = J(wp), J(wm)
        ak = a / (1 + it / 100) ** 0.602
        x = [xi + ak * (jp - jm) * di / 2 for xi, di in zip(x, D)]
        with open(out, "a") as f:
            f.write(json.dumps(dict(it=it, jp=jp, jm=jm, x=x, t=time.time() - t0)) + "\n")
        print(it, f"J+={jp:.3f} J-={jm:.3f}", f"{time.time()-t0:.0f}s", flush=True)
    params = to_params(default, ks, x)
    json.dump(params, open(out + ".params.json", "w"), indent=1)


if __name__ == "__main__":
    main()
