# INSIGHTS — beating F (catanatron `ValueFunctionPlayer`) in 2-player Catan

Goal: > 70 % win rate against F under the hackathon clock, **without using F as a training signal**
(F is only ever used as a held-out measuring stick, never as an opponent inside an optimisation loop
and never as a teacher to imitate).

All numbers below come from runs in this repo (`tools/par_eval.py` = the official
`catan_kit.evaluate` harness split over 4 processes, same seeds `990000 + i//2`, seats alternated,
CPU clock enforced). 95 % intervals are ±1.96·sqrt(p(1-p)/n).

---

## 1. Understanding the opponent first

| Measurement (F vs F, 60 games, `tools/fstats.py`) | Value |
|---|---|
| Mean game length | 71 turns (≈35 per player) |
| Winner's VP sources | 2.5 settlements, 2.8 cities (5.6 VP), Longest Road 0.83 (1.7 VP), Largest Army **0.03**, VP cards 0.17 |
| Dev cards bought per game (both players) | 2.3 |
| Cards discarded to the robber per game | **17** |

Reading F's code (`catanatron/players/value.py`) explains these numbers:

* VP term `3e14`, production `1e8`, everything else ≤ `1e4`: it is a lexicographic greedy bot.
* It scores **public** VPs only, so a VP development card is worth `hand_devs = 10` to it — almost
  nothing. Played knights are worth `10.1`. → F almost never buys dev cards and never contests
  **Largest Army**: 2 free VP for anybody who does.
* It has no notion of hand-size risk beyond a −5 penalty → it hoards and loses ~17 cards per game to
  sevens.
* It is 1-ply: it never plans "trade, then build", except when the trade itself raises its score.

## 2. What others tried on Catan (literature check before building)

| Approach | Reported outcome | Lesson for us |
|---|---|---|
| catanatron `AlphaBetaPlayer` depth 2 vs F | README: 80 % but on **25 games**; our 40-game rerun (no clock, prunning) 57.5 % | search on F's own value function gives a modest edge, and under the clock it times out (problem statement: 0.1 %) |
| `SameTurnAlphaBetaPlayer` depth 2 | our 40-game rerun 42.5 %; 8 % under the clock | within-turn search alone does not fix a bad evaluation |
| Plain MCTS in Catan (Szita, Chaslot, Spronck 2010; 4-player DRL+MCTS work) | weak without domain knowledge; random playouts are poor | our random playout costs ~11 ms → at most ~1 playout per decision under our clock: MCTS is ruled out |
| Actor-critic / DQN from scratch (Utrecht thesis, Stanford AA228) | lost even to random agents (sparse reward, placement never learned) | pure RL from scratch is not viable in a 1-day hackathon |
| Buro-style linear evaluation fitted to outcomes (Othello) | world-class with simple features | worth trying: we can fit our own feature weights to self-play outcomes |
| SPSA self-play tuning (standard in chess engines, e.g. Stockfish "fishtest") | robust under noisy win/loss signal | lets us tune weights by playing our bot against itself — no F needed |

## 3. Cost model (measured, `tools/profile_prims.py`)

| Primitive | Cost on this dev box |
|---|---|
| `game.copy()` | 0.04 ms |
| `obs.sample_world()` | 0.07 ms |
| F's value function | 0.09 ms |
| copy + execute one action | 0.10 ms |
| random playout to the end | **11 ms** |

Clock: 12.5 ms per decision (+300 ms base) on the reference machine; F's mean on this box is ~250 ms
per game vs 158 ms on the reference machine → this box is ~1.6× slower. Budget ≈ 60–100 simulated
actions per decision. Conclusion: depth-1 to depth-2 evaluation of every action with a **good value
function** is what fits; deep search does not.

## 4. The agent (`bot/agent.py`)

Value function `V = Score(me) − k·Score(opp)`, every term in **VP units** (so weights are
interpretable: "a 6/8 tile pip is worth 0.11 VP early, 0.04 VP late"):

* VPs (my actual VPs incl. hidden VP cards; opponent: public VPs + expectation of its unknown cards)
* production per resource, robber-aware, phase-dependent (early production ≫ late production)
* resource diversity, ports (2:1 scaled by my production of that resource)
* expansion: pips of the best settlement spots reachable with 0/1/2 roads, number of open spots
* hand: card value, build-readiness bonuses (settlement / city / dev), partial progress, discard risk
* dev cards: knights in hand, other dev cards, played knights, army lead, longest-road lead

