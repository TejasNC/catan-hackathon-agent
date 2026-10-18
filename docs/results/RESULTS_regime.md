# Regime experiment (expand → build)

Code: `bot/agent.py`, params `regime`, `reg_fade`, `reg_dev`, `reg_reach` (all default off → baseline unchanged;
sanity check defaults vs `army/v5/agent.py`: 0.495 ± 0.069, n=200).

- phi = max(phi_VP, phi_space), per colour, computed once per decision from the root sampled world.
  - phi_VP = clip((actual VP − 4)/4, 0, 1)
  - phi_space = 1 − min(1, best_open_spot_pips/10); 0 in the initial phase, 1 when no settlements are left
- res_w × (1 + regime·(mix − 1)), mix = (1−q)·EXPAND + q·BUILD, q = phi + 0.5(1−phi)
- expansion terms × (1 − reg_fade·phi); knight_hand / dev_other / knight_played × (1 + reg_dev·phi)
  (also in dev_ev / dev_val, so the dev-draw correction stays consistent)

## Results (h2h = in-process, paired boards, vs v5_final; ± = 95% CI)

| Variant | Params | h2h win rate | n | seeds | vs VF (600, seed0=123000) |
|---|---|---|---|---|---|
| A | regime=1, fade=0.7, dev=0.5 | 0.516 ± 0.028 | 1200 | 300000 | – |
| **B** | regime=0.5, fade=0.35, dev=0.25 | 0.521 ± 0.028 | 1200 | 300000 | **0.773 ± 0.034** |
| B (replication) | same | 0.513 ± 0.028 | 1200 | 500000 | |
| B pooled | | **0.517 ± 0.020** (+1.7 SE) | 2400 | | |
| C | regime=1 only (multipliers, no fade/dev) | 0.499 ± 0.028 | 1200 | 300000 | – |
| D | A + reg_reach=2 (two-road spots count too) | 0.517 ± 0.028 | 1200 | 300000 | – |
| v5 (reference) | – | 0.5 | | | 0.777 ± 0.033 (same 600 seeds); 0.791 on 1000 |

## Verdict: not adopted (default stays off)

- No variant clears the > 2 SE bar. Best (B, pooled n=2400) is +1.7 SE.
- vs VF, B equals v5 on the same seeds (0.773 vs 0.777).
- C ≈ 0.50: the resource-multiplier swing alone does nothing. Whatever small gain A/B/D show comes from fading
  expansion and boosting dev cards late.
- Spec quirk: right after setup, every legal spot is usually 2 roads away, so with 1-road reach phi_space
  can jump to 1 early. D (two-road reach) fixes this but scores no better than A.
- Next step if continued: SPSA-tune `reg_fade` and `reg_dev` only (keep `regime`=0), then do one more ≥2400-game h2h.

## Follow-up: SPSA with the regime turned on (VF never used)

- Started from v5 DEFAULT plus regime=0.5, reg_fade=0.35, reg_dev=0.25 (`experiments/agent_spsa_reg.py`); ran 301 iterations × 64 games.
- Tuned regime values: regime=0.77, reg_fade=0.26, reg_dev=0.24. Full params are in `experiments/spsa_reg_params.json`, loaded by `experiments/v9_spsareg.py`.

| Variant | h2h vs v5_final | n | seeds |
|---|---|---|---|
| v9_spsareg | 0.503 ± 0.028 | 1200 | 1800000 |

Not adopted: the tuned variant is no better than v5.
