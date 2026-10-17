"""Parallel version of catan_kit.evaluate: splits the board seeds over worker processes.

    python tools/par_eval.py --a agent/agent.py --b examples/f_agent.py --games 400 --procs 4
Same seeds/seat convention as evaluate.py (seed0 + i//2, game index i).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catan_kit._patch import ensure_hash_seed


def _work(args, q):
    from catan_kit import match
    a, b, seeds, idx, clock = args
    recs, _ = match.play_chunk(a, b, seeds, idx, clock_a=clock, clock_b=clock)
    q.put(recs)


def main():
    ensure_hash_seed()
    import multiprocessing as mp
    from catan_kit.evaluate import summarise
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--games", type=int, default=400)
    p.add_argument("--seed0", type=int, default=990000)
    p.add_argument("--procs", type=int, default=4)
    p.add_argument("--noclock", action="store_true")
    p.add_argument("--out", default=None)
    a = p.parse_args()
    t0 = time.time()
    idx = list(range(a.games))
    # chunk by board pairs so both seats of a board land in the same chunk
    chunks = [[] for _ in range(a.procs)]
    for i in idx:
        chunks[(i // 2) % a.procs].append(i)
    jobs = [(a.a, a.b, [a.seed0 + i // 2 for i in c], c, not a.noclock) for c in chunks if c]
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    ps = [ctx.Process(target=_work, args=(j, q)) for j in jobs]
    for pr in ps:
        pr.start()
    res = [q.get() for _ in ps]
    for pr in ps:
        pr.join()
    recs = [r for rr in res for r in rr]
    s = summarise(recs)
    print(f"A={a.a} B={a.b} games={a.games} seed0={a.seed0}")
    print(f"A win rate {s['win_rate']:.4f} +-{s['ci95']:.4f} ({s['wins']}/{s['games']}) no_winner={s['no_winner']}")
    print(f"A mean CPU/game {s['mean_cpu_s']*1000:.1f} ms worst {s['worst_cpu_s']*1000:.1f} ms "
          f"over_budget={s['games_over_budget']} errors={s['errors']} timeouts={s['timeouts']} crashes={s['crashes']} "
          f"decisions={s['decisions']}")
    sb = summarise(recs, "b")
    print(f"B mean CPU/game {sb['mean_cpu_s']*1000:.1f} ms over_budget={sb['games_over_budget']}")
    first = [r for r in recs if r["a_first"]]
    second = [r for r in recs if not r["a_first"]]
    print(f"A wins as first {sum(r['winner']=='a' for r in first)}/{len(first)}, as second {sum(r['winner']=='a' for r in second)}/{len(second)}")
    print(f"wall {time.time()-t0:.1f}s")
    if a.out:
        with open(a.out, "w") as f:
            json.dump(recs, f)


if __name__ == "__main__":
    main()