Decision procedure (one sampled world per decision):

1. every legal action is simulated on a copy and scored with V;
2. random outcomes are scored **in expectation** rather than on the sampled outcome
   (dev-card draw → expected value of the unseen pile; robber steal → +1 card for me, −1 for them);
3. trades / Year of Plenty / Monopoly get a second step: their value is the best build reachable
   right after them (this is how the bot plans "trade, then build");
4. Knight / Road Building get a second step: the greedy robber placement or two free roads.

## 5. Results log

All "vs F" rows use the official harness (`tools/par_eval.py`, CPU clock on). "h2h" rows are
in-process self-play on paired boards (`tools/h2h.py`), which is what we *select* on; F is only the
held-out check.

| # | Change | vs F | n / seeds | h2h | CPU/game (dev box) |
|---|---|---|---|---|---|
| v1 | value function + trade lookahead | 0.635 ± 0.067 | 200 / 990000 | | 248 ms |
| v2 | + knight / road-building follow-up step | 0.683 ± 0.046 | 400 / 990000 | | 256 ms |
| v3 | + snake-draft opening lookahead | 0.713 ± 0.044 | 400 / 990000 | 0.537 ± 0.056 vs v2 | 257 ms |
| v3 | (same, fresh seeds) | 0.726 ± 0.028 | 1000 / 123000 | | 270 ms |
| **v5** | **+ SPSA self-play-tuned weights (final `bot/agent.py`)** | **0.791 ± 0.025** | 1000 / 123000 | 0.550 ± 0.049 vs v3 | 264 ms |
| v5 | (same, third seed set, + low-clock fallback tier) | 0.787 ± 0.033 | 600 / 777000 | | 249 ms |
| v6 | SPSA continued to 126 iterations | 0.785 ± 0.026 | 1000 / 123000 | 0.523 ± 0.049 vs v5 | 255 ms |
| — | SPSA round 2 (170 more iterations from v5 weights + draft) | — | | 0.503 ± 0.040 vs v5 (n=600) | |
| — | endgame "danger mode" (opponent weight rises above 6 VP), 2 strengths | — | | 0.497 ± 0.040 each | |
| — | regime B (expand→build resource weights, fade expansion, late dev value; remote session) | 0.773 ± 0.034 (v5 same seeds 0.777) | 600 / 123000 | 0.517 ± 0.020 vs v5 (n=2400) | |
| — | turn-plan lookahead, top-3 actions, outcomes in expectation (remote session) | 0.785 | 600 / 123000 | 0.519 ± 0.023 vs v5 (n=1800) | 368 ms |
| — | opponent-roll expectimax at END_TURN (remote session) | — | | 0.42–0.46 | |
| — | robber lookahead (remote session) | — | | 0.498 | |
| — | combo: regime B + turn-plan | — | | 0.508 ± 0.028 vs v5 (n=1200) | |
| — | stronger army race / road race / both (vs F+regime bot) | — | | 0.745 / 0.732 / 0.728 vs F+regime (v5: 0.747) | |
| — | 1v1 community heuristics (remote session): defensive knight hold, Monopoly gate, bottleneck robber, duplicate-number discount, plow/contested spots | — | | 0.470–0.512 vs v5 (600 each); strong settings lean negative | |
| — | team-provided variant (`army/pasted`) | 0.792 ± 0.033 | 600 / 123000 | 0.518 vs v5, 0.510 vs combo, 0.760 vs fregime | 274 ms |
| — | SPSA with regime on (301 iters; regime 0.77, fade 0.26, dev 0.24) | — | | 0.503 ± 0.028 vs v5 (n=1200) | |
| — | 1v1-community heuristics: knight hold / bottleneck robber / duplicate-number discount / plow / monopoly timing (two strengths each) | — | | 0.47–0.51 vs v5 (n=600 each); strong settings mildly negative | |
| — | convex "progress toward target" hand features | — | | 0.417 ± 0.056 vs v2 | |
| — | hybrid: regression-informed asset weights | — | | 0.500 ± 0.057 vs v2 | |
| — | pure learned linear eval (logistic regression on outcomes) | — | | **0.100 ± 0.034** vs v2 (0.16 after fixing a weight-index bug in runs/v4_lin.py) | |
| — | same, fitted on END_TURN after-states (2000 v5 games, remote session) | — | | 0.190 vs v5 (pre-decision fit on same data: 0.253) | |
| — | blends: v5 transition terms + regression static-asset weights | — | | 0.247 / 0.428 / 0.403 vs v5 | |

