"""Head-to-head between two agent files, in-process (no clock), paired boards, parallel.
python tools/h2h.py A.py B.py N [procs] [seed0]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp

_AB = None
def _init(pa, pb):
    global _AB
    from tools.selfplay import load_agent_class
    _AB = (load_agent_class(pa), load_agent_class(pb))

def _g(args):
    seed, a_first = args
    from tools.selfplay import play
    res, g = play(_AB[0](), _AB[1](), seed, a_first)
    return 1.0 if res else (0.5 if res is None else 0.0)

if __name__ == "__main__":
    from catan_eval._patch import ensure_hash_seed
    ensure_hash_seed()
    pa, pb, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    procs = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    s0 = int(sys.argv[5]) if len(sys.argv) > 5 else 300000
    with mp.get_context("spawn").Pool(procs, initializer=_init, initargs=(pa, pb)) as pool:
        r = pool.map(_g, [(s0 + k // 2, k % 2 == 0) for k in range(n)], chunksize=4)
    w = sum(r) / n
    print(f"{os.path.basename(pa)} vs {os.path.basename(pb)}: {w:.4f} +-{1.96*(w*(1-w)/n)**.5:.4f} (n={n})")
