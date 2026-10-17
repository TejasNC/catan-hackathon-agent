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

Gauntlet results: see below (filled in as they finish).
