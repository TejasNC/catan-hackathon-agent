"""SPSA self-play tuning of the bot's value-function weights. The VF benchmark is never used.

Each iteration: draw a random sign vector D, play theta+ = x + cD against theta- = x - cD on
paired boards (both seats), and step x along D by the score difference. Weights live in log space
(theta_k = default_k * exp(x_k)) so every perturbation is multiplicative.
"""
import os, sys, json, math, random, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp

BOT = os.environ.get("SPSA_BOT", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot", "agent.py"))


def keys_and_x0(default):
    ks = []
    for k, v in default.items():
        if isinstance(v, tuple):
            for j, vj in enumerate(v):
                ks.append((k, j))
        elif v != 0:
            ks.append((k, None))
    return ks


def to_params(default, ks, x):
    p = {k: (list(v) if isinstance(v, tuple) else v) for k, v in default.items()}
    for (k, j), xi in zip(ks, x):
        if j is None:
            p[k] = default[k] * math.exp(xi)
        else:
            p[k][j] = default[k][j] * math.exp(xi)
    return {k: (tuple(v) if isinstance(v, list) else v) for k, v in p.items()}


_A = None


def _init():
    global _A
    os.environ.setdefault("PYTHONHASHSEED", "0")
    from tools.selfplay import load_agent_class
    _A = load_agent_class(BOT)


def _game(args):
    pa, pb, seed, a_first = args
    from tools.selfplay import play
    res, g = play(_A(pa), _A(pb), seed, a_first)
    return 1.0 if res else (0.5 if res is None else 0.0)


def main():
    from catan_eval._patch import ensure_hash_seed
    ensure_hash_seed()
    import importlib.util
    spec = importlib.util.spec_from_file_location("botmod", BOT)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    default = mod.DEFAULT
    ks = keys_and_x0(default)
    d = len(ks)
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    ngames = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    out = sys.argv[3] if len(sys.argv) > 3 else "spsa_log.jsonl"
    c, a = 0.25, 0.6
    x = [0.0] * d
    if os.path.exists(out + ".state"):
        x = json.load(open(out + ".state"))["x"]
    rng = random.Random(12345)
    pool = mp.get_context("spawn").Pool(4, initializer=_init)
    seed_base = 100000
    t0 = time.time()
    start_it = sum(1 for _ in open(out)) if os.path.exists(out) else 0
    for it in range(start_it, start_it + iters):
        D = [rng.choice((-1, 1)) for _ in range(d)]
        xp = [xi + c * di for xi, di in zip(x, D)]
        xm = [xi - c * di for xi, di in zip(x, D)]
        pp, pm = to_params(default, ks, xp), to_params(default, ks, xm)
        jobs = []
        for g in range(ngames):
            seed = seed_base + it * 1000 + g // 2
            jobs.append((pp, pm, seed, g % 2 == 0))
        res = pool.map(_game, jobs)
        score = sum(res) / ngames  # theta+ win rate
        diff = 2 * score - 1
        ak = a / (1 + it / 100) ** 0.602
        x = [xi + ak * diff * di / (2 * c) * c for xi, di in zip(x, D)]  # step = ak*diff*D/2
        rec = dict(it=it, score=score, x=x, t=time.time() - t0)
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        json.dump(dict(x=x, ks=[list(k) for k in ks]), open(out + ".state", "w"))
        if it % 5 == 0:
            print(it, f"{score:.3f}", f"{time.time()-t0:.0f}s", flush=True)
    params = to_params(default, ks, x)
    json.dump(params, open(out + ".params.json", "w"), indent=1)


if __name__ == "__main__":
    main()
