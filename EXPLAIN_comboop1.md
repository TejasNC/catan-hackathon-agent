# How `army/comboop1` plays Catan

`comboop1` is two bots merged. The mid-game comes from **combo**: the v5 value function, regime-B
weights and a within-turn turn-plan lookahead (`cop1_base.py`, `cop1_core.py`). The opening comes
from **op1**: a learned opening model plus a draft search (`cop1_opener.py`, `open_model.json`,
`cop1_mbase.py` = plain v5, used to predict the opponent). `agent.py` is the glue between them.

## 1. Overview

On each decision the bot gets an observation with hidden information: the opponent's hand and
the dev-card pile. It draws **one sampled world** (`obs.sample_world`), a full game state consistent
with what it can see. On a copy of that world it **simulates every legal action** and scores the
resulting state with a hand-built value function $V$, measured in victory points. Random outcomes
are averaged rather than taken from the sample. Actions that pay off later get a short follow-up:
trade → build, knight → robber, road building → 2 roads. In the main phase of a turn the top
candidates are then played out greedily to the end of the turn, and a different first move replaces
the 1-ply choice only if it beats it by a margin. The bot plays the action with the best score.

**Budget.** The clock allows ≈ 300 ms base + 12.5 ms per decision, roughly 1 s of CPU per game.
Copying a state and executing one action costs ≈ 0.1 ms and one $V$ call ≈ 0.1 ms, so a decision
can afford about 60–100 simulated actions. A random playout costs 11 ms, which rules out MCTS. The
design that fits this budget is a **good evaluation with depth 1–2 search**, not deep search.

## 2. The value function

$$V(s) \;=\; \mathrm{Score}_{\text{me}}(s) \;-\; k\cdot \mathrm{Score}_{\text{opp}}(s)
\;+\; w_{\text{army}}\,\mathrm{clip}(K_{me}-K_{opp},\pm2) \;+\; \tfrac{w_{\text{road}}}{2}\,\mathrm{clip}(L_{me}-L_{opp},\pm2)$$

with $k = 0.737$ and $w_{\text{army}} = 0.20$, $w_{\text{road}} = 0.26$. $K$ = knights played,
$L$ = longest-road length.

Every term is in **VP units**. That makes each weight readable as a claim: "a ready-to-build city
hand is worth 0.47 VP" or "one pip of wheat is worth 0.09 VP". Two consequences:

- You can sanity-check a weight against the game. A settlement is +1 VP plus its production, so
  any hand term above 1 VP would be absurd. This check is exactly what exposed the learned-eval
  failure in §8.
- $k < 1$ means "race, don't block": hurting the opponent by 1 VP is worth 0.74 of gaining 1 VP.

Two shared quantities set how fast production fades. The **phase** is
$\text{phase} = \mathrm{clip}\big((\text{lead VP} - 2)/7,\,0,1\big)$, and the production weight
moves with it: $w_p = 0.055(1-\text{phase}) + 0.0495\,\text{phase}$.

| Group | Term (per player) | Weight | Why it exists |
|---|---|---|---|
| **VPs** | me: actual VP (incl. hidden VP cards); opp: public VP | 1 | the objective |
| **Production** | $w_p \sum_r \rho_r\,\text{pips}_r$, robber tile excluded, city = 2× | $\rho$ = (1.06, 1.30, 1.15, **1.60**, **1.58**) for wood, brick, sheep, wheat, ore | future cards; wheat/ore build cities and dev cards |
| **Diversity** | $w_{div}(1-\text{phase})\cdot\#\{r:\text{pips}_r>0\}$ | 0.274 | a 2-player game has nobody to trade with, so a missing resource costs 4:1 |
| **Expansion** (only if settlements remain) | $\text{fade}\,(1-\tfrac{\text{phase}}{2})\,(0.019\,e_1 + 0.010\,e_2 + 0.050\min(n_b,2))$ | see left | $e_1$ = best 2 spots buildable now or 1 road away (×0.8); $e_2$ = best 2 spots 2 roads away; $n_b$ = spots buildable now |
| **Hand** | $0.061\min(n,8)$; $-0.177\lfloor n/2\rfloor$ if $n>7$ | | cards have value, and a 7 costs half the hand |
| | ready-settle / ready-city / ready-dev bonuses | 0.30 / 0.47 / 0.12 | a hand that can build *now* is worth more than its card count |
| | partial: $0.059\,(2 - d_{city} - d_{settle})/2$ | | smooth credit for getting closer to a build |
| **Dev cards / army** | me: $m_d(0.095\,\text{knights} + 0.18\,\text{other})$ | | a knight is cheap to hold: SPSA cut it from 0.25 to 0.09 so the bot plays them |
| | opp: per unknown card $m_d(0.56\cdot0.095 + 0.24\cdot0.18) + 0.2$ | | expectation over the pile: 0.2 ≈ P(VP card) |
| | $m_d\cdot0.157\min(K,4)$ + army-lead term above | | Largest Army is 2 VP that F never contests |
| **Ports** | 3:1: $0.193(1-\tfrac{\text{phase}}{2})$; 2:1: $0.010\cdot\text{pips}_r$ | | a 2:1 port is only worth what you produce of its resource |
| **Roads** | $0.040\min(L,10)$ + road-lead term above | | the race for Longest Road (2 VP) |

