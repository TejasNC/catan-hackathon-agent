"""Write a runs/ variant file from fitted weights (tools/fit.py *_w.npy), in VP units.
python tools/mk_lin_variant.py W.npy OUT.py lin|blend"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools.feats import NAMES

w = np.load(sys.argv[1]); w = w / w[0]
W = {n: round(float(x), 4) for n, x in zip(NAMES, w)}
mode = sys.argv[3]
hdr = ("import os, sys\n"
       "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot'))\n"
       "import agent as _a\n")
if mode == "lin":
    # pure learned linear evaluation; dev-card EV terms take the matching fitted weights
    body = (f"W = {[W[n] for n in NAMES]}  # VP units, order tools/feats.NAMES, from {os.path.basename(sys.argv[1])}\n"
            "class Agent(_a.Agent):\n"
            "    def __init__(self):\n"
            f"        super().__init__(dict(lin=W, card=W[{NAMES.index('card')}], knight_hand=W[{NAMES.index('knight_hand')}],"
            f" dev_other=W[{NAMES.index('dev_other')}], opp_k=1.0))\n")
else:
    # hand-tuned v5 value, static asset weights replaced by the regression (negatives clamped to 0)
    pe = [W[f"prodE_{r}"] for r in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE")]
    pl = [W[f"prodL_{r}"] for r in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE")]
    m = sum(pe) / 5
    P = dict(prod=round(m, 4), prod_late=round(sum(pl) / 5, 4), res_w=tuple(round(x / m, 3) for x in pe),
             div=max(0, W["div"]), exp1=max(0, W["exp1"]), exp2=max(0, W["exp2"]), exp_n=max(0, W["expn"]),
             port3=max(0, W["port3"]), port2=max(0, W["port2"]), road_len=max(0, W["road_len"]))
    body = (f"P = {P}  # static assets from {os.path.basename(sys.argv[1])} (VP units); transition terms stay v5\n"
            "class Agent(_a.Agent):\n"
            "    def __init__(self):\n"
            "        super().__init__(dict(P))\n")
open(sys.argv[2], "w").write(hdr + body)
