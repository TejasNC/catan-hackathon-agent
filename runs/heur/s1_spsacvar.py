import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import agent as _a
_P = {'prod': 0, 'res_w': 0}
_HERE = os.path.dirname(os.path.abspath(__file__))
_P = json.load(open(os.path.join(_HERE, "spsa_cvar_params.json")))
_P["res_w"] = tuple(_P["res_w"])
class Agent(_a.Agent):
    def __init__(self):
        super().__init__(dict(_P))
