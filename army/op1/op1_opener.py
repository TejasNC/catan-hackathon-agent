"""Opening draft search against M with a learned P(win | opening) model.

M's opening picks are a deterministic function of the board and the settlements already placed
(mayer_base.Agent.draft_pick), so they are predicted exactly here, on node sets, by a port of that
logic. Our picks are chosen to maximise the learned model's score of the final four settlements.
"""
import json
import os
import time

import op1_mbase as MB

NEIGH = MB.NEIGH
M_TOP = int(os.environ.get("M_TOP", 5))
_HERE = os.path.dirname(os.path.abspath(__file__))
_MP = os.path.join(_HERE, os.environ.get("OPEN_MODEL", "open_model.json"))
MODEL = json.load(open(_MP)) if os.path.exists(_MP) else None
W = MODEL["w"] if MODEL else None
USE = MODEL.get("use", list(range(16))) if MODEL else None


def block(free, n):
    f = set(free)
    f.discard(n)
    for nb in NEIGH[n]:
        f.discard(nb)
    return f


class Opener:
    def __init__(self, m_agent):
        self.m = m_agent          # an M Agent, for its pair_value and opp_k

    # ---- the learned score -----------------------------------------------------------------
    def pfeats(self, nodes, c):
        prod = [0.0] * 5
        nums = set()
        ports = set()
        for n in nodes:
            for r, p, t in c.node_tiles[n]:
                prod[MB.RIDX[r]] += p
                nums.add(t.number)
            if n in c.port_of:
                ports.add(c.port_of[n])
        p3 = 1.0 if None in ports else 0.0
        p2 = sum(prod[MB.RIDX[r]] for r in ports if r is not None)
        wd, br, sh, wh, ore = prod
        full = [wd, br, sh, wh, ore, sum(prod), sum(1 for x in prod if x > 0), len(nums),
                p3, p2, 0.0, 0.0, 0.0, min(wh, ore), min(wd, br), min(wd, br, sh, wh)]
        return [full[i] for i in USE]

    def score(self, mine, theirs, c, first):
        a = self.pfeats(mine, c)
        b = self.pfeats(theirs, c)
        z = sum(w * (x - y) for w, x, y in zip(W, a, b))
        return z + W[-1] * (1.0 if first else -1.0)

    # ---- M's picks, ported from mayer_base.Agent.draft_pick (M's own perspective) ---------------
    def m_pick(self, m_nodes, o_nodes, free0, c):
        pv = lambda ns: self.m.pair_value(ns, c)
        lam = self.m.V.p["opp_k"]

        def best_completion(base, free):
            best, bn = -1e9, None
            for n in free:
                v = pv(base + [n])
                if v > best:
                    best, bn = v, n
            return best, bn

        single = sorted(free0, key=lambda n: -pv([n]))
        if len(m_nodes) == 0 and len(o_nodes) == 1:
            best, choice = -1e9, None
            top = single[:M_TOP]
            for x in top:
                fx = block(free0, x)
                for y in top:
                    if y == x or y not in fx:
                        continue
                    f = block(fx, y)
                    vo, _ = best_completion(o_nodes, f)
                    sc = pv([x, y]) - lam * vo
                    if sc > best:
                        best, choice = sc, x
            return choice
        if len(m_nodes) == 1 and len(o_nodes) == 1:
            best, choice = -1e9, None
            for y in single[:25]:
                f = block(free0, y)
                vo, _ = best_completion(o_nodes, f)
                sc = pv(m_nodes + [y]) - lam * vo
                if sc > best:
                    best, choice = sc, y
            return choice
        return best_completion(m_nodes, free0)[1]

    # ---- our pick ------------------------------------------------------------------------------
    def pick(self, mine, theirs, free0, c, first, legal, deadline=float("inf")):
        """Our next settlement node, or None to defer to M's own logic."""
        if W is None:
            return None
        pv = lambda ns: self.m.pair_value(ns, c)
        cand = sorted((n for n in free0 if n in legal), key=lambda n: -pv([n]))
        if first and not mine and not theirs:              # P1, first pick
            best, choice = -1e9, None
            for a1 in cand[:8]:
                if time.process_time() > deadline:
                    break
                f = block(free0, a1)
                b1 = self.m_pick([], [a1], f, c)
                if b1 is None:
                    continue
                f = block(f, b1)
                b2 = self.m_pick([b1], [a1], f, c)
                if b2 is None:
                    continue
                f = block(f, b2)
                s = max(self.score([a1, a2], [b1, b2], c, True) for a2 in f)
                if s > best:
                    best, choice = s, a1
            return choice
        if first and len(mine) == 1:                        # P1, last pick
            return max(cand, key=lambda n: self.score(mine + [n], theirs, c, True))
        if not first and not mine and len(theirs) == 1:     # P2, first of two picks
            best, choice = -1e9, None
            top = cand[:9]
            for x in top:
                if time.process_time() > deadline:
                    break
                fx = block(free0, x)
                for y in top:
                    if y == x or y not in fx:
                        continue
                    f = block(fx, y)
                    b2 = self.m_pick(theirs, [x, y], f, c)
                    if b2 is None:
                        continue
                    s = self.score([x, y], theirs + [b2], c, False)
                    if s > best:
                        best, choice = s, x
            return choice
        if not first and len(mine) == 1 and len(theirs) == 1:   # P2, second pick
            best, choice = -1e9, None
            for y in cand[:15]:
                if time.process_time() > deadline:
                    break
                f = block(free0, y)
                b2 = self.m_pick(theirs, mine + [y], f, c)
                if b2 is None:
                    continue
                s = self.score(mine + [y], theirs + [b2], c, False)
                if s > best:
                    best, choice = s, y
            return choice
        return None
