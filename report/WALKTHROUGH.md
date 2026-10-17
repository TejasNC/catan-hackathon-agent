# The report, explained in plain English

This goes through `report.pdf` section by section, in the same order. For each part it says
what the report claims, what that means, and why things are the way they are.

---

## The whole story in one minute

1. We built a bot that plays 2-player Catan. It gets about **12 milliseconds of CPU per move**.
2. That is far too little time to think many moves ahead. So the bot does the opposite: it judges
   a position **at a glance**, using a scoring formula. The formula says how good a board position is
   for us, measured in victory points.
3. On every move, the bot tries **every legal move** on a copy of the game. It scores each resulting
   position with the formula and plays the move with the best score.
4. The numbers inside the formula were tuned by making the bot play **against slightly different
   versions of itself**, thousands of times, and keeping whatever won more (a method called SPSA).
5. The opening (where to place the first settlements) was **learned from 16,000 games**.
6. Result on the leaderboard: about **81 % against F** and **66 % against O**.
7. The main lesson: **a model that predicts who will win is not automatically good at choosing
   moves.**

## Catan words you need

| Word | Meaning |
|---|---|
| VP (victory point) | First to 10 wins. Settlement = 1, city = 2, Largest Army = 2, Longest Road = 2, VP card = 1 (hidden until the end). |
| Pips | Dots under a number token: how many of the 36 dice outcomes roll that number. 6 and 8 have 5 pips, 2 and 12 have 1. **Pips = expected production.** |
| Robber / rolling a 7 | Anyone holding more than 7 cards discards half. The roller moves the robber onto a tile, which then produces nothing, and steals one card. |
| Dev (development) card | Bought for sheep + wheat + ore. The 25-card deck has 14 knights, 5 VP cards, 2 road building, 2 year of plenty, 2 monopoly. |
| Knight | Move the robber and steal a card. The player who has played the most knights (at least 3) holds **Largest Army**, worth 2 VP. |
| Monopoly | Name a resource and take all of it from the opponent. |
| Ports and bank trades | Normally trade 4 of a card for 1 from the bank. A 3:1 port trades 3 of anything; a 2:1 port trades 2 of one specific resource. |

---

## Title

> *Beating a greedy Catan bot with a better evaluation, not deeper search*

- **Greedy** means F looks only one move ahead.
- **Evaluation** is our scoring formula for positions.
- **Search** means looking many moves ahead.

The title is the whole thesis: under a tight time limit, judging positions well beats looking far
ahead.

---

## Section 1: Problem, budget and what it rules out

**"2-player Catan, no player trades, against F, O and other teams."** This is the setup. F is a
simple bot built into the game library. O is the organisers' stronger trained bot.

**"The only hidden information is the opponent's unplayed development cards."**
- There are 19 cards of each resource. We can see the bank and our own hand, so the opponent's hand
  is simply 19 − bank − ours.
- *Why it matters:* the game is almost fully visible. To simulate it, we only have to guess the
  opponent's dev cards. The engine's `sample_world` function does that guess for us.

**"300 ms plus 12.5 ms per decision, about 1 s per game."** This is the CPU budget.

**"We measured the primitives…"**
- Copying the game and making one move costs 0.10 ms.
- Scoring a position costs 0.09 ms.
- Playing one random game to the end costs 11 ms.

**"60–100 simulated actions per decision."** This is simple arithmetic: 12.5 ms ÷ about 0.1–0.2 ms
per try.

*Insight:* this one calculation decided the whole design. Measure costs **before** choosing an
algorithm.

**"MCTS and deep alpha-beta do not fit."**
- **MCTS** (Monte Carlo tree search) needs hundreds to thousands of random playouts. One playout
  (11 ms) already eats almost the whole budget for a move.
- **Alpha-beta** (minimax search) two moves deep must also cover every dice roll in between. That
  is thousands of positions.

**"AlphaBeta depth 2 beat F only 57.5 % even with no clock; the same-turn variant won 8 % under the
clock."**
- Even with unlimited time, searching deeper with F's own scoring formula barely helps.
- With the real clock, search runs out of time and collapses.

**"The lever is the quality of a one-ply evaluation."** "One-ply" means looking one move ahead.
Since we can't search deep, the only way to get better is to **judge positions better**.

---

## Section 2: Understanding the opponent first

**"F scores public VPs at 3·10¹⁴, production at 10⁸, everything else at most 10⁴."**
- The weights are so far apart that they work like a strict priority order. Victory points beat
  everything. Production only breaks ties between equal VPs. Everything else only breaks ties of
  ties.