$m_d$ and fade come from the regime (§3). The opponent's hand is visible to the engine as a count,
and its unknown dev cards are scored in expectation.

## 3. The regime φ: expand early, build late

Each player has a regime $\varphi\in[0,1]$, computed **once per decision at the root** and then held
fixed:

$$\varphi = \max\Big(\underbrace{\mathrm{clip}\big(\tfrac{VP-4}{4}\big)}_{\text{score}},\;
\underbrace{1-\min\big(1,\tfrac{\text{best open spot pips}}{10}\big)}_{\text{space}}\Big)$$

The space term is 1 when no settlements remain. "Best open spot" means reachable with at most one road.

It changes three things (regime B: $a=0.5$, fade 0.35, dev 0.25):

1. **Resource weights.** With $q = \tfrac12 + \tfrac12\varphi$:
   $$\rho_r \leftarrow \rho_r\big(1 + a\,[(1-q)E_r + qB_r - 1]\big),\quad
   E=(1.25,1.25,1,0.9,0.6),\; B=(0.6,0.6,0.9,1.35,1.55)$$
   At $\varphi=1$, wood and brick drop to ×0.80 and wheat and ore rise to ×1.18 and ×1.28.
2. **Fade expansion:** $\text{fade} = 1 - 0.35\varphi$.
3. **Raise dev cards:** $m_d = 1 + 0.25\varphi$ (knights, other dev cards, played knights).

## 4. Decision procedure

The pipeline below is `cop1_base.Agent.decide`, plus `cop1_core` on top:

1. **1-ply scoring.** Every legal action $a$ is executed on a copy of the sampled world, and its
   score is $V(s_a)$.
2. **Chance nodes in expectation.**
   - *Buying a dev card:* the sampled draw is replaced by the mean over the unseen pile,
     $\mathbb{E}[\text{dev}] = \frac{n_K\,0.095\,m_d + n_{VP}\cdot1 + n_{other}\,0.18\,m_d}{n}$.
     That is ≈ 0.30 VP for a fresh pile.
   - *Robber steal:* $V + 0.061\,(1+k)$, i.e. one card for me and one fewer for them.

   Without this, every dev-card decision would be a coin flip on one sample.
3. **2-step follow-ups.**
   - *Trade, Year of Plenty, Monopoly:* the score becomes the best of
     {city, settlement, dev, road} reachable right afterwards. This covers the top 6 such actions,
     each with up to 12 follow-ups.
   - *Knight:* the score includes the greedy robber placement it triggers.
   - *Road Building:* the score includes the two greedy free roads.
4. **Turn-plan lookahead** (`cop1_core`, PLAY_TURN only).
   - Take the top **3** first actions by 1-ply score, plus the base choice from steps 1–3.
   - Extend each one greedily, up to 6 steps, until ending the turn scores best.
   - Score the end-of-turn state, keeping the chance corrections from step 2.
   - Switch away from the base choice only if a plan beats it by **0.05 VP**. The margin keeps
     search noise from overriding the evaluation.
5. **CPU-safety tiers**, keyed on `cpu_left`:

| cpu_left | Behaviour |
|---|---|
| ≥ 0.45 s | full: steps 1–4 |
| 0.25–0.45 s | no turn-plan |
| 0.10–0.25 s | **cheap mode**: 1-ply only, no follow-ups |
| < 0.10 s | **panic mode**: no simulation; priorities city > settlement > knight > dev > roll > end |

## 5. The opening (op1)

**What is learned:** a logistic model of P(win | 4 initial settlements),
$$P(\text{win}) = \sigma\Big(\textstyle\sum_i w_i\,(x_i^{me}-x_i^{opp}) \pm w_{seat}\Big)$$
It has 17 numbers in `open_model.json`. The largest weights, per raw unit:

| Feature | $w$ |
|---|---|
| distinct resources | +0.28 |
| 3:1 port | +0.24 |
| min(wheat, ore) pips | +0.17 |
| total pips | +0.16 |
| min(wood, brick) pips | +0.12 |
| 2:1 port resource pips | +0.08 |
| single resources | ≤ 0.02 |

Balance beats raw pips.

**Data.** 16,000 v5-vs-v5 games. Each initial settlement was v5's own pick, or with probability 0.5
a random node among the 10 free nodes with the most pips. The random picks let the model see
openings v5 would never choose. Fit quality: held-out log-loss 0.600 against 0.693 for seat alone,
AUC 0.74. Gradient boosting did no better.

**Draft search.** The snake order is P1, P2, P2, P1. Candidates are ordered by v5's pair value.

| Our pick | Search |
|---|---|
| P1 first | top 8: predict the opponent's 2 picks, take our best last pick by the model |
| P1 last | the model's best completion |
| P2 first | all pairs from the top 9, predict the opponent's last pick |
| P2 second | top 15, predict the opponent's last pick |

