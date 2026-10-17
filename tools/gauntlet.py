"""Archetype gauntlet: X vs each opponent on paired boards; reports per-opponent win rate, mean and
CVaR_0.5 (mean of the worst half). F is never in the gauntlet.
python tools/gauntlet.py X.py N_per_opp [procs] [seed0]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPPS = ["zoo/arch/ows_zealot.py", "zoo/arch/road_plower.py", "zoo/arch/port_trader.py",
        "zoo/arch/blocker.py", "zoo/arch/greedy.py", "zoo/v3_agent.py", "zoo/fregime_agent.py",
        "zoo/v5_final.py"]
_C = None


def _init(pa):
    global _C
    from tools.selfplay import load_agent_class
    _C = {o: load_agent_class(os.path.join(ROOT, o)) for o in OPPS}
    _C["X"] = load_agent_class(pa)


def _g(args):
    o, seed, a_first = args
    from tools.selfplay import play
    res, g = play(_C["X"](), _C[o](), seed, a_first)
    return o, (1.0 if res else (0.5 if res is None else 0.0))


if __name__ == "__main__":
    from catan_kit._patch import ensure_hash_seed
    ensure_hash_seed()
    pa, n = sys.argv[1], int(sys.argv[2])
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    s0 = int(sys.argv[4]) if len(sys.argv) > 4 else 2800000
    jobs = [(o, s0 + k // 2, k % 2 == 0) for o in OPPS for k in range(n)]
    with mp.get_context("spawn").Pool(procs, initializer=_init, initargs=(pa,)) as pool:
        r = pool.map(_g, jobs, chunksize=4)
    w = {o: sum(x for oo, x in r if oo == o) / n for o in OPPS}
    ws = sorted(w.values())
    mean = sum(ws) / len(ws)
    cvar = sum(ws[: len(ws) // 2]) / (len(ws) // 2)
    se = (0.25 / n) ** .5 / (len(ws) // 2) ** .5   # rough SE of the worst-half mean
    cells = " ".join(f"{os.path.basename(o)[:-3]}={w[o]:.3f}" for o in OPPS)
    print(f"{os.path.basename(pa)}: mean={mean:.4f} cvar50={cvar:.4f} (+-{1.96*se:.3f}) n/opp={n} | {cells}")
