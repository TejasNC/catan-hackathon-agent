# agent_v2: one-ply search with a hand-built value function

Not part of the submission zip, which holds `agent.py` only.

## Submit

On the team machine, from the kit root:

```bash
mkdir -p submissions && (cd agent_v2 && zip -j ../submissions/agent_v2.zip agent.py)
python -m catan_kit.evaluate --a agent_v2/agent.py --b examples/f_agent.py --games 1000
~/upload.sh submissions/agent_v2.zip
```

## Choices where the spec left room

| Point | Choice | Why |
|---|---|---|
| Phase φ | once per decision, from the root | all candidates compared under the same weights |
| "0.20 per other dev card" | excludes VP cards | a VP card's 1.0 is already in actual VPs |
| Spot pips | plain pip sum of the node's tiles | spec says "pips" |
| n_spots | legal spots on the road network now | same as "reachable now" in e1 |
| Win | +1000 when my actual VP reaches 10 | breaks ties toward winning now |

## Additions beyond the spec, for the clock only

* **Trade-lookahead budget: 25 ms per decision** (less when the clock is short). Simulating a road
  runs the engine's longest-road DFS, which gets slow on big road networks. Unbounded, one decision
  cost 152 ms and one game in 200 went over the clock. With the budget the worst decision in that
  game is 26 ms. On 1000 games vs F the result was identical (727 wins) with and without it.
  Because the cut depends on measured CPU, a rare slow decision can replay differently.
* **Panic move** when `cpu_left < 10 ms + 0.5 ms × legal actions`: roll, else city, else
  settlement, else end turn. No search.
* Any exception inside the search falls back to the panic move. `CATAN_AGENT_STRICT=1` re-raises.

## Measured (this container, ~1.7x slower per core than the scoring machine)

| Run | Games | Win rate | Mean CPU / game | Over clock | Errors |
|---|---|---|---|---|---|
| vs F, seeds 990000+ | 1000 | 0.727 ± 0.028 | 186 ms | 0 | 0 / 50,893 decisions |
| vs random | 200 | 1.000 | 251 ms | 0 | 0 |
| vs itself | 200 | 0.500 | 168 ms | 0 | 0 |
| vs F, seeds 991000+ | 200 | 0.660 ± 0.066 | 212 ms (worst 1480) | 0 | 0 |
| vs F, seeds 991000+, clock halved | 200 | 0.655 ± 0.066 | 204 ms | 1 | 0 |

## Tests

```bash
PYTHONHASHSEED=0 python -m unittest tests.test_agent_v2 -v   # value fn vs reference, rules, fuzz
PYTHONHASHSEED=0 python tests/profile_agent_v2.py 60          # CPU by decision kind
python tests/stress_clock.py --factor 2 --a agent_v2/agent.py --b examples/f_agent.py --games 200
```
