import os, sys, time, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "army", "comboop1"))
import importlib.util
_spec = importlib.util.spec_from_file_location("cop1_agent_mod", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "army", "comboop1", "agent.py"))
_m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)
LOG = os.environ.get("COP1_LOG", "/tmp/cop1.log")
class Agent(_m.Agent):
    def decide(self, obs, acts):
        t = time.process_time(); i = super().decide(obs, acts); dt = time.process_time() - t
        st = obs._game.state
        with open(LOG, "a") as f:
            f.write(json.dumps([obs.cpu_left, st.current_prompt.name, acts[i].action_type.name, len(acts), round(dt*1000, 1), st.num_turns]) + "\n")
        return i
