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

| # | Change | vs F | n | CPU/game (dev box) | Notes |
|---|---|---|---|---|---|
| v1 | value function + trade lookahead | 0.635 ± 0.067 | 200 | 248 ms | first try |
| v2 | + knight / road-building follow-up | **0.683 ± 0.046** | 400 | 256 ms | knights were left unplayed: their value only appears after the robber move |

## 6. Insights so far

1. **The evaluation is the bottleneck, not the search depth.** AlphaBeta on F's own value function
   gains little, while a better 1-ply evaluation gains +18 points.
2. **Exploit what the opponent's objective ignores.** F's value function counts public VPs only; our
   bot gets Largest Army in ~89 % of its wins and holds ~1.5 VP cards — VP sources F does not contest.
3. **Score chance nodes in expectation.** Scoring a dev-card purchase on the one sampled draw makes the
   decision a coin flip; using the expected value of the unseen pile makes it stable.
4. **Delayed-payoff actions need a follow-up step.** A knight's value is in the robber move it
   triggers; a 1-ply evaluator sees only "a knight left my hand" and never plays it.
5. Opening quality was *not* the gap: average pips of our two initial settlements 22.5 vs F's 22.0,
   and similar in won and lost games.
