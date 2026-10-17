"""Run catan_kit.evaluate with the CPU allowance divided by a factor.

    python tests/stress_clock.py --factor 2 --a agent_v2/agent.py --b examples/f_agent.py --games 200

factor=2 halves the base, the increment and the ceiling: the same as the agent running twice as
slow as it does here. Use it to check the clock guards and the margin before the scoring machine.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catan_kit._patch import ensure_hash_seed  # noqa: E402


def main():
    ensure_hash_seed()
    from catan_kit import evaluate, match
    p = argparse.ArgumentParser()
    p.add_argument("--factor", type=float, default=2.0)
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--games", type=int, default=200)
    p.add_argument("--seed0", type=int, default=990000)
    args = p.parse_args()
    match.CPU_BASE_S /= args.factor
    match.CPU_PER_DECISION_S /= args.factor
    match.CPU_MAX_S /= args.factor
    evaluate.run(args.a, args.b, args.games, args.seed0)


if __name__ == "__main__":
    main()
