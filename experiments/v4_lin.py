import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import agent as _a
W = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lin_v2.json")))
class Agent(_a.Agent):
    def __init__(self):
        # names order: see tools/feats.NAMES; card idx 15, knight_hand 22, dev_other 23
        super().__init__(dict(lin=W, card=W[15], knight_hand=W[22], dev_other=W[23], opp_k=1.0))
