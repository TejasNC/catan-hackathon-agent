import sys; sys.path.insert(0,'.')
from catan_kit._patch import ensure_hash_seed; ensure_hash_seed()
from catan_kit import match
def main():
    seed, idx = int(sys.argv[1]), int(sys.argv[2])
    recs,_=match.play_chunk('redteam/log_cop1.py','redteam/robber_spam.py',[seed],[idx],clock_a=True,clock_b=True)
    print(recs[0]['a'], recs[0]['turns'], recs[0]['winner'])

if __name__=='__main__':
    main()
