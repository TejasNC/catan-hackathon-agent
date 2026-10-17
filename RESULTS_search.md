# Search extensions on top of v5 (zoo/v5_final.py = bot/agent.py)

Code: `runs/search.py` (all behind class flags, defaults = v5 behaviour); variant wrappers `runs/s_*.py`.
h2h = `tools/h2h.py X zoo/v5_final.py N` (paired boards, seed0 300000, no clock); CI = ±1.96·SE.

| variant | what | h2h vs v5 | n | CPU/game (dev box) | vs F (600, seed0 123000) |
|---|---|---|---|---|---|
| s_k3 | turn-plan: top-3 first actions, greedy to END_TURN, raw end value | 0.460 ± 0.040 | 600 | – | – |
| s_k3r | s_k3 + opponent-roll expectimax at END_TURN | 0.423 ± 0.048 | 400 | – | – |
| s_k3m0.0 | turn-plan, random outcomes kept in expectation (dev draw, steal) | 0.510 ± 0.040 | 600 | – | – |
| s_k3m | same + override base only if > 0.05 VP better | 0.518 ± 0.040 (seed 300000)<br>0.530 ± 0.040 (seed 500000)<br>0.508 ± 0.040 (seed 700000)<br>**pooled 0.519 ± 0.023** | 1800 | 368 ms mean, 1420 worst, 0 over budget (v5 ≈ 164 ms on scoring box) | 0.785 ± 0.033 (v5 0.791) |
| s_k3m0.1 | same, margin 0.10 | 0.512 ± 0.040 | 600 | – | – |
| s_k3rm | corrected turn-plan + opponent-roll expectimax, margin 0.05 | 0.463 ± 0.049 | 400 | – | – |
| s_rob | robber: + ROB_TURNS(2)·card·(opp_k·opp blocked cards − my blocked cards) | 0.498 ± 0.040 | 600 | – | – |

## Findings
* **Naive turn-plan hurts (0.46).** If the rollout end state is scored with the sampled dev-card draw,
  plans that buy a card get the luck of that one sample (a VP draw adds +1). Scoring dev draws and
  steals in expectation, as `eval_action` already does, brings it back to 0.51–0.52 at every margin.
  The best one (s_k3m) pooled over 1800 games is 0.519 ± 0.023, about 1.6 SE above 0.5. It is under the 2-SE bar
  and F shows no change (0.785 vs 0.791), so it is **not adopted**. It is the best search candidate if more games are run later.
* **Opponent-roll expectimax hurts (0.42–0.46)** both with and without the correction. The value function
  is fitted on states where the side to move has just finished a turn. Scoring states in the middle of
  the opponent's turn (after their roll, holding the produced cards) seems to add bias that does not
  cancel between candidates. It would need its own tuning, or a deeper reply that also covers the
  opponent's builds.
* **Robber lookahead is neutral (0.498):** the static value already removes the robbed tile's production,
  so the explicit denied-cards term mostly re-ranks equal targets.
* Conclusion: none of these search extensions is clearly better than v5 (> 2 SE), and bot/agent.py stays unchanged.
  Spare CPU is better spent elsewhere, such as averaging over several sampled worlds, or SPSA on the value
  function with the search turned on.
