# After-state value regression (TD-Gammon idea, no bootstrapping): results

**Verdict: after-state data doesn't fix insight 6.** Pure learned-linear play is still far below v5
(19 % vs 16–25 % for the pre-decision fits). Every blend into v5 also loses. Nothing beat 0.53,
so no 1200-game follow-up was run.

## Setup

- Data: `tools/gen_data_after.py`. One row per turn: the state right after a player's END_TURN,
  recorded at the next decision (forced ROLL included, via a patched `Wrap.decide`). Features are
  `diff_feats(game, player_who_ended)` and the label is whether that player won.
  2000 self-play games of `zoo/v5_final.py`, eps 0.03, 4 procs, about 3 min.
- Pre-decision control on the **same policy**: `tools/gen_data.py zoo/v5_final.py 2000 4 runs/pre5`.
- Fit: `tools/fit.py` (logistic, symmetric augmentation, 80/20 holdout).

| data | states | holdout log-loss | holdout acc |
|---|---:|---:|---:|
| pre-decision, v2 data (INSIGHTS) | n/a | 0.445 | 0.78 |
| pre-decision, v5 data | 91,835 | 0.459 | 0.772 |
| after-state, v5 data | 132,089 | 0.479 | 0.754 |

## Fitted weights, VP units (weight / weight of `vp`)

| feature | v5 hand | pre (v2 data, INSIGHTS) | pre (v5 data) | **after (v5 data)** |
|---|---:|---:|---:|---:|
| vp | +1.000 | +1.000 | +1.000 | +1.000 |
| prodE_WOOD | +0.058 | +0.112 | +0.225 | +0.240 |
| prodE_BRICK | +0.072 | +0.143 | +0.141 | +0.211 |
| prodE_SHEEP | +0.063 | +0.204 | +0.211 | +0.168 |
| prodE_WHEAT | +0.088 | +0.167 | +0.146 | +0.156 |
| prodE_ORE | +0.087 | +0.131 | +0.198 | +0.170 |
| prodL_WOOD | +0.053 | +0.060 | +0.110 | +0.091 |
| prodL_BRICK | +0.064 | +0.107 | +0.065 | +0.103 |
| prodL_SHEEP | +0.057 | +0.121 | +0.101 | +0.099 |
| prodL_WHEAT | +0.079 | +0.069 | +0.104 | +0.089 |
| prodL_ORE | +0.078 | +0.072 | +0.101 | +0.087 |
| **div** | +0.274 | +0.522 | -0.280 | -0.186 |
| exp1 | +0.019 | +0.034 | +0.009 | +0.013 |
| exp2 | +0.010 | +0.015 | +0.055 | -0.006 |
| **expn** | +0.050 | +0.246 | +0.102 | +0.296 |
| card | +0.061 | +0.029 | +0.109 | +0.055 |
| discard | -0.176 | +0.036 | +0.036 | +0.051 |
| **ready_settle** | +0.302 | +1.064 | +0.800 | +0.930 |
| **ready_city** | +0.466 | +1.481 | +0.870 | +1.070 |
| ready_dev | +0.118 | +0.133 | +0.272 | +0.229 |
| **partial** | +0.059 | +0.981 | +1.421 | +1.591 |
| **knight_hand** | +0.095 | +0.539 | +1.413 | +1.085 |
| dev_other | +0.180 | +0.484 | +0.823 | +0.799 |
| **knights_played** | +0.157 | -0.218 | +0.084 | -0.231 |
| **port3** | +0.193 | +0.903 | +1.128 | +0.407 |
| port2 | +0.010 | -0.018 | +0.031 | +0.040 |
| **road_len** | +0.040 | +0.174 | +0.003 | +0.228 |
| army_lead | +0.202 | +0.435 | +0.483 | +0.550 |
| road_lead | +0.257 | -0.675 | +0.327 | -0.625 |

What the table shows:
- **The hoarding terms stay inflated.** `ready_city` 1.07, `ready_settle` 0.93, `partial` 1.59 and
  `knight_hand` 1.08 are still 2–20× the v5 values. In VP units a city costs `ready_city` + `partial`
  ≈ 2.7 VP of "held cards" and returns only +1 VP plus some production.
  `ready_city`/`ready_settle` are non-zero in only about 1.2–1.4 % of after-states. v5 almost always
  builds when it can, so these weights come from rare, selected states (eps moves, a blocked build).
