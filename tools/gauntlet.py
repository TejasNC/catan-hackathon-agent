"""Run a candidate against every bot in army/ (in-process, paired boards, no clock).

    python tools/gauntlet.py path/to/agent.py [games_per_bot=400] [procs=4] [seed0=4000000] [--skip ab2,...]

Reports the candidate's win rate (± 95% CI) against each bot and the mean over bots.
For the clocked number against VF use tools/par_eval.py.
"""
import os, sys, subprocess, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--skip")]
    skip = set()
    for a in sys.argv[1:]:
        if a.startswith("--skip"):
            skip |= set(a.split("=", 1)[1].split(","))
    cand = args[0]
    n = args[1] if len(args) > 1 else "400"
    procs = args[2] if len(args) > 2 else "4"
    seed0 = args[3] if len(args) > 3 else "4000000"
    rates = []
    for b in sorted(os.listdir(os.path.join(ROOT, "army"))):
        p = os.path.join(ROOT, "army", b, "agent.py")
        if b in skip or not os.path.exists(p):
            continue
        out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "h2h.py"), cand, p, n, procs, seed0],
                             capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": "0"}).stdout
        m = re.search(r": ([0-9.]+) \+-([0-9.]+)", out)
        if m:
            rates.append(float(m.group(1)))
            print(f"vs {b:10s} {m.group(1)} +-{m.group(2)}  (n={n})", flush=True)
        else:
            print(f"vs {b:10s} FAILED\n{out}", flush=True)
    if rates:
        print(f"mean over {len(rates)} bots: {sum(rates)/len(rates):.4f}")

if __name__ == "__main__":
    main()
