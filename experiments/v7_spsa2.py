import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import agent as _a
P = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "spsa2.jsonl.params.json")))
P = {k: (tuple(v) if isinstance(v, list) else v) for k, v in P.items()}
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(P)
