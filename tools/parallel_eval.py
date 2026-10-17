"""Play one agent against one or more opponents on many cores, and log every run.

    python tools/parallel_eval.py --a my_team/agent.py --b examples/f_agent.py --games 1000
    python tools/parallel_eval.py --a my_team/agent.py --b examples/f_agent.py examples/random_agent.py

Same boards, dice and seats as catan_kit.evaluate: game i is played on board seed0 + i // 2, with
seats alternating, under the same clock and limits (through catan_kit.match.play_chunk). Games are
split into fixed chunks of CHUNK games, one fresh pair of agent processes per chunk. An agent that
keeps state across games (an RNG, or anything it learns) therefore plays slightly differently from a
single evaluate run, which uses one process for every game. Chunks never depend on --workers, so
the same command gives the same games on any machine.

Every run appends one row per opponent to runs/runs.csv, and its per-game records to
runs/records/<run id>.jsonl, so any game can be replayed alone from its board seed and game index.

CPU per game is inflated when the machine is busy, and an agent pushed over its clock plays random
moves, which lowers its win rate too. The default of 4 workers keeps F within about 1.3x of its
quiet timing on this laptop (12 workers: 2.3x, with games over the clock). Confirm timings with a
quiet run (--workers 1) before you submit, and remember our machine is slower per core again.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from catan_kit._patch import ensure_hash_seed  # noqa: E402
from catan_kit import match  # noqa: E402
from catan_kit.evaluate import summarise  # noqa: E402

RUNS_DIR = os.path.join(ROOT, "runs")
CSV_FIELDS = ["run_id", "time", "commit", "tag", "a", "a_sha", "b", "games", "seed0", "win_rate",
              "ci95", "wins", "no_winner", "mean_cpu_ms", "worst_cpu_ms", "games_over_budget",
              "random_moves", "errors", "decisions", "timeouts", "crashes", "init_s", "workers",
              "wall_s"]
CHUNK = 20


def _play(args):
    path_a, path_b, indices, seed0, vps = args
    seeds = [seed0 + i // 2 for i in indices]
    return match.play_chunk(path_a, path_b, seeds, indices, vps=vps)


def chunks(games):
    """Consecutive game indices in chunks of CHUNK (even, so a board pair is never split)."""
    return [list(range(i, min(i + CHUNK, games))) for i in range(0, games, CHUNK)]


def evaluate(path_a, path_b, games, pool, seed0=990000, vps=10):
    """Return (summary dict, per-game records) for path_a against path_b."""
    t0 = time.time()
    jobs = [(path_a, path_b, c, seed0, vps) for c in chunks(games)]
    records, init_s = [], 0.0
    for recs, info in pool.map(_play, jobs):
        records.extend(recs)
        init_s = max(init_s, info["a_init_s"])
    records.sort(key=lambda r: r["game"])
    res = summarise(records)
    res.update(init_s=init_s, wall_s=time.time() - t0)
    return res, records


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def _commit():
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                               capture_output=True, text=True).stdout.strip()
        return out + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return ""


def report(path_a, path_b, res, games):
    lim = (f"{match.CPU_BASE_S*1000:g} ms + {match.CPU_PER_DECISION_S*1000:g} ms per decision, "
           f"at most {match.CPU_MAX_S*1000:g} ms")
    print(f"A = {path_a}")
    print(f"B = {path_b}")
    print(f"A win rate          {res['win_rate']:.4f} +-{res['ci95']:.4f}   ({res['wins']}/{games})")
    print(f"A mean CPU / game   {res['mean_cpu_s']*1000:8.1f} ms   (limit {lim})")
    print(f"A worst CPU / game  {res['worst_cpu_s']*1000:8.1f} ms")
    print(f"A games over budget {res['games_over_budget']:8d}      "
          f"(random moves played after the limit: {res['random_moves']})")
    print(f"A errors            {res['errors']:8d}      illegal index or exception, of "
          f"{res['decisions']} decisions")
    print(f"A timeouts/crashes  {res['timeouts']:3d} / {res['crashes']:<3d}")
    print(f"A load time         {res['init_s']:8.2f} s    (limit {match.INIT_TIMEOUT_S:.0f} s)")
    print(f"no winner           {res['no_winner']:8d}      (a loss for both sides)")
    print(f"wall clock          {res['wall_s']:8.1f} s")


def log(row, records, run_id):
    os.makedirs(os.path.join(RUNS_DIR, "records"), exist_ok=True)
    path = os.path.join(RUNS_DIR, "runs.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    with open(os.path.join(RUNS_DIR, "records", f"{run_id}.jsonl"), "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def main(argv=None):
    ensure_hash_seed()          # may restart this process with PYTHONHASHSEED=0
    p = argparse.ArgumentParser(description="Parallel catan_kit.evaluate, with a run log.")
    p.add_argument("--a", required=True, help="path to your agent file")
    p.add_argument("--b", required=True, nargs="+", help="one or more opponent agent files")
    p.add_argument("--games", type=int, default=1000, help="games against each opponent")
    p.add_argument("--seed0", type=int, default=990000, help="first board seed")
    p.add_argument("--vps", type=int, default=10)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--tag", default="", help="a note for the log, for example 'v2 depth-2 search'")
    p.add_argument("--no-log", action="store_true", help="do not write to runs/")
    p.add_argument("--strict", action="store_true",
                   help="exit with status 1 on any error, timeout, crash or game over the clock")
    args = p.parse_args(argv)

    stamp = datetime.datetime.now()
    commit, a_sha = _commit(), _sha(args.a)
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for k, path_b in enumerate(args.b):
            res, records = evaluate(args.a, path_b, args.games, pool, args.seed0, args.vps)
            report(args.a, path_b, res, args.games)
            print()
            results.append((path_b, res))
            if args.no_log:
                continue
            run_id = f"{stamp:%Y%m%d-%H%M%S}-{k}"
            log(dict(run_id=run_id, time=stamp.isoformat(timespec="seconds"), commit=commit,
                     tag=args.tag, a=args.a, a_sha=a_sha, b=path_b, games=args.games,
                     seed0=args.seed0, win_rate=round(res["win_rate"], 4),
                     ci95=round(res["ci95"], 4), wins=res["wins"], no_winner=res["no_winner"],
                     mean_cpu_ms=round(res["mean_cpu_s"] * 1000, 1),
                     worst_cpu_ms=round(res["worst_cpu_s"] * 1000, 1),
                     games_over_budget=res["games_over_budget"],
                     random_moves=res["random_moves"], errors=res["errors"],
                     decisions=res["decisions"], timeouts=res["timeouts"],
                     crashes=res["crashes"], init_s=round(res["init_s"], 2),
                     workers=args.workers, wall_s=round(res["wall_s"], 1)), records, run_id)

    if len(results) > 1:
        print("summary")
        for path_b, res in results:
            print(f"  vs {path_b:40s} {res['win_rate']:.4f} +-{res['ci95']:.4f}   "
                  f"cpu {res['mean_cpu_s']*1000:6.1f} ms   over {res['games_over_budget']}   "
                  f"errors {res['errors']}")
        print(f"  mean win rate {sum(r['win_rate'] for _, r in results) / len(results):.4f}")

    faults = sum(r["errors"] + r["timeouts"] + r["crashes"] + r["games_over_budget"]
                 for _, r in results)
    return 1 if args.strict and faults else 0


if __name__ == "__main__":
    sys.exit(main())
