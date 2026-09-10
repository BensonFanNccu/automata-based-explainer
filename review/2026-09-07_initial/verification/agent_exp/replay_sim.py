"""Pure-Python replica of DFASampler.perturbation (src/learner/dfa_learner.py:419-519)
to quantify how much of the 'external holdout' drawn in run_kllucb_comparison.py:686-687
is replayed by the search's own sequential draws after DFASampler re-seeds global random."""
import random, sys

def perturbation(instance, symbols, edit_distance, num_samples, rng=None):
    _r = rng if rng is not None else random
    local_paths_set = set()
    max_trials = 10000
    no_progress_count = 0
    max_no_progress = 50
    trials = 0
    while len(local_paths_set) < num_samples and trials < max_trials:
        trials += 1
        new_instance = list(instance)
        remaining_edits = _r.randint(0, edit_distance)
        while remaining_edits > 0:
            possible_ops = ["replace", "insert"]
            if len(new_instance) > 0:
                possible_ops.append("delete")
            op = _r.choice(possible_ops)
            if op == "replace":
                idx = _r.randrange(len(new_instance))
                different_symbols = [s for s in symbols if s != new_instance[idx]]
                if different_symbols:
                    new_instance[idx] = _r.choice(different_symbols)
            elif op == "insert":
                idx = _r.randint(0, len(new_instance))
                new_instance.insert(idx, _r.choice(symbols))
            elif op == "delete":
                idx = _r.randrange(len(new_instance))
                del new_instance[idx]
            remaining_edits -= 1
        hashable = tuple(new_instance)
        before = len(local_paths_set)
        local_paths_set.add(hashable)
        if len(local_paths_set) == before:
            no_progress_count += 1
        else:
            no_progress_count = 0
        if no_progress_count > max_no_progress:
            break
    return local_paths_set, trials

CONFIGS = {
    "mnist": dict(alphabet=["R","U","L","D"], ed=3, init=500,
                  inst=['R','R','R','R','D','D','L','D','D','L','D','D']),
    "ECG": dict(alphabet=["VL","L","SL","M","SH","H","VH"], ed=2, init=500,
                inst=['VL','M','M','M','H','H','SH','SL','SH','VL','SL']),
    "wafer": dict(alphabet=["VL","L","SL","M","SH","H","VH"], ed=2, init=500,
                  inst=['VL','VH','VH','SL','M','SH','SH','SH','SH','SH','SH','SH','SL','L','L','L','L']),
    "SecureHandshake": dict(alphabet=sorted(["ack","alert","cert","hello","key","retry","verify"]), ed=7, init=1000,
                  inst=['hello','cert','verify','key','ack','key','ack','cert','verify','key','ack']),
    "DocumentReleaseWorkflow": dict(alphabet=sorted(["approve","assign","comment","draft","hold","publish","review","revise"]), ed=5, init=1000,
                  inst=['draft','review','review','review','approve','comment','comment','approve','comment','publish']),
    "MultiObligationOrder": dict(alphabet=sorted(["blue","dock","drop","green","move","pick","wait","yellow"]), ed=5, init=1000,
                  inst=['pick','blue','green','move','drop','dock','yellow']),
}
HOLDOUT = 10000
BATCH = 1000

def frac(a, b):
    return (len(a & b) / len(a)) if a else float('nan')

for name, c in CONFIGS.items():
    print("=" * 78)
    print(f"{name}: len(inst)={len(c['inst'])}, |alphabet|={len(c['alphabet'])}, edit_distance={c['ed']}, init_num_samples={c['init']}")
    for seed in (0, 1, 2):
        # --- holdout draw: create_explainer(seed) -> random.seed(seed); holdout_sampler(num_samples=10000)
        random.seed(seed)
        H, tH = perturbation(c['inst'], c['alphabet'], c['ed'], HOLDOUT)
        # --- WITH-KL run: create_explainer(seed) -> random.seed(seed); init draw; then eval batches of 1000 (sequential, global random)
        random.seed(seed)
        V, tV = perturbation(c['inst'], c['alphabet'], c['ed'], c['init'])
        t_after = [tV]
        batches = []
        tot = tV
        for k in range(4):
            Bk, tk = perturbation(c['inst'], c['alphabet'], c['ed'], BATCH)
            tot += tk
            t_after.append(tot)
            batches.append(Bk)
        # --- NO-KL run with prebuilt init: create_explainer(seed) -> random.seed(seed); first draw is directly a 1000 batch
        random.seed(seed)
        B1_no, _ = perturbation(c['inst'], c['alphabet'], c['ed'], BATCH)
        # --- control: an independent stream (different seed) of 1000
        random.seed(seed + 12345)
        B_ind, _ = perturbation(c['inst'], c['alphabet'], c['ed'], BATCH)
        cum = set(V)
        cover = []
        for Bk in batches:
            cum |= Bk
            cover.append(len(cum & H) / len(H))
        print(f" seed={seed}: |H|={len(H)} (trials used={tH}, requested 10000)  |V|={len(V)} (trials={tV})")
        print(f"   V subset of H: {V <= H}  frac(V in H)={frac(V,H):.3f}")
        print(f"   batch1..4 frac in H: " + ", ".join(f"{frac(B,H):.3f}" for B in batches) + f"   cumulative trials after each: {t_after[1:]}")
        print(f"   share of H covered by V+batch1..k: " + ", ".join(f"{x:.3f}" for x in cover))
        print(f"   NO-KL first batch: |B1'|={len(B1_no)}  V subset of B1': {V <= B1_no}  frac(B1' in H)={frac(B1_no,H):.3f}")
        print(f"   control independent seed batch: frac in H = {frac(B_ind,H):.3f}   frac in V = {frac(B_ind,V):.3f}")
