# Team tools

Run from the repository root with the environment active (`source .venv/bin/activate`).

## `parallel_eval.py`: evaluate on several cores, log every run

```bash
python tools/parallel_eval.py --a my_team/agent.py --b examples/f_agent.py --games 1000 --tag "v1 baseline"
python tools/parallel_eval.py --a my_team/agent.py --b examples/f_agent.py examples/random_agent.py other/agent.py
```

- Same boards, dice, seats and clock as `catan_kit.evaluate`, split into fixed 20-game chunks. The
  same command gives the same games on any machine and with any `--workers`.
- Each run appends a row per opponent to `runs/runs.csv` (commit, agent hash, win rate, CI, CPU,
  faults) and writes per-game records to `runs/records/<run id>.jsonl`. This is the experiment
  table for the report.
- `--workers` defaults to 4. More workers inflate CPU readings on this laptop (hybrid CPU) and can
  push an agent over its clock. Check timings with `--workers 1` before submitting.
- `--strict` exits with status 1 on any error, timeout, crash or game over the clock.
- Seeds: the default `--seed0 990000` is the kit's. Keep it for evaluation and use other seeds
  (for example below 900000) for tuning or training, so you don't overfit to the eval set.

## `package.py`: build and test the submission zip

```bash
python tools/package.py my_team
```

It checks the folder (agent.py at the top, at most 100 MB, no compiled files, only allowed imports),
writes `submissions/my_team-<time>.zip`, unzips it into a fresh folder and plays that copy against F.
Only upload a zip that ends with `ready`.

Uploading happens from the team machine (each upload counts, 10 at most):

```bash
scp submissions/my_team-<time>.zip team<yourteam>@32.190.233.160:~/
ssh team<yourteam>@32.190.233.160 '~/upload.sh my_team-<time>.zip'
```
