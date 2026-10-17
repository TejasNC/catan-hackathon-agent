# A 2-player Catan agent: better evaluation, not deeper search

Team **bakarwadi**'s agent for the Catan agent hackathon (17 October 2026): 2-player Catan, no player
trading, one CPU core and about **1 s of thinking per game**, scored against two anchor bots, **F**
(catanatron's `ValueFunctionPlayer`) and **O** (the organisers' trained bot).

| Submission | vs F | vs O | Mean CPU / game |
|---|---|---|---|
| `army/v5`: value function + self-play-tuned weights | 0.779 ± 0.026 | 0.626 ± 0.030 | 164 ms |
| **`army/comboop1`**: v5 + turn planning + regime weights + learned opening (final) | **0.813 ± 0.024** | **0.658 ± 0.029** | 277 ms |

*Leaderboard numbers, measured by the organisers over 1000 games each, with 0 games over the clock
and 0 faults.*

**F was never used as a training or tuning opponent**, only as a held-out measuring stick.

---

## How it works, in one minute

1. **One sampled world per decision.** The only hidden information is the opponent's unplayed dev cards.
2. **Every legal action is simulated and scored** with a hand-built value function in victory-point
   units:

   $$V = \text{Score(me)} - k \cdot \text{Score(opp)}$$

   Score covers actual VPs (hidden VP cards included), robber-aware production by resource,
   diversity, expansion reach, ports, hand readiness, discard risk, dev cards, and army and road leads.
3. **Random outcomes are scored in expectation**: dev-card draws, robber steals.
4. **Short lookahead where it pays**:
   - trade, then the best build;
   - knight, then the best robber move;
   - Road Building, then the two best roads;
   - top-3 first moves played greedily to the end of the turn.
5. **Opening**: a learned model of P(win | the four opening settlements), with a snake-draft search
   that predicts the opponent's picks.
6. **Weights** were tuned by **SPSA self-play** ($\theta^+$ vs $\theta^-$ of our own bot).

The biggest lesson: about 26 of our ~32 points over F came from *what the bot values*, not how far it
searches. A logistic regression that predicted game winners with 78 % accuracy won only 10 % of its
games as a player. See [`docs/STORY.md`](docs/STORY.md) and [`docs/INSIGHTS.md`](docs/INSIGHTS.md).

## Version history

| Version | Change | vs F (local, ≥ 400 games) |
|---|---|---|
| F | catanatron `ValueFunctionPlayer` | 0.50 |
| v1 | value function in VP units, chance in expectation, trade→build lookahead | 0.635 |
| v2 | + knight / Road Building follow-up | 0.683 |
| v3 | + snake-draft opening | 0.726 |
| v5 | + SPSA self-play weights | 0.791 |
| combo | + regime weights + turn planning | 0.793 (52.4 % head-to-head vs v5, 3000 games) |
| comboop1 | + learned opening (op1) | 0.820 |
| comboop1_fix | + audit fix (no pre-roll Monopoly) + clock guard | 0.770 (400 games, fresh seeds) |

---

## Repository layout

| Path | What it is |
|---|---|
| [`army/`](army/README.md) | **Every bot we built or used**, each self-contained and loadable by the harness. Includes the final `comboop1`, its audited variant `comboop1_fix`, and the opponents we evaluate against |
| `bot/` | Research agent: v5 defaults plus every experimental switch (regime, linear eval, robber weight, …) |
| [`tools/`](tools/README.md) | Evaluation (`par_eval`, `h2h`, `gauntlet`, `parallel_eval`), tuning (`spsa`), learning (`gen_data`, `fit`), decision `audit`, packaging |
| `experiments/` | Variant wrappers for every experiment, SPSA logs, audit data, raw outputs |
| [`docs/`](docs/) | [`STORY.md`](docs/STORY.md) (the day as a story), [`INSIGHTS.md`](docs/INSIGHTS.md) (full results log), [`EXPLAIN_comboop1.md`](docs/EXPLAIN_comboop1.md) (how the final bot works), [`report/`](docs/report/) (report PDF, walkthrough, presentation script), [`results/`](docs/results/) (per-experiment write-ups) |
| `catan_kit/`, `examples/`, `PROBLEM_STATEMENT.md` | The hackathon kit: harness, scoring script, F and a random agent, rules |

## Quick start

Use **Python 3.11**. The engine is a pinned catanatron commit, so do not install catanatron from PyPI.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu   # optional: our agents do not use torch
pip install -r requirements.txt
python -m catan_kit.selfcheck
```

Play the final agent against F through the official, clocked harness:

```bash
python -m catan_kit.evaluate --a army/comboop1/agent.py --b examples/f_agent.py --games 200
python tools/par_eval.py --a army/comboop1/agent.py --b army/f/agent.py --games 1000 --procs 4   # parallel version
```

Run a candidate against the whole bot army, or a head-to-head between two bots (paired boards):

```bash
python tools/gauntlet.py army/comboop1/agent.py 400 4 4000000 --skip ab2
python tools/h2h.py army/comboop1/agent.py army/v5/agent.py 600
```

Package a bot for upload (a zip with `agent.py` at the top level):

```bash
cd army/comboop1 && zip ../../comboop1.zip *.py *.json && cd -
```

## Credits and licence

Built on [catanatron](https://github.com/bcollazo/catanatron) by Bryan Collazo (GPL-3.0) and the
organisers' hackathon kit. Released under GPL-3.0-or-later: see [`LICENSE`](LICENSE) and
[`NOTICE.md`](NOTICE.md). Much of the code and analysis was written with Claude Code; every number
comes from a run in this repository.
