"""python redteam/sanity.py OPP.py N seed0 -> logs suspicious comboop1 decisions + per-type CPU."""
import os, sys, time, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multiprocessing as mp
from catanatron.models.enums import ActionType as AT, RESOURCES

def run(args):
    opp, seed, a_first = args
    from tools.selfplay import load_agent_class, play, Wrap
    A = load_agent_class(os.environ.get("CAND","army/comboop1/agent.py"))(); B = load_agent_class(opp)()
    flags = collections.Counter(); times = collections.defaultdict(list); ex = []
    orig = A.decide
    last = {}
    def timed(obs, acts):
        t = time.process_time(); i = orig(obs, acts); dt = time.process_time() - t
        st = obs._game.state
        key = "INIT" if st.is_initial_build_phase else st.current_prompt.name + ":" + acts[i].action_type.name
        times[key].append(dt); return i
    A.decide = timed
    def hook(game, color, acts, i):
        from catanatron.models.player import Color
        if color != Color.RED: return
        st = game.state; a = acts[i]; types = {x.action_type for x in acts}
        opp = [c for c in st.colors if c != color][0]
        b = st.board
        if a.action_type == AT.END_TURN:
            if AT.BUILD_CITY in types: flags["end_turn_with_city"] += 1
            if AT.BUILD_SETTLEMENT in types: flags["end_turn_with_settlement"] += 1; ex.append((seed, a_first, st.num_turns, "end_with_settle"))
        if a.action_type == AT.MOVE_ROBBER:
            t = b.map.land_tiles[a.value[0]]
            mine = sum(1 for n in t.nodes.values() if b.buildings.get(n, (None,))[0] == color)
            theirs = sum(1 for n in t.nodes.values() if b.buildings.get(n, (None,))[0] == opp)
            if mine > 0: flags["robber_on_own_tile"] += 1
            if theirs == 0: flags["robber_no_opp_building"] += 1
            if a.value[1] is None and any(x.action_type == AT.MOVE_ROBBER and x.value[1] is not None for x in acts):
                flags["robber_no_steal_when_possible"] += 1
        if a.action_type == AT.PLAY_MONOPOLY:
            from catanatron.state_functions import player_num_resource_cards
            n = player_num_resource_cards(st, opp, a.value)
            flags["monopoly_played"] += 1
            if n == 0: flags["monopoly_zero"] += 1
            elif n == 1: flags["monopoly_one"] += 1
        if a.action_type == AT.PLAY_YEAR_OF_PLENTY: flags["yop"] += 1
        if a.action_type == AT.MARITIME_TRADE:
            give = [x for x in a.value[:4] if x]; n = len(give)
            flags[f"trade_{n}to1"] += 1
            rates = [x for x in acts if x.action_type == AT.MARITIME_TRADE and x.value[0] == a.value[0]]
            if any(len([y for y in x.value[:4] if y]) < n for x in rates): flags["trade_worse_rate"] += 1
    res, g = play(A, B, seed, a_first, hook=hook)
    return res, dict(flags), {k: v for k, v in times.items()}, ex, g.state.num_turns

if __name__ == "__main__":
    from catan_kit._patch import ensure_hash_seed
    ensure_hash_seed()
    opp, n, s0 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    procs = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    with mp.get_context("spawn").Pool(procs) as p:
        R = p.map(run, [(opp, s0 + k // 2, k % 2 == 0) for k in range(n)], chunksize=2)
    w = sum(1 if r[0] else (0.5 if r[0] is None else 0) for r in R) / n
    F = collections.Counter(); T = collections.defaultdict(list); EX = []
    for r in R:
        F.update(r[1]); EX += r[3]
        for k, v in r[2].items(): T[k] += v
    print(f"comboop1 vs {opp}: win {w:.3f} n={n} no_winner={sum(r[0] is None for r in R)} mean_turns={sum(r[4] for r in R)/n:.0f}")
    print("flags:", dict(F))
    print("examples:", EX[:8])
    rows = sorted(T.items(), key=lambda kv: -max(kv[1]))
    for k, v in rows[:14]:
        v = sorted(v); print(f"  {k:40s} n={len(v):6d} mean={1000*sum(v)/len(v):6.1f}ms p99={1000*v[int(.99*(len(v)-1))]:6.1f} max={1000*v[-1]:6.1f}")
    pg = [sum(sum(v) for v in r[2].values()) for r in R]
    print(f"  per-game CPU mean {sum(pg)/n:.2f}s max {max(pg):.2f}s")
