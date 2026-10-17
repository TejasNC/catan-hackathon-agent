# 1v1-community heuristics vs v5

h2h = `tools/h2h.py X zoo/v5_final.py 600 4 2600000` (paired boards, no clock). CI = ±1.96·SE ≈ ±0.040.
Pass bar for follow-up (1200 more on seed 2700000 + 600 vs fregime): > 0.53. **No variant reached it**,
so no follow-up runs were made. All code is in `bot/agent.py` behind params that default OFF
(v5 behaviour unchanged; control `h0_ctrl` = 0.500 exactly on paired boards).
Trigger counts were checked in 6 games: every heuristic fires (knight-hold 8/22 knight decisions,
monopoly gate blocks 12/20, robber bonus on 133/972 robber evaluations).

| variant | params | h2h vs v5 | n | vs fregime |
|---|---|---|---|---|
| h1 knight hold | kn_hold=0.15 | 0.508 ± 0.040 | 600 | – |
| h1b knight hold | kn_hold=0.35 | 0.498 ± 0.040 | 600 | – |
| h2 bottleneck robber | rb_short=0.15, rb_only=0.10 | 0.485 ± 0.040 | 600 | – |
| h2b bottleneck robber | rb_short=0.05, rb_only=0.05 | 0.502 ± 0.040 | 600 | – |
| h3 duplicate-number discount | dup=0.6 | 0.470 ± 0.040 | 600 | – |
| h3b duplicate-number discount | dup=0.85 | 0.510 ± 0.040 | 600 | – |
| h4 plow / contested spots | plow=0.08 | 0.472 ± 0.040 | 600 | – |
| h4b plow / contested spots | plow=0.03 | 0.508 ± 0.040 | 600 | – |
| h5 monopoly timing | mono_min=3 | 0.512 ± 0.040 | 600 | – |
| h5b monopoly timing | mono_min=4 | 0.507 ± 0.040 | 600 | – |
| h6 combo (h1 + h5) | kn_hold=0.15, mono_min=3 | 0.505 ± 0.040 | 600 | – |

Reading: strong settings (dup 0.6, plow 0.08, robber 0.15) are mildly negative (−0.7 SE…−1.5 SE);
weak settings are indistinguishable from v5. Same plateau as before: a self-play-tuned 1-ply value
function already absorbs these effects (e.g. production loss from the robber is in V, so the
"bottleneck" bonus double counts).

## Robustness ideas (CVaR_0.5 over an archetype gauntlet)

New: `zoo/arch/` (frozen v5 with extreme weights: ows_zealot, road_plower, port_trader, blocker,
greedy), `tools/gauntlet.py` (X vs 5 archetypes + v3 + fregime + v5 mirror; reports mean and
CVaR_0.5 = mean of the worst half), `tools/spsa_cvar.py` (SPSA on J = 0.5·mean + 0.5·CVaR_0.5,
fregime held out). Variants (params in bot/agent.py, default off):
r1 adapt_k=1.0 (in-game opponent profiling: opp_k → 1.0 vs non-hoarding knight players),
r2 rob_aware=0.4 (expected robber on each player's best tile), r3 army_give=0.6 (stop valuing
the army race when 2+ knights behind), r4 conc_cap=8 (concave per-resource production).

Note: v5's opp_k = 0.74 and knight_hand = 0.09 were tuned by SPSA in **self-play** (θ⁺ vs θ⁻),
not against F, so they are already mirror-tuned.

### Gauntlet (`tools/gauntlet.py X 100 4 2800000`, 100 paired games per opponent, 800 per row)

CVaR_0.5 = mean of the worst 4 of 8 cells; its CI is about ±0.05.

| variant | mean | CVaR_0.5 | ows | road | port | blocker | greedy | v3 | fregime | v5 |
|---|---|---|---|---|---|---|---|---|---|---|
| v5 (control) | 0.584 | 0.510 | 0.69 | 0.61 | 0.58 | 0.50 | 0.54 | 0.50 | 0.75 | 0.50 |
| r1 profiling, adapt_k=1.0 | 0.586 | 0.510 | 0.69 | 0.63 | 0.58 | 0.51 | 0.53 | 0.50 | 0.75 | 0.50 |
| r2 robber-aware, 0.4 | 0.583 | 0.500 | 0.66 | 0.64 | 0.59 | 0.49 | 0.49 | 0.52 | 0.77 | 0.50 |
| r3 army give-up, 0.6 | 0.583 | 0.513 | 0.69 | 0.61 | 0.56 | 0.50 | 0.53 | 0.52 | 0.75 | 0.50 |
| r4 concave prod, cap 8 | 0.571 | 0.493 | 0.65 | 0.61 | 0.59 | 0.47 | 0.52 | 0.54 | 0.75 | 0.44 |
| s1 CVaR-SPSA weights | 0.491 | **0.400** | 0.58 | 0.57 | 0.42 | 0.35 | 0.50 | 0.47 | 0.68 | 0.36 |

h2h vs v5 (600 games, seed 2600000): r1 0.497, r2 0.502, r3 0.507, r4 0.502, **s1 0.463** (all ±0.040).

**CVaR-SPSA** (`tools/spsa_cvar.py 40 6`: 40 iterations, 7 opponents × 6 games per θ±, fregime held out)
made things clearly worse: CVaR 0.51 → 0.40, held-out fregime 0.75 → 0.68, h2h 0.463. Why: with 6
games per opponent each cell has SE ≈ 0.2, so J = mean + worst-half is dominated by which cells
got unlucky. The min-of-noisy-cells is a biased, high-variance signal, and the weights random-walked
(rms log-move 0.40, opp_k 0.74 → 0.52). To work, the gauntlet objective needs ≥ 30 games per
opponent per θ (≈ 400 games per iteration, ~45 s) or a smooth surrogate (mean of logits).

Reading: no variant moves the floor; every difference is < 1 SE. v5's floor is set by the
near-mirrors (blocker = v5 with opp_k 1.25, v3, v5 itself), where paired boards split 1–1
almost every time: the dice decide those games, not the weights. The profiler works (alpha
moves 0 → 1 within games) but moving opp_k from 0.74 toward 1.0 changes nothing measurable,
consistent with opp_k having been tuned in self-play already.
