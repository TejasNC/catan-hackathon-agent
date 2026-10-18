# Red-team of `army/comboop1` (2026-10-17, ~40 min budget)

Box: 4 cores (a slow dev box). All adversaries and scripts are in `redteam/`;
raw outputs in `redteam/out/`.

## Summary

| # | Finding | Severity | comboop1-specific? |
|---|---|---|---|
| 1 | Clock overrun in very long games (2 / 500 clocked games vs robber-spammer, both lost; 37–42 random moves each) | medium | yes (turn-plan CPU ~2x v5) |
| 2 | Single decisions up to 420 ms (MARITIME_TRADE / YOP / MONOPOLY with turn-plan), entered while `cpu_left` ≈ 0.45 s | medium (cause of #1) | yes |
| 3 | Ends turn holding a buildable settlement, repeatedly (value fn prefers the "ready_settle" hand bonus over +1 VP) | low–medium | no (v5 does it at the same rate) |
| 4 | Monopoly played for 1 card in ~30% of plays | low | no (v5 similar) |
| 5 | No crash / illegal index / exception found | — | — |
| 6 | No exploit found: all simple adversaries ≥ 0.84, comboop1 ≥ v5 on each | — | — |

## 1. Robustness / legality — clean

- 100 clocked games vs a fuzzing random bot (`redteam/fuzz_random.py`, 80 % non-END_TURN moves → many
  dev plays, odd trades, discards): **100/100 wins, errors=0, timeouts=0, crashes=0.**
- 600 more clocked games vs `robber_spam` (seed0 778000 / 990500 / 991000): errors=0, crashes=0.
- 600 in-process games vs the three adversaries below: no exceptions.
- Edge cases (empty bank, deck exhausted, 0-steal robber, discards) occurred naturally in these games;
  the fuzz bot drains the dev deck often. None raised. I did **not** hand-construct a road-building-with-no-legal-road
  state (ran out of time).

## 2. CPU

Clocked (`tools/par_eval.py`), comboop1 vs `robber_spam`:

| run | games | win | mean CPU/game | worst | over_budget |
|---|---|---|---|---|---|
| seed0 778000 | 100 | 0.780 | 664 ms | 1510 ms | **2** |
| seed0 990500 | 200 | 0.835 | 580 ms | 1330 ms | 0 |
| seed0 991000 | 200 | 0.845 | 576 ms | 1410 ms | 0 |
| v5, seed0 990500 | 200 | 0.800 | 422 ms | 1300 ms | 0 |
| vs fuzz, seed0 777000 | 100 | 1.000 | 548 ms | 1220 ms | 0 |

**Finding 1.** The two overruns (games 29 and 63 of seed0 778000) were 159- and 168-turn games with
137 / 149 decisions. Past ~96 decisions the allowance is capped at 1.5 s, so the clock stops growing while the bot keeps paying for search.
Both games went `over='cpu'`, then 37 / 42 random moves, and **both were lost**. A robber-spamming opponent stretches games (several games
>100 turns), so an opponent can drive this. On a faster machine the rate should be
much lower, but the margin is thin: 4 of 500 games finished at ≥1.41 s of 1.50 s.

**Finding 2: slowest decision types** (unclocked in-process, so search always on; 600 games, ~33k decisions):

| decision | mean | p99 | max |
|---|---|---|---|
| PLAY_TURN → MARITIME_TRADE | 26–33 ms | 130–172 ms | **421 ms** |
| PLAY_TURN → PLAY_MONOPOLY | 13–18 ms | 65–104 ms | 248 ms |
| PLAY_TURN → END_TURN | 8–12 ms | 54–88 ms | 205 ms |
| PLAY_TURN → BUILD_ROAD / SETTLEMENT | 18–24 ms | 83–144 ms | 190 ms |
| PLAY_TURN → YEAR_OF_PLENTY | 29–35 ms | 117–156 ms | 180 ms |
| v5, same games (max of any type) | — | — | 122 ms |

The turn-plan (`cop1_core._SearchAgent.decide`) runs whenever `cpu_left ≥ MIN_CPU = 0.45 s`, and its cost
is unbounded: top-3 + base candidates × `finish_turn` up to 6 steps × `eval_action` over every legal action
(20+ maritime trades with a big hand), plus the base's trade second step. A 420 ms decision started at
`cpu_left = 0.46` lands at ≈0.04 s, which is in panic mode, and leaves the bot close to the overrun in #1. In a logged
replay, a single YOP decision at `cpu_left = 0.4525` took 150 ms.

**Suggested fix (cheap):** give the turn-plan a deadline. Check `time.process_time()` against
`start + min(0.08, 0.25*(cpu_left-0.45))` inside the candidate loop and inside `finish_turn`, and keep the
best result found so far (the base choice is always the fallback). Also scale `MIN_CPU` with the decisions
remaining: past the 1.5 s cap the clock stops growing, so require e.g.
`cpu_left > 0.45 + 0.01*expected_remaining_decisions`. As a second guard, cap `finish_turn` to the top-12
actions by 1-ply score.

## 3. Exploitability: no loophole found

Simple adversaries (each built on VF's value function for whatever it doesn't override):

- `robber_spam`: always buys dev cards and plays knights at once, and robs the tile with comboop1's most pips.
- `road_plow`: always builds the road touching the most comboop1 roads/buildings (cutting its expansion).
- `dev_hoard`: never trades or builds roads, only cities/devs/knights (Largest-Army race, hoards cards
  to bait monopoly).

In-process, paired seeds, 200 games each (seed0 880000):

| adversary | comboop1 | v5 |
|---|---|---|
| robber_spam | 0.840 | 0.840 |
| road_plow | 0.980 | 0.960 |
| dev_hoard | 0.995 | 0.990 |
| robber_spam, clocked, 200 g, seed0 990500 | 0.835 | 0.800 |

comboop1 stays well above 60 % and is never worse than v5. The robber-spammer is the strongest simple
counter (≈16 % losses). It is a better VF-like bot, not an exploit of comboop1, but it is also what makes games long (#1).

## 4. Decision sanity (hook logs, `redteam/sanity.py`, 600 games)

- **Finding 3: ends turn while able to build a settlement.** 8 times in 200 games vs road_plow (all as second
  seat, turns 17–67). It repeats across turns: seed 880093 skipped the same settlement (node 2) on turns
  19, 21 and 25 at 2 VP vs 2 VP. Scores at turn 19 (`redteam/inspect_endturn.py 880093 redteam/road_plow.py`):
  END_TURN 1.759 vs BUILD_SETTLEMENT 1.378. The cause is the hand terms in `score()`: `ready_settle` (0.30),
  `card`×4, `ready_dev`, `partial` and `exp_n` (the open frontier node). Holding the cards outscores the
  +1 VP of a low-pip spot, so the bot keeps the cards and risks the 7. **v5 does the same (9 in the same
  200 games), so this is inherited from the value function.** Suggested fix: when BUILD_SETTLEMENT is legal, do not count
  `ready_settle`/`exp_n` in the END_TURN value. Equivalently, count `ready_settle` only when no
  settlement is buildable this turn. Low frequency (~4 % of games), and it costs tempo rather than games.
- **Finding 4: monopoly for 1 card:** 68 of 216 monopoly plays across the three opponents took exactly 1 card (0 plays took
  0 cards). v5 shows the same pattern (15/53). Suggested fix: require ≥2 cards, or a gain larger than the held-card
  value `dev_other`.
- Robber on a tile with one of its own buildings: 58 / 4,797 robber moves (1.2 %). I did not check whether
  the opponent also sat on those tiles, so this is probably benign.
- Trading at a worse rate than an available port: 0. Ending turn while a city was buildable: 0.
- Discards: 1–5 ms, no anomaly.

## Not covered (time)

Hand-built edge states (road building with no legal road, 0 knights left in the deck), the 2-player turn limit,
and adversaries vs `gauntlet.py`'s full army.
