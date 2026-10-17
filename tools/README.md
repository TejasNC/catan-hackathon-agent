# Tools

Run everything from the repository root with the environment active (`source .venv/bin/activate`).
Scripts that play games set `PYTHONHASHSEED=0` themselves (or restart with it), so runs replay exactly.

| Tool | Purpose |
|---|---|
| `par_eval.py` | The official `catan_kit.evaluate` harness (CPU clock on), split over N processes. Same seeds and seat convention |
| `parallel_eval.py` | Same harness in fixed 20-game chunks, with every run logged to `experiments/runs.csv` (see below) |
| `h2h.py` | Fast in-process head-to-head between two agent files on paired boards (no clock). Used for self-play comparisons |
| `gauntlet.py` | A candidate against every bot in `army/`, plus the mean |
| `spsa.py` | SPSA self-play tuning of `bot/agent.py`'s weights ($\theta^+$ vs $\theta^-$, log-space perturbations) |
| `gen_data.py`, `feats.py`, `fit.py` | Self-play positions → features → logistic regression of the winner (the "learned evaluation" experiment) |
| `audit.py` | Decision audit: Monte Carlo rollout regret of the bot's choices, per decision type |
| `selfplay.py` | In-process game runner with a decision hook (used by most tools) |
| `stats.py`, `opening_stats.py`, `fstats.py`, `timing.py`, `profile_prims.py`, `lib_match.py` | Game statistics, opening quality, F-vs-F statistics, per-decision timing, engine micro-benchmarks, catanatron library matches |
| `package.py` | Build and check a submission zip |

## `parallel_eval.py`: evaluate on several cores, log every run

```bash
python tools/parallel_eval.py --a army/comboop1/agent.py --b examples/f_agent.py --games 1000 --tag "comboop1"
python tools/parallel_eval.py --a my_team/agent.py --b examples/f_agent.py examples/random_agent.py other/agent.py
```

- **Same games as the official script:** same boards, dice, seats and clock as `catan_kit.evaluate`,
  split into fixed 20-game chunks. The same command gives the same games on any machine and with any
  `--workers`.
- **Logging:** each run appends a row per opponent to `experiments/runs.csv` (commit, agent hash, win
  rate, CI, CPU, faults) and writes per-game records to `experiments/records/<run id>.jsonl`.
- **`--workers`:** defaults to 4. More workers inflate CPU readings and can push an agent over its
  clock, so check timings with `--workers 1`.
- **`--strict`:** exits with status 1 on any error, timeout, crash or game over the clock.
- **Seeds:** the default `--seed0 990000` is the kit's. Keep it for evaluation and use other seeds
  for tuning or training.

## `package.py`: build and test a submission zip

```bash
python tools/package.py army/comboop1
```

It checks the folder (agent.py at the top, at most 100 MB, no compiled files, only allowed imports),
writes `submissions/<name>-<time>.zip`, unzips it into a fresh folder and plays that copy against F.
Only upload a zip that ends with `ready`.

## `audit.py`: is the bot's choice the best move?

```bash
python tools/audit.py army/v5/agent.py 16 4 5200000 experiments/audit/run 24 4
python tools/audit.py --summary 'experiments/audit/*.jsonl'
```

- **Sampling:** samples real decisions from self-play.
- **Rollouts:** plays each candidate move out 24 times on common dice.
- **Unbiased regret:** the first half of the rollouts picks the best alternative; the second half
  measures its edge over the bot's choice.
