# How we built our Catan bot

*A 2-player Catan agent on catanatron, built in one intense day of experiments.*

---

## Prologue: the opponent

The goal: beat **VF**, catanatron's `ValueFunctionPlayer`, in 2-player Catan, on one CPU core with
about **1 second of thinking per game**.

Before writing a line of bot code, we watched VF play itself and read its source.

- VF ranks moves by a weighted sum whose weights are *tiers*: victory points $3\cdot10^{14}$ ≫
  production $10^8$ ≫ everything else. In practice it is a greedy, one-move-ahead bot.
- It counts only **public** victory points, so a VP card is worth ~nothing to it, and a played knight
  is worth $10.1$.
- Result, VF vs VF over 60 games: Largest Army in **3 %** of wins, 2.3 dev cards bought per game,
  **17 cards** thrown away to sevens per game.

We also checked the literature. Plain MCTS was weak in Catan, RL-from-scratch agents lost to random
players, and catanatron's AlphaBeta beats VF only modestly. Then we measured the clock: one random
playout costs 11 ms, the whole per-decision budget. **Deep search was off the table.** Our bet: a
better *evaluation*, not a deeper search.

---

## Act I: a value function in victory points (50 % → 64 %)

We wrote our own evaluation, with every term in the same currency, victory points:

$$V = \text{Score(me)} - k\cdot\text{Score(opp)}$$

Score includes actual VPs (hidden VP cards too), robber-aware production by resource, diversity,
expansion reach, ports, hand readiness, discard risk, dev cards, and army and road leads.

Two decision tricks came with it:
- random outcomes (a dev-card draw, a robber steal) are scored **in expectation**, not on one lucky
  sample;
- trades get a second step: a trade is worth the best build it enables this turn.

**v1: 63.5 % vs VF.** A 13-point jump from changing what the bot cares about.

## Act II: the knight that was never played (64 % → 68 %)

The game logs showed something odd. Our bot ended games holding 1–1.4 unplayed knights. A one-step
evaluator only sees "a card left my hand", because a knight's value is in the robber move it
triggers. We let knights (and Road Building) look one step further, to their best robber move or
free roads.

**v2: 68.3 %.**

## Act III: the snake draft (68 % → 73 %)

Our opening spots were as rich as VF's (22.5 vs 22.0 pips), so the spots weren't the problem. The order
was. In 2-player Catan the picks go P1, P2, P2, P1. We scored each pick as *my best pair minus the
opponent's best pair* after they respond.

**v3: 72.6 % over 1000 fresh games.** The 70 % target was crossed.

## Act IV: the most instructive failure

Could the evaluation be *learned* instead of hand-set? We fitted a logistic regression of
"who won" on our features over 68,000 self-play positions. It fitted beautifully: **78 %**
accuracy on held-out positions.

As a player it won **10 %** of its games.

The reason: "holding the cards for a city" predicted winning more strongly than *building* the city
did, so the learned bot hoarded and never built. Prediction is not decision. (A later re-fit on
end-of-turn positions still scored 19 %.)

## Act V: tuning by playing ourselves (73 % → 79 %)

We borrowed a chess-engine trick, **SPSA**. Perturb all the weights at once, play $\theta^+$ against
$\theta^-$, and step toward the winner. VF was never used. In about 12 minutes on 4 cores the bot
learned to play its knights instead of hoarding them, to value wheat and ore more, and to race to
10 instead of blocking.

**v5: 79.1 % over 1000 held-out games.** An independent re-measurement on another machine agreed:
**0.779 vs VF**.

---

## Act VI: the plateau

Next we went wide, running experiments in parallel on several machines:

| Idea | Head-to-head vs v5 |
|---|---|
| Regime weights (expand → build) | 51.7 % |
| Turn planning (top 3 moves, played to end of turn) | 51.9 % |
| Averaging over the opponent's next roll | 42–46 % |
| Second SPSA round | 50.3 % |
| Community 1v1 heuristics (knight hold, plowing, …) | 47–51 % |
| Danger mode, race weights, robber lookahead | ~50 % |

Almost everything landed in the noise. A self-tuned evaluation absorbs small structural changes. Two
small gains did stack, though: regime + turn planning, **52.4 % over 3000 games**, became `combo`.

## Act VII: a learned opening

Meanwhile we attacked the one part SPSA couldn't reach. They learned **P(win | the four
opening settlements)** from 16,000 games (AUC 0.74) and built a draft search around it.
**`op1` beat v5 54.3 %**, the biggest gain since SPSA. Merged with combo it became **`comboop1`:
82.0 % vs VF**.

## Act VIII: the bandit that couldn't remember

An opponent-adaptive bot seemed like the next step: a Thompson-sampling bandit over four play
styles that learns, across the games of one process, which style beats the current opponent. It
worked: 80.5 % vs VF, 53 % vs v5.

But it only helps when one process plays many games against the same opponent, and the statistics
are unforgiving: detecting a 5-point edge between two styles takes about **770 games per style**.
In short or freshly restarted matches the bandit has nothing to learn from, so it stayed an experiment
(`army/adapt`).

## Act IX: the audit and the red team

To close, we checked the bot's judgement directly. For ~950 real decisions we played the game out
from every candidate move, many times on the same dice. Was the bot's choice actually the best?

- Robber moves, discards, trades, builds, knight timing: **essentially optimal**.
- One clear mistake: **playing Monopoly before rolling** (+7.3 win-rate points of regret). Rolling
  first can only help.

A red-team session attacked `comboop1` with fuzzing and adversarial bots. It found no crashes and no
exploits, but 2 of 500 very long games ran out of clock. Both fixes went into **`comboop1_fix`**.

---

## Epilogue: what we learned

1. **Understand the opponent before optimising.** Our biggest edge came from reading VF's code: the VP
   cards and Largest Army it ignores.
2. **Under a tight clock, evaluation beats depth.** About 26 of our ~32 points came from what the bot
   values, not how far it searches.
3. **Predicting winners ≠ choosing moves.** Our best-fitting model was our worst player.
4. **Self-play tuning is cheap, and then it plateaus.** After that, gains came from structure: the
   opening, and bug fixes found by auditing.
5. **Small samples lie.** "Wins" at 40 games and a "flaw" at 35 decisions vanished at a few thousand.

| Version | What changed | vs VF |
|---|---|---|
| VF | — | 50 % |
| v1 | value function in VP units | 63.5 % |
| v2 | + knight follow-up | 68.3 % |
| v3 | + draft opening | 72.6 % |
| v5 | + self-play tuned weights | 79.1 % |
| combo | + regime + turn planning | 79.3 % (h2h +2.4 vs v5) |
| comboop1 | + learned opening | 82.0 % |
| comboop1_fix | + audit & red-team fixes | 77.0 % (400 g, fresh seeds; within noise) |