Final agent robustness (h2h, 200 games each): vs v1 0.595, vs v3 0.555, vs WeightedRandom 1.000,
vs catanatron AlphaBeta depth 2 with pruning (unclocked, 60 games) 0.883.
v6 was not adopted: neither its head-to-head nor its F score was distinguishable from v5, and it had
1 game over the clock on an oversubscribed box. That game led to a no-simulation fallback tier
(`cpu_left < 0.10 s` → fixed build priorities) so a very long game can never fall into random moves.
Official `catan_kit.evaluate` path: 20 games, 0 errors, 0 over budget, 225 ms mean CPU.
Clock safety: max decision 33 ms, max opening decision 19 ms (allowance for decision 1 is 312 ms);
0 games over budget in all 3,000+ clocked games. Mean CPU ≈ F's, i.e. ~160 ms/game expected on
the reference machine (budget ≈ 1,000 ms).

## 6. Insights

1. **The evaluation is the bottleneck, not search depth.** AlphaBeta on F's own value function gains
   little (57.5 % in 40 games, and it cannot fit the clock), while a better 1-ply evaluation took us
   from 50 % to 64 % at the same CPU as F.
2. **Exploit what the opponent's objective ignores.** F scores public VPs only, so VP cards and
   played knights are invisible to it. Our bot wins Largest Army in ~89 % of its wins and holds
   ~1.5 hidden VP cards per won game — VP sources F never contests.
3. **Score chance nodes in expectation.** Scoring a dev-card purchase on the one sampled draw makes the
   decision a coin flip; the expected value of the unseen pile makes it stable. Same for robber steals.
4. **Delayed-payoff actions need a follow-up step** (+5 points). A knight's value is in the robber
   move it triggers; a 1-ply evaluator only sees "a knight left my hand" and ends the game with 1–1.4
   knights unplayed.
5. **Opening: the draft matters more than the spot.** Our greedy placements already had as many pips
   as F's (22.5 vs 22.0). Thinking of the snake order (P1 picks one, P2 two, P1 one) and scoring a pick
   as "my best pair minus the opponent's best pair" gave +3 points vs F.
6. **Fitting a value function to outcomes is a trap for greedy play (the most instructive failure).**
   Logistic regression of the winner on our features fits well (78 % holdout accuracy, log-loss 0.445)
   but the bot using it wins only 10 % against the hand-tuned one. Reason: features that *predict*
   winning are not features worth *choosing*. "Holding the cards for a city" gets +1.48 VP, more than
   building the city gains (+1 VP + production − the bonus − the hand terms), so the learned bot hoards
   and never builds. Played knights even get a negative weight (collinear with army lead). This is the
   pre-decision vs after-state problem TD-Gammon avoids by scoring after-states and bootstrapping.
   **Fitting on after-states alone does not fix it** (0.19 vs v5; ready_city still 1.07 VP, partial
   1.59 VP): log-loss mostly explains between-game variance (board, dice), and rare, collinear states
   get inflated weights. What would fix it is a *decision-level* signal — pairwise ranking of the
   chosen after-state against its siblings, or genuine TD bootstrapping — not more outcome regression.
7. **…but the regression is a good diagnostic for "static asset" weights.** It said diversity of
   resources (0.52 VP), open settlement spots (0.25), and late production were undervalued by hand.
   SPSA, independently and with no regression input, moved the same way: diversity ×2.3, and
   production re-weighted towards wheat/ore/brick.
