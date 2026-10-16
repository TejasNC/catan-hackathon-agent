# Catan agent hackathon: starter kit

Build a program that plays 2-player Catan. It will play against our two bots, F and O, and against the other
teams' programs.

**Read [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) first.** This file is only for getting you started.

---

## 1. Install

**On your team machine the kit is already installed**, in `~/catan-agent-hackathon` with its
virtual environment and a passed self-check: read `~/START_HERE.txt` and skip to section 3. You get
the machine's address and your login at the start of the event; change your password with `passwd`.
A wrong password does not say "Permission denied": the connection just closes. Check the password
and try again. A new password must be at least 8 characters, differ from the old one and not be a
palindrome, or `passwd` refuses it and the old one stays. On your first login, answer `yes` to the
host-key question. A line `client_global_hostkeys_prove_confirm: server gave bad signature` at each
login is harmless.
Each team machine has 8 CPU cores and 16 GB of memory. To work on your own computer as well:

You need **Python 3.11** and **git** (pip uses it to fetch the pinned engine). catanatron needs
at least Python 3.11, and we score on 3.11.

```bash
git clone https://github.com/pbhar-hyde/catan-agent-hackathon.git
cd catan-agent-hackathon
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu    # Linux and Windows only
pip install -r requirements.txt
```

The `torch` line installs the CPU build of PyTorch. Without it, pip on Linux fetches the much
larger CUDA build. On macOS, skip it.

If the install fails:

* **`python3.11: command not found`.** Many systems ship another version, for example Ubuntu 24.04
  ships 3.12. [uv](https://docs.astral.sh/uv/) installs 3.11 next to it: `uv python install 3.11`,
  then `uv venv --python 3.11 .venv` in place of the `python3.11 -m venv` line.
* **pip cannot find `git`.** Install git, then open a new terminal. On Windows: Git for Windows.
* **Windows PowerShell refuses to run `activate`.** Run
  `Set-ExecutionPolicy -Scope Process RemoteSigned` first, in the same window.
* **No PyTorch for your machine.** PyTorch 2.8 has no build for Intel Macs. Develop on Linux, in
  Google Colab or on Kaggle, or write an agent that does not import torch.
* **Google Colab and Kaggle** may run another Python version. The kit installs and passes its
  self-check on Python 3.12 too, but we score on 3.11, so check timings on the leaderboard.

Run every command from the root of this repository: that is where Python finds `catan_kit`.

The engine version is pinned. **Do not upgrade it.** The action space changed between catanatron
releases, so an agent written against another version produces actions our scorer rejects.

## 2. Check the install

```bash
python -m catan_kit.selfcheck
```

Fix any failure before you write agent code. A broken environment produces plausible numbers, not
error messages.

## 3. Play a game

```bash
python -m catan_kit.evaluate --a examples/f_agent.py --b examples/random_agent.py --games 200
```

```
A = examples/f_agent.py
B = examples/random_agent.py
A win rate          1.0000 +-0.0000   (200/200)
A mean CPU / game       97.7 ms   (limit 300 ms + 12.5 ms per decision, at most 1500 ms)
A worst CPU / game     262.5 ms
A games over budget        0      (random moves played after the limit: 0)
A errors                   0      illegal index or exception, of 12611 decisions
A timeouts/crashes    0 / 0     (a silent agent is killed after 3 s)
A load time             0.00 s    (limit 60 s)
wall clock              30.2 s
```

Measured on an idle laptop. Your numbers will differ, and a busy machine reports more CPU for
the same work. The leaderboard reports ours.

This is the script we score with. In the final evaluation we change only the board seeds, the dice key and
the opponents.

## 4. Write your agent

Make a folder for your agent, for example `my_team/`, copy `examples/random_agent.py` into it as
`agent.py`, and edit it.

```python
class Agent:
    def __init__(self):
        """Load weights or tables here. Called once, when your agent's process starts."""

    def decide(self, obs, playable_actions) -> int:
        """Return the INDEX of your chosen action in playable_actions."""
```

Then measure it against F:

```bash
python -m catan_kit.evaluate --a my_team/agent.py --b examples/f_agent.py --games 1000
```

## 5. Submit

Zip the folder, with `agent.py` at the top level of the zip and every file it loads beside it, up
to 100 MB, and upload it from your team machine:

```bash
~/upload.sh my_team.zip
```

Your report goes the same way, as a PDF: `~/upload.sh report.pdf`. Results appear on the team
portal: sign in with your team name and your team leader's phone number. You get its address during
the event. PROBLEM_STATEMENT.md, section 4, has the rules.

Any operating system's zip works: we run your Python files directly, on Linux, with nothing to
build or start. Two things differ from Windows there: file names are case sensitive (`Weights.pt`
is not `weights.pt`), and paths must be built with `os.path.join`, never with `\`.

## 6. What is in here

| Path | What it is |
|---|---|
| `PROBLEM_STATEMENT.md` | the rules, scoring and schedule |
| `catan_kit/obs.py` | what your agent sees, and `sample_world` for search |
| `catan_kit/evaluate.py` | the scoring script |
| `catan_kit/match.py` | the harness it uses: one process per agent, the CPU clock, the masked copy |
| `catan_kit/host.py` | the agent's side of the harness, run in the agent's own process |
| `catan_kit/sandbox.py` | extra isolation used only on our machine, off on yours |
| `catan_kit/selfcheck.py` | install check |
| `catan_kit/_patch.py` | a determinism fix for the engine, applied at import |
| `examples/random_agent.py` | plays a random legal move and scores 0.000 against F |
| `examples/f_agent.py` | **F itself**, one of the two bots you have to beat |


## License

GPL-3.0-or-later, because this kit builds on catanatron. See [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md).
