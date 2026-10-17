import os, sys, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.selfplay import load_agent_class, play
import collections
A = load_agent_class(sys.argv[1])
F = load_agent_class("examples/f_agent.py")
times = collections.defaultdict(list)
class Timed:
    def __init__(self, a): self.a = a
    def decide(self, obs, acts):
        t = time.process_time(); i = self.a.decide(obs, acts); dt = time.process_time() - t
        st = obs._game.state
        key = "init" if st.is_initial_build_phase else st.current_prompt.name
        times[key].append((dt, len(acts)))
        return i
t0 = time.process_time()
a = A()
print("init", time.process_time() - t0)
for k in range(int(sys.argv[2])):
    play(Timed(a), F(), 7000 + k, k % 2 == 0)
for k, v in times.items():
    ds = sorted(x[0] for x in v)
    print(f"{k:20s} n={len(v):5d} mean={1000*sum(ds)/len(ds):.2f}ms p99={1000*ds[int(.99*len(ds))]:.2f} max={1000*ds[-1]:.2f}ms acts={sum(x[1] for x in v)/len(v):.1f}")