**Opponent prediction.** It uses v5's deterministic draft formula (`Opener.m_pick`, inner loop
top 5). That is exact against v5 and a reasonable proxy for any greedy drafter.

**Clock.** Each search loop has a deadline of $\min(150\text{ ms}, (\text{cpu\_left}-80\text{ ms})/2)$.
The search is skipped below 120 ms, and any failure falls back to combo's own draft.

## 6. How the weights were obtained, and the results

1. **Hand-set** v1–v3 weights (INSIGHTS §8).
2. **SPSA self-play.** Weights are stored as $\theta_k=\theta_k^0e^{x_k}$. Each iteration draws
   $\Delta\in\{\pm1\}^d$ and plays $\theta^\pm = x\pm0.25\Delta$ against each other on 64 paired games.
   With $s$ = θ⁺'s win rate, the update is
   $x \leftarrow x + a_t(2s-1)\Delta/2$, where $a_t = 0.6/(1+t/100)^{0.602}$.
   93 iterations gave v5. **F was never an opponent or teacher**; it is only a held-out measuring stick.
3. **Regime B** ($a$ = 0.5, fade 0.35, dev 0.25) was set by hand. An SPSA run with the regime
   switched on landed elsewhere (0.77 / 0.26 / 0.24), and that version was no better (0.503 vs v5).

Results are win rates; for the 95 % interval use $\pm1.96\sqrt{p(1-p)/n}$ (≈ ±0.025 at n = 1000).

| Bot | vs F | head-to-head |
|---|---|---|
| v5 (submission #1) | 0.791 (1000 g); leaderboard 0.779, **vs O 0.626** | 0.550 vs v3 |
| combo | 0.793 | 0.524 vs v5 (3000 g) |
| op1 | 0.786 (1600 g; v5 0.761 on the same games) | 0.543 vs v5 (600 g) |
| **comboop1** | **0.820** (1000 g; combo 0.787 on the same games); official harness 0.805 (200 g), 0 over clock | 0.523 vs combo (1000 g) |

## 7. Worked example (hypothetical, real weights)

**Situation.** Mid-game, I have 5 VP and the opponent has 5 public VP, so phase $=3/7$ and
$w_p = 0.0526$. My best open spot has 9 pips, so $\varphi=\max(0.25, 0.10)=0.25$. The regime
weights are then $\rho \approx (0.98, 1.20, 1.11, 1.75, 1.73)$.

**Hand.** wood 1, brick 0, sheep 1, wheat 3, ore 3: 8 cards, so a 7 would cost 4 of them. I own a
3:1 port. Only the changing terms are shown; the opponent's score is unchanged.

| Option | ΔVP | Δprod | Δother | Δhand | **ΔV** |
|---|---|---|---|---|---|
| **Build city** on (wheat 5, ore 4, sheep 3 pips) | +1 | +1.00 | | −0.21 | **+1.80** |
| Trade 3 ore→brick, then settle (wood 4, brick 3, wheat 2) | +1 | +0.58 | +0.16 div, −0.15 exp | −0.28 | **+1.31** |
| Trade 3 ore→brick only (1-ply) | | | | +0.29 | +0.29 |
| Buy dev card | | | +0.30 (E[dev]) | −0.07 | +0.23 |

How to read it:

- **Hand deltas net out the discard risk.** For the city: −0.30 for card count, **+0.71** for
  escaping the 4-card discard, −0.47 for losing ready-city, −0.12 for losing ready-dev, −0.02 partial.
- **The 2-step follow-up matters.** Scored alone, the trade is worth +0.29. With the follow-up it
  carries the settlement's value, +1.31, and becomes a real contender. That is how a 1-ply bot
  "plans" trade → build.
- **The city wins** mostly through wheat and ore production, which the regime boosts as φ grows.
  The dev card is far behind: 0.30 VP of expected value can't compete with 1 VP plus production.
- **The turn-plan finds nothing to add.** After the city the hand is wood 1, sheep 1, wheat 1, and
  no follow-up build is affordable. So the plan equals the 1-ply choice, and the bot builds the city.

## 8. Known limits and what did not work

- **Learned linear eval is a trap.** Logistic regression on outcomes predicts the winner well
  (78 % accuracy) but wins only **10–19 %** as a policy. It gives "holding city cards" more value
  than building the city, so the bot hoards. Features that *predict* winning are not features
  worth *choosing*. Fitting on after-states did not fix it.
- **Search on top of a tuned eval adds little.** Other attempts ended between 0.42 and 0.50:
  - opponent-roll expectimax at END_TURN: 0.42–0.46
  - robber lookahead: 0.498
  - danger mode: 0.497
  - a second SPSA round: 0.503
  - 1v1 community heuristics: 0.47–0.51

  Once SPSA has tuned the weights, small structural changes get absorbed.
- **Opening limits:**
  - Roads are ignored when an opening is scored.
  - The opponent model is v5's draft, not F's "pips + 4 per resource".
  - Training data is v5 vs v5 only.
- **Single sampled world.** Hidden VP-card risk late in the game is not averaged.
- **The next real gain needs a different model class,** e.g. TD(λ) on after-states.
