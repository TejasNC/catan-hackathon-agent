# Notes for agents working in this repo

- **Evaluation opponents:** use the bot army in `army/`. Run
  `python tools/gauntlet.py <candidate>/agent.py 400` for the full pool, and
  `python tools/par_eval.py --a <candidate>/agent.py --b army/f/agent.py --games 1000 --seed0 123000`
  for the clocked F number. See `army/README.md` for what each bot is and its known strength.
- **F is a measuring stick only:** never use F (or `army/f`) as a training/tuning opponent.
- Results and lessons: `docs/INSIGHTS.md`; the story: `docs/STORY.md`. Submissions: #1 = `army/v5`
  (= `bot/agent.py` defaults), final = `army/comboop1`. Experiment wrappers and raw outputs: `experiments/`.
- Run `python -m catan_kit.selfcheck` after setting up the venv; use Python 3.11.
- Never `pkill -f` a pattern that appears in your own command line (it kills your shell);
  use a bracketed pattern such as `pkill -f "tools/h[2]h.py"`.