8. **SPSA self-play tuning is cheap and strong (+6.5 points vs F, F never used).** 93 iterations of
   64 games θ⁺ vs θ⁻ (~12 min on 4 cores). The tuned vector beats its parent 55 % head-to-head, and
   the gain transfers to F (72.6 → 79.1 %). Largest moves (VP units): knight in hand 0.25 → 0.09
   (play them, don't hoard them), production per pip 0.11 → 0.055 with wheat/ore ×1.6, opponent weight
   0.9 → 0.74 (race, don't block), diversity 0.12 → 0.27, ready-for-city 0.35 → 0.47.
   SPSA's running θ⁺-vs-θ⁻ score stays ≈ 0.5 by design, so progress must be measured against a
   frozen parent, never from the SPSA log itself.
9. **Saving is hard for a 1-ply evaluator, and our convex "progress" fix made it worse** (41.7 % vs
   parent): it made the bot hold cards instead of converting them, and under discard risk the tempo
   loss outweighs the better builds.
10. **Variance is huge**: ±4.4 points at n = 400; several "improvements" at n = 40–60 vanished at
    n = 300. Paired boards (same board and dice for both seats) and ≥ 300-game head-to-heads were
    necessary to see anything.

**Leaderboard (organisers' machine), submission #1 = v5:** vs F 0.779 ± 0.026, vs O 0.626 ± 0.030,
164 ms mean CPU, 0 over clock, 0 faults. Our local F estimate (0.787–0.791) matched the leaderboard.
SPSA has plateaued: a second round from the tuned weights gives 0.503 head-to-head.

**Second, independent strong benchmark.** We implemented the team's "F + regime correction" bot
(`zoo/fregime_agent.py`, beats F 0.570 ± 0.049 in 400 games, never used for training). Against it:
v5 0.747, turn-plan 0.743, combo 0.738, regime B 0.733 (600 games each, same boards). The difficulty
ladder is consistent: F 0.79 > F+regime 0.75 > O 0.63.

**Plateau.** Every structural change since v5 (regime weights, turn planning, opponent-roll expectimax,
robber lookahead, danger mode, a second SPSA round, race weights) lands within ±2 SE of v5 on self-play,
on F, and on the F+regime bot. Two +1.7 SE changes did not add up (combo 0.508). Lesson: once a
1-ply value function is tuned by self-play, small structural changes are absorbed by the weights;
the next real gain needs a different model class (e.g. after-state TD learning), not more terms.
In games v5 loses to the stronger bot, the opponent holds Largest Army / Longest Road ~58 % of the
time (vs ~10 % in v5's wins) — but weighting those races more does not help, so it is a symptom
of a bad position, not a decision error.

**Decision audit (tools/audit.py, ~950 sampled v5 decisions, 24 Monte Carlo rollouts per candidate,
common dice, split-half unbiased regret).** Robber moves (n=247): +0.2 ± 1.4 win-rate points; discards
(n=112): +1.6 ± 1.3; ending the turn (n=74): +1.5 ± 2.3; opening roads/settlements, trades, builds,
knight timing: ≈ 0. The one clear flaw: **Monopoly played before rolling, +7.3 ± 5.7** (rolling first adds
information, and a pre-roll Monopoly swells the hand before a possible 7) → fixed in `bot_cop1fix/`.
An early n=35 robber signal (+2.9 ± 2.8) vanished at n=247, and re-weighting robber moves did nothing
(0.498 / 0.502 vs v5, n=1200): small audit samples mislead just like small win-rate samples.

## 7. Ideas not finished (for next time)

* TD(λ) on after-states with self-play (the principled fix for insight 6).
* Longer SPSA run (it was still moving) and SPSA on the opening-draft parameters separately.
* Spending the unused ~80 % of the clock: an expectimax over the opponent's next roll for END_TURN
  decisions, or several sampled worlds for hidden-VP-card risk late in the game.
* Opponent adaptation across games in one process (allowed by the rules): e.g. detect a bot that never
  contests Largest Army and lower our knight-play urgency.

## 8. Original hand-set weights (v1–v3), for reference

prod 0.11, prod_late 0.04, div 0.12, res_w (1.0, 1.0, 0.8, 1.1, 1.1), opp_k 0.9, exp1 0.02,
exp2 0.008, exp_n 0.06, card 0.045, ready_settle 0.30, ready_city 0.35, ready_dev 0.10,
partial 0.10, discard 0.18, knight_hand 0.25, dev_other 0.20, knight_played 0.22, army_lead 0.15,
road_len 0.05, road_lead 0.25, port2 0.012, port3 0.20.

## 9. Reproduce

```
python tools/par_eval.py --a bot/agent.py --b examples/f_agent.py --games 1000 --seed0 123000
python tools/h2h.py bot/agent.py zoo/v3_agent.py 400          # self-play comparison
python tools/spsa.py 100 64 runs/spsa.jsonl                     # SPSA tuning (no F)
python tools/gen_data.py zoo/v2_agent.py 1500 3 runs/data 0.03 && python tools/fit.py runs/data
```

Submission: zip the `bot/` folder (`agent.py` only; imports catanatron + stdlib).
