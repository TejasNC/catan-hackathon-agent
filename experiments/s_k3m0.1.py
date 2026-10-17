import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import search as _s
class Agent(_s.Agent):
    TURN_K=3
    MARGIN=0.1
