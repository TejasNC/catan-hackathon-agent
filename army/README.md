# Bot army: every bot we built or benchmarked

Every folder is a self-contained agent (`agent.py`, plus uniquely named helper modules where needed)
that runs in the `catan_eval` harness and in `tools/h2h.py`. The strongest is **`comboop1`**.

Use them as the opponent pool when evaluating a new candidate:

```
python tools/gauntlet.py path/to/candidate/agent.py 400        # candidate vs every bot below
python tools/gauntlet.py cand.py 400 4 4000000 --skip ab2       # ab2 is slow (unclocked alpha-beta)
python tools/par_eval.py --a cand.py --b army/valuefn/agent.py --games 1000 --seed0 123000   # clocked, vs VF
```

VF is a benchmark only: never tune against it.

| Bot | What it is | Known strength |
|---|---|---|
| `valuefn` | catanatron `ValueFunctionPlayer` (VF) | reference |
| `ab2` | catanatron AlphaBeta depth 2 + pruning, VF's value fn (unclocked; slow) | 0.575 vs VF (40 g) |
| `fregime` | VF + a regime correction (expand → build resource weights) | 0.570 vs VF (400 g) |
| `v1` | first value-function agent (hand weights, trade lookahead) | 0.635 vs VF (200 g) |
| `v2` | v1 + knight / road-building follow-up step | 0.683 vs VF (400 g) |
| `v3` | v2 + snake-draft opening | 0.726 vs VF (1000 g) |
| `v5` | v3 + SPSA self-play weights | 0.791 vs VF (1000 g) |
| `regime_b` | v5 + regime B weights | 0.517 vs v5 (2400 g), 0.773 vs VF |
| `turnplan` | v5 + within-turn turn-plan lookahead (top-3, margin 0.05) | 0.519 vs v5 (1800 g), 0.785 vs VF |
| `combo` | v5 + regime B + turn-plan | 0.524 vs v5 (3000 g), 0.793 vs VF |
| `profiler` | v5 + regime 0.75 + robber-block risk, in-process opponent profiling, monopoly/knight bonuses | 0.518 vs v5, 0.510 vs combo, 0.760 vs fregime, 0.792 vs VF (600 g each) |
| `op1` | v5 + learned opening: P(win \| 4 settlements) logistic model fit on 16k v5-vs-v5 games with perturbed openings (AUC 0.74), draft search predicting the opponent's picks, CPU-deadline guarded (see `army/op1/README.md`) | 0.543 vs v5, 0.588 vs v2, 0.590 vs v3, 0.685 vs v1 (600 g each, paired); 0.786 vs VF (1,600 g pooled; v5 0.761 on the same games) |
| `adapt` | opponent-adaptive: Thompson-sampling bandit over 4 strategy arms (combo, v5, block, race), one arm per game, learns per opponent across the games of one process | 0.805 vs VF (400 g, clocked), 0.530 vs v5 (400 g, clocked) |
| **`comboop1`** | combo (v5 + regime B + turn-plan) with op1's learned opening; CPU-deadline guarded | 0.523 vs combo (1000 g), **0.820 vs VF** (1000 g; combo 0.787 on the same games), 0 games over the clock |
| `comboop1_fix` | comboop1 + decision-audit fix (never play Monopoly before rolling: rollout regret +7.3 ± 5.7 points) + stricter clock guard (turn-plan only with ≥ 0.9 s left) | 0.5025 ± 0.035 vs comboop1 (800 g; the fix fires rarely), 0.770 vs VF (400 g, fresh seeds), 0 errors / 0 over the clock |