- **`knights_played` is still negative** (−0.23), collinear with `army_lead` (+0.55).
- **`div` turns negative** in both v5-data fits (−0.19 / −0.28). The +0.52 in INSIGHTS came from
  v2 data, so it doesn't hold up across policies.
- **Production is about 3× v5** (≈0.19 vs ≈0.07 VP per unit, early game).

## Head-to-head vs `zoo/v5_final.py` (600 games, paired boards, seed 2100000, ±1.96σ)

| variant | what | score |
|---|---|---:|
| `runs/v9_lin_after.py` | (a) pure lin, after-state weights | 0.190 ± 0.031 |
| `runs/v9_lin_after_road.py` | (a) with `road_len` set back to the v5 value | 0.185 ± 0.031 |
| `runs/v9_lin_pre5.py` | pure lin, pre-decision weights, v5 data | 0.253 ± 0.035 |
| `runs/v9_lin_pre_fixidx.py` | pure lin, original v2 pre-decision weights (index bug fixed) | 0.162 ± 0.030 |
| `runs/v9_blend_after.py` | (b) v5 transition terms + all regression static assets | 0.247 ± 0.035 |
| `runs/v9_blend_prod.py` | v5 + regression production only (prod, prod_late, res_w) | 0.428 ± 0.040 |
| `runs/v9_blend_static.py` | v5 + regression div/exp/port/road_len only | 0.232 ± 0.034 |
| `runs/v9_blend_static_noroad.py` | same, with `road_len` at the v5 value | 0.295 ± 0.037 |
| `runs/v9_blend_expport.py` | same, with `div` also at v5 (only exp*/port* changed) | 0.403 ± 0.039 |

What the head-to-heads show:
- After-state pure lin (0.19) is *worse* than pre-decision pure lin on the same data (0.25).
- In the blend, the clamped `div`=0 costs about 11 points and `road_len` about 6. `exp_n`/`port3`
  cost another 10, and 3× production costs about 7. **Every regression weight we tried made v5 worse.**
- **Bug found in `runs/v4_lin.py`:** it passes `W[22]`, `W[23]` as `knight_hand`, `dev_other`.
  In `tools/feats.NAMES` those are `dev_other` and `knights_played`; `knight_hand` is index 21.
  So the dev-card EV used a *negative* `dev_other`. Fixing it moves the v2 weights from the reported
  10 % to 16 %: still a failure. (`runs/lin_v2.json` isn't in the repo, so I used
  `runs/data_v2_w.npy`, divided by its `vp` weight.) The v9 files use the correct indices
  (`tools/mk_lin_variant.py`).

## Why after-states weren't enough

Start from the policy-improvement theorem. If **V̂ = V^π** (the true value of v5's after-states),
then acting greedily on V̂ is at least as good as π = v5. So the losses have to come from
approximation error, and from where that error falls:

1. **The regression fits the wrong variance.** Most of the variance in game outcomes is
   *between games* (board, dice). A greedy move compares *sibling* after-states from one position,
   where differences are a fraction of a VP. Log-loss accepts large errors there if that buys a
   better fit across games, so proxy features (hand size, road length, port) soak up "this game is
   going well" credit.
2. **The weights are off-distribution.** v5 rarely ends a turn holding a city's cards, so
   E[win | `ready_city`] is estimated from rare, selected states. A greedy agent then visits those
   states all the time.
3. **Collinearity** (`knights_played` with `army_lead`, `div` with production) leaves individual
   weights unidentified. The fit is fine, but the gradients that drive decisions point the wrong way.

After-states remove the "about to act" bias, but none of 1–3. What would address them is real
TD(λ)/bootstrapping, so that targets are V̂(s′) of the next after-state rather than the final
outcome (less between-game variance). Better still, fit on **decision pairs**: maximise the
likelihood of the chosen action over its siblings, or regress the difference between sibling
after-states. That fits within-position comparisons directly, and none of the between-game
variance enters at all.

## Reproduce

```
python tools/gen_data_after.py zoo/v5_final.py 2000 4 runs/after 0.03 && python tools/fit.py runs/after
python tools/gen_data.py zoo/v5_final.py 2000 4 runs/pre5 0.03 && python tools/fit.py runs/pre5
python tools/mk_lin_variant.py runs/after_w.npy runs/v9_lin_after.py lin      # or ... blend
python tools/h2h.py runs/v9_lin_after.py zoo/v5_final.py 600 4 2100000
```
