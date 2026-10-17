# Bot army — opponents for evaluation

Every folder is a self-contained agent (`agent.py`, plus a uniquely named helper module where needed),
loadable by the kit harness and by `tools/h2h.py`. **Use these as the opponent pool when evaluating a
new candidate:**

```
python tools/gauntlet.py path/to/candidate/agent.py 400        # candidate vs every bot below
python tools/gauntlet.py cand.py 400 4 4000000 --skip ab2       # ab2 is slow (unclocked alpha-beta)
python tools/par_eval.py --a cand.py --b army/f/agent.py --games 1000 --seed0 123000   # clocked F number
```

F is a measuring stick only: never tune against it.

| Bot | What it is | Known strength |
|---|---|---|
| `f` | catanatron `ValueFunctionPlayer` (the hackathon's F) | reference |
| `ab2` | catanatron AlphaBeta depth 2 + pruning, F's value fn (unclocked; slow) | 0.575 vs F (40 g) |
| `fregime` | F + the team's regime correction (implemented from the brief) | 0.570 vs F (400 g) |
| `v1` | first value-function agent (hand weights, trade lookahead) | 0.635 vs F (200 g) |
| `v2` | v1 + knight / road-building follow-up step | 0.683 vs F (400 g) |
| `v3` | v2 + snake-draft opening | 0.726 vs F (1000 g) |
| `v5` | v3 + SPSA self-play weights — **submission #1** | 0.791 vs F (1000 g); leaderboard F 0.779, O 0.626 |
| `regime_b` | v5 + regime B weights | 0.517 vs v5 (2400 g), 0.773 vs F |
| `turnplan` | v5 + within-turn turn-plan lookahead (top-3, margin 0.05) | 0.519 vs v5 (1800 g), 0.785 vs F |
| `combo` | v5 + regime B + turn-plan (`bot_combo/`) | 0.524 vs v5 (3000 g), 0.793 vs F |
| `pasted` | team variant: v5 + regime 0.75 + robber-block risk, opponent profiling, monopoly/knight bonuses | 0.518 vs v5, 0.510 vs combo, 0.760 vs fregime, 0.792 vs F (600 g each) |
| `op1` | v5 + learned opening: P(win \| 4 settlements) logistic model fit on 16k v5-vs-v5 games with perturbed openings (AUC 0.74), draft search predicting the opponent's picks with v5's draft, CPU-deadline guarded (see `army/op1/README.md`) | 0.543 vs v5, 0.588 vs v2, 0.590 vs v3, 0.685 vs v1 (600 g each, paired); 0.786 vs F (1,600 g pooled; v5 0.761 on the same games) |
| `adapt` | opponent-adaptive: Thompson-sampling bandit over 4 strategy arms (combo, v5, block, race), one arm per game, learns per opponent across the games of one process (`bot_adapt/`) | 0.805 vs F (400 g, clocked), 0.530 vs v5 (400 g, clocked) |