- So F grabs any visible point immediately and never gives up something now for something later.

**F-vs-F statistics.** Winners held Largest Army only 3 % of the time, VP cards 0.17 per game,
2.3 dev cards were bought per game, and 17 cards per game were lost to sevens.

*Why:* F counts only **public** VPs.
- A hidden VP card is worth almost nothing to it.
- A knight in hand is worth almost nothing until it is played.
- So F rarely buys dev cards and never fights for Largest Army.
- Its penalty for a big hand is tiny, so it hoards cards and loses them to sevens.

**"Two VP sources are left uncontested… v5 holds Largest Army in about 89 % of its wins."**
- Largest Army (2 VP) and VP cards are almost free points against F, and our bot takes them.

*Insight:* study the opponent's objective and find what it cannot see.

---

## Section 3.1: The value function (the scoring formula)

**The formula, in words:**

> **V** = (my score) − 0.74 × (opponent's score)
>   + a bonus for being ahead in knights played
>   + a bonus for being ahead in road length

- **My score minus their score:** a position is good when I am strong and they are weak.
- **The "clip ±2" on the race bonuses:** the bonus stops growing once you are 2 ahead. At that point
  you have basically secured the title.
- **k = 0.74 < 1, "race, don't block":** making the opponent 1 VP weaker is worth only 0.74 of making
  myself 1 VP stronger.
  - SPSA tuning found this; it started at 0.9.
  - *Intuition:* in 2-player Catan you win by reaching 10 first. Spending your resources to hurt the
    opponent usually slows you down more than it slows them.

**Each player's score is a sum of terms:**

| Term | Plain meaning | Why it exists |
|---|---|---|
| VPs | Me: true VPs, including hidden VP cards. Opponent: public VPs + 0.2 per unknown dev card. | 5 of the 25 dev cards are VP cards, so an unknown card is a VP with probability about 0.2. |
| Production | Expected cards per roll (pips), weighted per resource. A robber-blocked tile counts zero. Worth less as the game goes on. | Wheat and ore are weighted highest: cities need 2 wheat + 3 ore, and dev cards need wheat + ore. Late in the game, fewer turns are left to collect. |
| Diversity | How many of the 5 resource types I produce. | With no player trades, a missing resource costs 4:1 at the bank. |
| Ports | A 3:1 port gets a fixed bonus. A 2:1 port is worth my production of its resource. | A 2:1 wheat port is useless if you make no wheat. |
| Expansion | Pips of the best empty spots my roads can reach now, with 1 road, or with 2. | These are future settlements. |
| Hand | Cards have small value. Holding more than 7 cards is penalised. There is a bonus for holding exactly what a build needs. | A 7 costs half your hand. Being "ready to build" is real progress. |
| Dev cards | Knights and other dev cards in hand; knights already played. | Future robber moves and Largest Army. |

**"Every weight is in VP units."** Every number means "this many victory points' worth". For
example, a hand that can build a city right now is worth 0.47 VP.

*Why that matters:* you can sanity-check it. Something that is merely a step toward 1 VP should
never be worth more than 1 VP. That check is exactly how we spotted the bug in the learned formula
(Section 6, insight 1).

**The regime φ (phi).** This is a number from 0 to 1 that tracks how far into the game a player is.

> φ = the larger of:
> - (my VP − 4) / 4, kept between 0 and 1 (so it goes from 0 at 4 VP to 1 at 8 VP);
> - 1 − (pips of my best reachable empty spot) / 10 (it nears 1 when no good spots are left).

- When φ is near 0, early game: wood and brick matter, because roads and settlements spread you out.
- When φ is near 1, late game: wheat and ore matter, because cities and dev cards turn production
  into points. Expansion terms fade and dev cards gain value.
- *Why:* this is how good human players play. You expand until you run out of space or get close to
  winning, then you upgrade.

---

## Section 3.2: How the bot picks a move

**"We sample one world, simulate every legal action, pick the best V."**
1. Fill in the opponent's hidden dev cards with a random guess consistent with what we know.
2. Try each legal move on a copy of the game.
3. Score each copy and play the best move.

Four refinements:

**1. Chance nodes in expectation.**
- When you buy a dev card in a simulation, the engine draws one random card. If that draw happens to
  be a VP card, buying looks great (+1 VP). If it is a knight, buying looks mediocre. The decision
  becomes a coin flip.
- So instead we use the **average value of the remaining deck**, about 0.30 VP.
- A robber steal is scored the same way: "+1 card for me, −1 for them", not the one random card the
  simulation happened to steal.

*Insight:* when choices involve luck, compare averages, not one lucky sample. Otherwise noise makes
the decision.

**2. Two-step follow-ups.**
- Some moves look bad alone. Trading 4 cards for 1 makes your hand smaller, so the score drops. But
  the trade lets you build a settlement right after.
- So a trade is scored as **"the best thing I can build right after it"**.
- A knight is scored including the robber move it triggers.
- Road Building is scored including its 2 free roads.

**3. Turn plan.**
- Take the top 3 moves. For each one, keep playing the greedy best move until the end of the turn.
  Compare the positions at the end of the turn.
- Switch away from the normal choice only if a plan is better by more than **0.05 VP**.
- *Why the margin:* the plan's estimate is noisier. Without a margin, the bot would switch on tiny
  differences that are just noise.

**4. Clock tiers.**
- As CPU runs low, the bot drops its expensive parts in order: first the turn plan, then the
  follow-ups.
- Below 0.1 s left it stops simulating and uses a fixed priority list: city > settlement > knight >
  dev card > roll > end turn.
- *Why:* a simple safe move beats running out of time.

---

## Section 3.3: The learned opening

**Why focus on the opening.**
- In 2-player Catan, the 4 initial settlements set most of your production for the whole game.
- The first move also gets 300 ms of extra time. The old opening formula used only a few
  milliseconds of it.

**The model:**

> P(win) = sigmoid( Σ weight × (my feature − opponent's feature) ± a small bonus for moving first )

This is logistic regression. The **sigmoid** squashes any number into a probability between 0
and 1. The features are production per resource, total pips, the number of distinct resources,
ports, and balance measures such as min(wheat pips, ore pips).

**The data.**
- 16,000 games of the bot against itself.
- In half the placements, the settlement was chosen **at random among the 10 richest free spots**.
- *Why:* if the model only ever saw the bot's own choices, it could not learn what the alternatives
  are worth. You need variety in the data to compare options. This is the classic exploration idea.

**How good it is.**
- **AUC 0.74:** take one opening that won and one that lost. The model ranks the winner higher
  74 % of the time (50 % would be a coin flip).
- **Log-loss 0.600 vs 0.693:** 0.693 is the score of a model that only knows who moves first. Lower
  is better.
- **Gradient boosting did no better:** a fancier model gained nothing, so the relationship is close
  to linear. We kept the simple model.

**The largest weights:**

| Feature | Weight |
|---|---|
| distinct resources | +0.28 |
| a 3:1 port | +0.24 |
| min(wheat, ore) | +0.17 |
| total pips | +0.16 |

In plain words: **balance beats raw production**, because with no one to trade with, every missing
resource hurts.

**The draft search.**
- The placement order is P1, P2, P2, P1 (a "snake").
- At each of our picks, we try our best candidate spots.
- For each candidate, we **predict the opponent's next pick**, using our previous greedy formula as a
  model of a sensible opponent, and finish the draft.
- We score the final 4 settlements with the model and pick the best candidate.
- A CPU deadline stops the search before it can overrun.

---

## Section 4: Design decisions and why

**Hand-built features tuned by self-play, not learned end-to-end.**
- Published attempts to learn Catan from scratch with reinforcement learning lost even to random
  players.
- One day is too short for that.
- A simple weighted-sum formula is also very fast (0.1 ms per call).

**SPSA (Simultaneous Perturbation Stochastic Approximation).** We have about 25 weights and want
them to win more games. Win rate has no gradient you can compute. SPSA works around that:
1. Pick a random direction: **+ or − for every weight at once**.
2. Build two bots, one with all weights nudged "+" and one nudged "−". Each nudge is about ±28 %,
   because weights are stored as logarithms, so nudges are percentages.
3. Let the two bots play 64 games against each other on identical boards.
4. If "+" won more, move the weights toward "+"; otherwise toward "−". Steps shrink over time.
5. Repeat. 93 rounds took about 12 minutes on 4 cores.

*Why SPSA:* each round costs the same two bots, no matter how many weights there are.

**"F was never an opponent, teacher or selection signal."**
- We never tuned or chose versions using games against F; F was only for the final measurement.
- *Why:* tuning on the test opponent inflates your score against it. That is overfitting, like
  training on your test set. It could also make the bot worse against O and other teams.
- It worked: our local F numbers matched the leaderboard.

**Paired head-to-heads.**
- When comparing two versions, both play the **same boards and the same dice**, and they swap seats.
- This removes board luck from the comparison, so far fewer games are needed.
- Before believing a change, we required at least 300 games and about 2 standard errors.

**Expectation at chance nodes, with evidence.** The turn plan scored on the one random dev-card draw
**lost** against its parent (0.46). Scored with the deck average, it **won** (0.51–0.53).

---

## Section 5: Experiments

**"±1.96·√(p(1−p)/n)"** is the 95 % confidence interval. With p = 0.79 and n = 1000 games, it is
±0.025. The true win rate is very likely within ±2.5 points of the measured one.

**Table 1, row by row.** "h2h vs parent" is the head-to-head win rate against the previous
version. Above 0.5 means the new version is better.

| Row | What changed | What happened |
|---|---|---|
| v1 0.635 | The scoring formula plus trade-then-build. | Already beats F clearly. |
| v2 0.683 | Knight and Road Building follow-ups. | **+5 points.** Before this, the bot ended games still holding unplayed knights, because playing one looked like "losing a card". |
| v3 0.726 | Opening considers the opponent's next picks. | +4 points. |
| v5 0.791 | SPSA-tuned weights. | **+6.5 points, the biggest single jump.** This was submission 1. |
| combo 0.787 | Regime + turn plan. | No change vs F, but beats v5 52.4 % over 3000 games (about 2.6 standard errors). |
| op1 0.786 | v5 + learned opening. | Beats v5 54.3 %. On the same 1600 games v5 scored 0.761, so +2.5. |
| **comboop1 0.820** | combo + learned opening. | On the same 1000 games combo scored 0.787, so **+3.3**. |
| cop1fix 0.770 | Two fixes (below). | Only 400 games, so a wide interval (±0.041). It may be weaker (see "Red-teaming the clock"). |

**Other results.**
- **Leaderboard.** v5 scored 0.779 vs F and 0.626 vs O. comboop1 scored 0.813 vs F and 0.658 vs O.
  - The strength score is 0.5·F + 0.5·O: v5 = 0.70, comboop1 = 0.736.
  - Our local F estimates (0.791 and 0.820) were within the intervals of the leaderboard numbers.
    That means **our testing setup was trustworthy.**
- **Robustness.** v5 beats catanatron's AlphaBeta-2 88 % of the time and a random-ish bot 100 %.
- **Second benchmark.** We built "F + regime" from the organisers' hint. It beats F 57 %, and v5 beats
  it 75 %. The ordering is consistent: F is weakest, then F + regime, then O.

**Table 2: what failed, and why.**
- **Learned linear evaluation (0.10–0.25):** see insight 1.
- **Opponent-roll expectimax (0.42–0.46):** the bot imagined every possible opponent dice roll
  before ending its turn. This made it worse. Our formula was tuned on positions at the end of our
  own turn. Scoring positions in the middle of the opponent's turn adds a bias.
- **"Progress toward a build" features (0.417):** rewarding "almost having a city" more strongly made
  the bot **hold** cards instead of building. It lost tempo and lost cards to sevens.
- **Danger mode, robber lookahead (about 0.50):** no effect.
- **Second SPSA round, SPSA with regime (0.503):** tuning had already plateaued.
- **Community 1v1 heuristics (0.47–0.51):** human rules of thumb added nothing on top of the tuned
  formula.
- **Adaptive bandit (0.530 vs v5, 0.805 vs F):** a bot that learns which of 4 styles works against each
  opponent. Promising, but not clearly better than comboop1 at 400 games.

**Auditing decisions instead of only games.**
- Win rates average everything together, so a bad habit in one rare situation is invisible. So we
  checked individual decisions, about 950 of them, taken from real games:
  1. For each alternative move, play 24 random continuations to the end.
  2. Use **the same dice sequences** for every alternative ("common dice"). Differences then come from
     the move, not from luck.
  3. Estimate each move's win chance. **Regret** = how much better the best alternative was than the
     move the bot actually chose.
- **"Split-half unbiased":** if you pick the best of several noisy estimates, it looks better than it
  really is, purely from noise. So half the rollouts are used to choose the best alternative, and
  the other half to measure it.
- **Findings:**
  - Almost every decision type showed about zero regret.
  - **Playing Monopoly before rolling cost 7.3 points.** Rolling first is free information: you might
    get the cards anyway. Playing Monopoly first also swells your hand just before a possible 7,
    which makes you discard half.
  - The fix (never play Monopoly before rolling) did no harm: 0.503 vs comboop1. The situation is
    rare.

**Red-teaming the clock.**
- A separate session tried to break the bot. It found 0 crashes in 700 games and no exploit by 3
  adversarial bots.
- But 2 of 500 very long games ran out of CPU. The turn plan had no internal deadline and could take
  420 ms on one move.
- **Fix:** run the turn plan only when at least 0.9 s is left. Mean CPU per game dropped from 427 ms
  to 300 ms.
- **Cost:** the turn plan now runs less often. vs F it scored 0.770 (400 games), against
  comboop1's 0.820. That is close to 2 standard errors, so it may really be weaker.
- We did not submit this version. comboop1 had 0 games over the clock on the leaderboard, and the
  fixed version looked weaker, so we submitted comboop1.

---

## Section 6: Insights (the "lessons beyond this game")

**1. Predicting well ≠ deciding well.**
- We fitted a formula to predict the winner from game positions. It was **78 % accurate**, yet as a
  bot it won only **10 %** against our hand-tuned one.
- *Why:* positions where a player holds the cards for a city mostly come from winning games, because
  winners have lots of resources. So the model gave "holding city cards" a huge weight, +1.48 VP.
- The bot then compares two choices:
  - *Keep holding:* it keeps the +1.48 bonus.
  - *Build the city:* it gains +1 VP plus production, but loses the bonus.
- Holding looks better, so it **never builds**.
- **Correlation is not the value of an action.** The fix is to learn from decisions: compare the
  chosen move against its alternatives, or use TD learning, which learns from how the score changes
  move to move. More outcome data does not help.
- This holds for any learned scorer used to make greedy choices.

**2. Why the same kind of model worked for the opening.**
- When choosing settlements, all 4 placements are compared at one moment, and nothing is "in
  progress". Picking the spot and predicting the outcome from that spot are the same question.
- There are no "about to build" states to fool the model. In the mid-game there are.

**3. Evaluation beats depth when compute is limited.** Better judgment took us from 50 % to 79 % at
F's own CPU cost. Deeper search added little.

**4. Exploit what the opponent's objective cannot see.** F ignores hidden points and unplayed
knights. Those points are nearly free.

**5. After tuning, small changes get absorbed.**
- Once SPSA has tuned the weights, the formula already approximates most small additions.
- Two changes that each looked +1.7 standard errors better did **not** add up together (0.508).
- What still helped was **new information**, such as the learned opening.

**6. Measurement discipline.**
- SPSA's own log sits near 50 % by design, because it compares two nearly identical bots. Progress
  must be measured against a **frozen** older version.
- At 400 games the error bar is ±4.4 points, and several "wins" seen at 40–60 games vanished at
  300.
- Audits mislead the same way: a robber signal of +2.9 at 35 decisions disappeared at 247.

---

## Section 7: Limitations and next steps

- **One sampled world.** The bot guesses the opponent's hidden cards once per move, so it can be
  surprised by hidden VP cards late in the game. About 80 % of the clock goes unused; averaging
  several guesses would use it.
- **Opening limits.**
  - The opponent model in the opening is our own formula, not the real opponent.
  - The training data is self-play only.
  - Roads are ignored when scoring an opening.
- **Next steps.**
  - TD(λ) learning on after-states, the proper fix for insight 1.
  - Averaging over several sampled worlds.
  - Re-tuning with the turn plan switched on.

## References (what each one is for)

- **catanatron:** the game engine and F.
- **Spall 1992:** SPSA.
- **Buro 2002:** a linear evaluation tuned from data reached world-class play in Othello. This is
  the inspiration for our approach.
- **Tesauro 1995:** TD-Gammon, the classic example of learning the value of positions *after* moves.
  This is the fix we point to in insight 1.
- **Szita et al. 2010:** MCTS in Catan is weak without domain knowledge.

---

## Questions you will probably get (with short answers)

- **"Why not MCTS or RL?"** One random playout costs 11 ms, nearly the whole per-move budget. RL
  from scratch on Catan has lost to random players in published attempts, and we had one day.
- **"How do you know you didn't overfit to F?"** F was never used in tuning or selection. Our local
  F numbers matched the leaderboard, and we also improved against O, which we never trained against.
- **"Is +3 points real or noise?"** Comboop1 vs combo was measured on the same 1000 boards and dice
  (+3.3). Head-to-head it won 0.523 over 1000 games, about 1.5 standard errors: suggestive, not
  certain. The leaderboard agrees: higher vs both F and O.
- **"Why did the learned evaluation fail?"** It learned which positions *look* like winning
  positions, not which *moves* lead to winning. Holding city cards correlates with winning, so it
  hoarded.
- **"Why not submit the clock fix?"** It scored 0.770 vs F against comboop1's 0.820, close to 2
  standard errors, so it is probably weaker. comboop1 had 0 games over the clock in 1000
  leaderboard games, so the clock risk looked small.
