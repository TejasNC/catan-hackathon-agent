# Third-party notice

This project builds on **catanatron** by Bryan Collazo, released under GPL-3.0-or-later.

* Upstream: <https://github.com/bcollazo/catanatron>
* catanatron is **not** redistributed here. `requirements.txt` installs it from its GitHub
  repository, pinned to one commit.
* `examples/valuefn_agent.py` and `army/valuefn/` wrap catanatron's `ValueFunctionPlayer`, and
  `army/ab2/` wraps its `AlphaBetaPlayer`, unchanged.

The match harness in `catan_eval/` (clocked agent processes, hidden-information masking, the
determinism patch) and `examples/random_agent.py` were adapted from an open-source GPL-3.0 starter
kit for catanatron agents (<https://github.com/pbhar-hyde/catan-agent-hackathon>), and modified.

`catan_eval/_patch.py` changes one catanatron function at run time, in memory only. It sorts the
list of bank and port trade offers so that their order depends on their contents and not on memory
layout. Nothing on disk is modified; the reason is in that file's docstring.

This project is released under GPL-3.0-or-later. See `LICENSE`.
