# Beating a greedy Catan bot with a better evaluation, not deeper search

*Team bakarwadi — draft outline for the 4-page report. Numbers are from runs in this repo; see INSIGHTS.md.*

## 1. Problem and constraints (½ page)
- 2-player Catan, no player trades, ~12.5 ms CPU per decision (≈1 s per game), Python only.
- Only hidden information: the opponent's unplayed dev cards (resources are derivable).
- Cost model: copy+execute 0.10 ms, F's evaluation 0.09 ms, one random playout 11 ms
  → about 60–100 simulated actions per decision. Rules out MCTS with rollouts and deep alpha-beta.

## 2. Understanding F before optimising (½ page)
- F = greedy 1-ply, lexicographic weights (VP 3e14 ≫ production 1e8 ≫ rest).
- Scores **public** VPs only → ignores VP cards and played knights. F vs F: Largest Army in 3 % of
  wins, 2.3 dev cards bought per game, 17 cards discarded to sevens per game.
- Literature check: AlphaBeta on F's evaluation 57.5 % (our 40-game rerun; README's 80 % is from 25
  games), MCTS weak without domain knowledge, RL-from-scratch Catan agents lose to random.
- Hypothesis: the evaluation, not the search depth, is the bottleneck.

## 3. Method (1 page)
- Value V = Score(me) − k·Score(opp), every term in VP units (interpretable weights): VPs, robber-aware
  production by resource and game phase, diversity, ports, expansion reach, hand readiness, discard
  risk, dev cards, army and road leads.
- Decision: simulate every legal action on one sampled world; chance outcomes in expectation
  (dev draw, robber steal); two-step lookahead for trades / Year of Plenty / Monopoly (trade then
  build) and for Knight / Road Building (their payoff is the follow-up move).
- Opening: snake-draft lookahead (my best pair minus opponent's best pair).
- Tuning: SPSA on win rate, θ⁺ vs θ⁻ self-play on paired boards. **F never used in training.**
- Clock safety: tiers by `cpu_left`; no-simulation fallback below 0.1 s.

## 4. Experiments (1 page) — table from INSIGHTS.md §5
- 63.5 → 68.3 (follow-up step) → 72.6 (draft opening) → 79.1 % (SPSA) vs F, 1000 held-out games;
  78.7 % on a third seed set. Self-play head-to-heads used for selection, F only for checking.
- Robustness: beats earlier versions, AlphaBeta-2 (88 %), WeightedRandom (100 %).
- Leaderboard: F ___ / O ___ (fill from portal).

## 5. Insights (1 page)
1. Evaluation beats depth under a tight clock.
2. Exploit what the opponent's objective ignores (Largest Army in ~89 % of our wins).
3. **Learned evaluation failure:** logistic regression on outcomes, 78 % holdout accuracy, yet 10 %
   win rate as a policy — "about to build" states predict winning more than building does, so the
   greedy policy hoards. Prediction ≠ decision value; fix would be after-state TD learning.
4. Regression was still a useful diagnostic; SPSA independently moved the same weights (diversity ↑).
5. SPSA's own log stays at 0.5 by design: measure against a frozen parent.
6. Variance: ±4.4 points at n = 400; small-sample "wins" vanished at n = 300.

## References
catanatron (B. Collazo, GPL-3.0); Spall, SPSA (1992); Buro (2002); Tesauro, TD-Gammon (1995);
Szita, Chaslot, Spronck, MCTS in Settlers of Catan (2010).
