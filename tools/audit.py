"""Decision audit: is the bot's choice the best move? Monte Carlo rollouts per candidate action.

    python tools/audit.py BOT.py GAMES PROCS SEED0 OUT.jsonl [ROLLOUTS=32] [K=5]

1. Self-play BOT vs BOT; sample decisions (every rare decision type, a fraction of PLAY_TURN ones).
2. For each sampled decision: candidates = the bot's choice + the top-K other legal actions by the bot's
   own 1-ply score (all actions if few). Each candidate is played out ROLLOUTS times with BOT for both
   sides, the same dice seeds for every candidate (common random numbers).
3. Unbiased regret: rollouts [0, R/2) select the best alternative, rollouts [R/2, R) measure
   best_alt - bot_choice. Averaged per decision category, a mean significantly > 0 means the bot is
   systematically wrong there.
"""
import os, sys, json, random, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp

RARE = {"BUILD_INITIAL_SETTLEMENT": 1.0, "BUILD_INITIAL_ROAD": 0.5, "MOVE_ROBBER": 0.5, "DISCARD": 0.5}


def category(game, actions, choice):
    st = game.state
    pr = st.current_prompt.name
    ch = actions[choice].action_type.name
    if pr != "PLAY_TURN":
        return pr
    if st.is_road_building:
        return "FREE_ROAD"
    types = {a.action_type.name for a in actions}
    if "ROLL" in types:
        return "PRE_ROLL:" + ch                      # roll vs play a dev card first
    if ch in ("PLAY_KNIGHT_CARD", "PLAY_MONOPOLY", "PLAY_YEAR_OF_PLENTY", "PLAY_ROAD_BUILDING"):
        return "DEV_PLAY:" + ch
    return "TURN:" + ch                             # build / buy / trade / end turn


def _rollout(game, seed, A):
    from tools.selfplay import Wrap
    from catanatron.game import TURNS_LIMIT
    g = game.copy()
    ws = [Wrap(c, A(), seed + i) for i, c in enumerate(g.state.colors)]
    g.state.players = ws
    random.seed(seed)
    n = 0
    while g.winning_color() is None and g.state.num_turns < 400 and n < 3000:
        g.play_tick()
        n += 1
    return g.winning_color()


def audit_decision(game, actions, choice, me, A, R, K, seed):
    agent = A()
    scored = []
    for i, a in enumerate(actions):
        try:
            v, _ = agent.eval_action(game, a, me)
        except Exception:
            v = -1e9
        scored.append((v, i))
    scored.sort(reverse=True)
    cands = [choice] + [i for _, i in scored if i != choice][:K]
    res = {}
    for i in cands:
        g = game.copy()
        try:
            g.execute(actions[i])
        except Exception:
            continue
        wins = []
        for j in range(R):
            w = _rollout(g, seed + 1000 * j, A)
            wins.append(1.0 if w == me else 0.0)
        res[i] = wins
    if choice not in res or len(res) < 2:
        return None
    h = R // 2
    sel = {i: sum(w[:h]) / h for i, w in res.items()}
    alts = [i for i in res if i != choice]
    best = max(alts, key=lambda i: sel[i])
    diff = [res[best][j] - res[choice][j] for j in range(h, R)]
    full = {i: sum(w) / R for i, w in res.items()}
    return dict(regret=sum(diff) / len(diff), best=actions[best].action_type.name,
                best_val=str(actions[best].value), choice=actions[choice].action_type.name,
                choice_val=str(actions[choice].value), wr_choice=full[choice], wr_best_full=max(full.values()),
                n_cands=len(res), bot_is_full_argmax=full[choice] >= max(full.values()) - 1e-9)


def work(args):
    path, seeds, R, K, out = args
    os.environ["PYTHONHASHSEED"] = "0"
    from tools.selfplay import load_agent_class, play
    A = load_agent_class(path)
    rng = random.Random(seeds[0])
    with open(out, "w") as f:
        for s in seeds:
            picked = []

            def hook(game, color, acts, i):
                pr = game.state.current_prompt.name
                p = RARE.get(pr, None)
                if p is None:
                    types = {a.action_type.name for a in acts}
                    dev = types & {"PLAY_KNIGHT_CARD", "PLAY_MONOPOLY", "PLAY_YEAR_OF_PLENTY", "PLAY_ROAD_BUILDING"}
                    p = 0.6 if dev else 0.08
                if rng.random() < p and len(acts) > 1:
                    picked.append((game.copy(), list(acts), i, color))

            play(A(), A(), s, s % 2 == 0, hook=hook)
            for game, acts, i, color in picked:
                cat = category(game, acts, i)
                r = audit_decision(game, acts, i, color, A, R, K, s * 7 + len(acts))
                if r is None:
                    continue
                r.update(cat=cat, seed=s, turn=game.state.num_turns)
                f.write(json.dumps(r) + "\n")
                f.flush()


def summarise(path):
    rows = [json.loads(l) for l in open(path)]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["cat"]].append(r)
    print(f"{'category':40s} {'n':>4s} {'mean regret':>12s} {'±95%':>7s} {'bot=argmax':>10s}  most common better alt")
    for cat, rs in sorted(by.items(), key=lambda kv: -sum(r["regret"] for r in kv[1]) / len(kv[1])):
        reg = [r["regret"] for r in rs]
        m = sum(reg) / len(reg)
        sd = (sum((x - m) ** 2 for x in reg) / max(1, len(reg) - 1)) ** 0.5
        ci = 1.96 * sd / max(1, len(reg)) ** 0.5
        arg = sum(r["bot_is_full_argmax"] for r in rs) / len(rs)
        alts = collections.Counter(r["best"] for r in rs if r["regret"] > 0)
        print(f"{cat:40s} {len(rs):4d} {m:12.3f} {ci:7.3f} {arg:10.2f}  {alts.most_common(3)}")


if __name__ == "__main__":
    if sys.argv[1] == "--summary":
        for p in sys.argv[2:]:
            pass
        import glob
        files = [f for p in sys.argv[2:] for f in glob.glob(p)]
        tmp = "/tmp/_audit_all.jsonl"
        with open(tmp, "w") as o:
            for fpath in files:
                o.write(open(fpath).read())
        summarise(tmp)
        sys.exit()
    from catan_kit._patch import ensure_hash_seed
    ensure_hash_seed()
    path, games, procs, seed0, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    R = int(sys.argv[6]) if len(sys.argv) > 6 else 32
    K = int(sys.argv[7]) if len(sys.argv) > 7 else 5
    seeds = list(range(seed0, seed0 + games))
    ctx = mp.get_context("spawn")
    ps = [ctx.Process(target=work, args=((path, seeds[k::procs], R, K, f"{out}_{k}.jsonl"),)) for k in range(procs)]
    [p.start() for p in ps]
    [p.join() for p in ps]
    summarise_files = [f"{out}_{k}.jsonl" for k in range(procs)]
    with open(out, "w") as o:
        for fpath in summarise_files:
            o.write(open(fpath).read())
    summarise(out)
