# op1: M plus a learned, opponent-aware opening

op1 is this folder: `agent.py`, `op1_opener.py` (draft search), `op1_mbase.py` (M = v5, unchanged)
and `open_model.json` (the learned weights). It is byte-for-byte the evaluated candidate,
with the helper modules renamed so they cannot collide with other army bots in one process. It plays exactly like M (`army/v5`) after the opening. The difference is how it places its
two initial settlements.

## 1. Why the opening

We tried improving M's mid-game play in four ways (INSIGHTS.md), and none beat M:

- searching deeper on M's own value function;
- simulating the opponent's reply turn with M's exact policy;
- SPSA-fitting M's weights against M;
- large strategy shifts.

M is at a broad optimum of its own evaluation.

The opening is different, for three reasons:

- **It decides a lot.** In 2-player Catan the four initial settlements fix most of each player's
  production for the whole game. A model of the outcome from the opening alone reaches AUC 0.74
  (below).
- **There is time to think.** The first decision gets the 300 ms base allowance plus 12.5 ms. M
  spends a few milliseconds on it.
- **M's draft is a fixed hand formula**: a weighted production, diversity and port score of a pair
  of nodes, with a snake-draft lookahead. Nothing in it was fitted to who actually wins.

## 2. The model: P(win | opening)

**Data.** 16,000 M-vs-M games (`tools/gen_open.py`). In each game, every initial settlement was
M's own pick, or with probability 0.5 a random pick among the 10 free nodes with the most pips. The
perturbation shows the model openings M would never choose. When the opening ended, we recorded
features of both players' settlements, and the label was who won.

**Features**, per player (`cands/open_feats.py`):

- production pips per resource, total pips
- number of distinct resources, number of distinct dice numbers
- 3:1 port, pips of the resource of any 2:1 port held
- city potential min(wheat, ore), road potential min(wood, brick), settlement potential
  min(wood, brick, sheep, wheat)
- expansion terms (zero at decision time, see section 5)

**Model.** Logistic regression on (my features − opponent's features) plus a seat flag
(`tools/fit_open.py`). It is mirrored, so it is symmetric between the seats.

| | held-out log loss | AUC |
|---|---|---|
| seat only | 0.693 | 0.50 |
| opening model | 0.600 | 0.739 |

Gradient boosting on the same features did no better (AUC 0.733), so the linear model ships. It is
17 numbers in `open_model.json`.

**What it learned.** Coefficients per raw unit, on the difference between the players:

| Feature | Weight | Reading |
|---|---|---|
| distinct resources | +0.28 per resource | variety matters most: in 2-player there is no one to trade with |
| 3:1 port | +0.24 | a general port is worth almost one extra resource type |
| min(wheat, ore) pips | +0.17 per pip | city potential |
| total pips | +0.16 per pip | raw production |
| min(wood, brick) pips | +0.12 per pip | road and settlement potential |
| 2:1 port resource pips | +0.08 per pip | a 2:1 port only pays when you produce its resource |
| min(wood, brick, sheep, wheat) | +0.06 per pip | settlement potential |
| single resources | at most ±0.02 | no resource is good on its own; balance is |

Compared with M's draft formula, the model puts much more weight on balance (the min terms) and on
the 3:1 port, and less on raw pips.

## 3. The search: draft against a predicted opponent

The snake order is P1, P2, P2, P1. At each of our settlement decisions, op1 enumerates its
candidates and plays the rest of the draft out on node sets, predicting the opponent's picks. It
then scores the final four settlements with the model:

| Our decision | What op1 does |
|---|---|
| P1, first pick | for each of our top 8 candidates: predict the opponent's 2 picks, then take our best last pick by the model; keep the candidate with the best final score |
| P1, last pick | the model's best completion (nothing left to predict) |
| P2, first of two picks | for each pair from our top 9: predict the opponent's last pick, score; play the first node of the best pair |
| P2, second pick | for each of our top 15: predict the opponent's last pick, score |

Candidates are ordered by M's own pair value, so the search starts from M's choice.

**Predicting the opponent.** M's draft is deterministic: it depends only on the board and the
settlements already placed. op1 carries a port of it (`Opener.m_pick`) and uses it as the model of
any opponent. Against M it is exact, apart from a cheaper top-5 inner loop. Against other strong
bots it is a reasonable proxy for "a good greedy drafter".

Everything else is played by M: roads, robber, trades, builds, dev cards.

## 4. Clock safety

The first version predicted M with its full nested draft (top 14 × 14 × all nodes) inside our own
candidate loop. It took up to 763 ms per decision and went over the clock in 153 of 400 games.
The shipped version:

- shrinks the inner prediction to the top 5 and our candidates to 8, 9 or 15;
- checks a CPU deadline in every candidate loop: min(150 ms, (cpu_left − 80 ms) / 2). At the
  deadline it plays the best pick found so far, or M's own pick;
- skips the opening search entirely below 120 ms of clock.

Clocked harness smoke test (20 games vs VF): 169 ms mean CPU per game, 290 ms worst, 0 games over
the clock, 0 errors. On an 8-core machine, over 1,000 games vs VF: 144 ms mean, worst decision 100 ms.

## 5. Known limitations

- **Roads are ignored** when scoring an opening on node sets, so the expansion features are zero at
  decision time. Their weights are small (+0.04, +0.02), and they are zero for both players, so
  they cancel.
- **The opponent model is M's draft.** Against VF, the real picks follow "most pips + 4 per resource".
  op2 adds online identification: once VF is recognised, picks are predicted with VF's formula.
- **The training data is M vs M.** Openings that only work with a different mid-game style are not
  represented.
- **The gain is the opening only:** about +2.5 to +5 points against every bot tested. Each 600-game
  row alone is within noise, but all point the same way.

## 6. Results

Paired games (same boards, dice and seats for op1 and for M), clock on:

| Opponent | op1 | M | gain | games | where |
|---|---|---|---|---|---|
| VF | 0.786 | 0.761 | +2.5 | 1,600 | laptop (600) + 8-core machine (1,000) |
| M (v5_final) | 0.543 | 0.500 | +4.3 | 600 | 8-core machine |
| v1 | 0.685 | 0.658 | +2.7 | 600 | 8-core machine |
| v2 | 0.588 | 0.558 | +3.0 | 600 | 8-core machine |
| v3 | 0.590 | 0.537 | +5.3 | 600 | 8-core machine |
| spsa1 | 0.588 | 0.560 | +2.8 | 600 | 8-core machine |

These were run with `tools/h2h.py`, which plays in-process with the harness's clock rule emulated.


## 7. Reproduce

The data-generation and fitting scripts (`gen_open.py`, `fit_open.py`) are not included in this
repository; the fitted model they produced is `open_model.json`. The commands, for reference:

```
python tools/gen_open.py data/open1.npz --games 4000 --workers 4
python tools/gen_open.py data/open2.npz --games 12000 --workers 8 --seed0 9000000
python tools/fit_open.py data/open1.npz data/open2.npz --out cands/open_model.json
python tools/h2h.py cands/op1.py examples/valuefn_agent.py --games 1000 --workers 8 --seed0 990000
```
