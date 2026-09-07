"""Replicates DFASampler.perturbation (dfa_learner.py:419-519) verbatim and measures
(a) how many unique samples one call returns for the default experiment configs, and
(b) how much the init (validation) sample overlaps a KL-LUCB training batch."""
import random, statistics

def perturbation(instance, alphabet, edit_distance, num_samples, _r):
    symbols = alphabet
    local_paths_set = set()
    max_trials = 10000; no_progress_count = 0; max_no_progress = 50; trials = 0
    while len(local_paths_set) < num_samples and trials < max_trials:
        trials += 1
        new_instance = list(instance)
        remaining_edits = _r.randint(0, edit_distance)
        while remaining_edits > 0:
            possible_ops = ["replace", "insert"]
            if len(new_instance) > 0: possible_ops.append("delete")
            op = _r.choice(possible_ops)
            if op == "replace":
                idx = _r.randrange(len(new_instance))
                different_symbols = [s for s in symbols if s != new_instance[idx]]
                if different_symbols: new_instance[idx] = _r.choice(different_symbols)
            elif op == "insert":
                idx = _r.randint(0, len(new_instance)); new_instance.insert(idx, _r.choice(symbols))
            elif op == "delete":
                idx = _r.randrange(len(new_instance)); del new_instance[idx]
            remaining_edits -= 1
        hashable = tuple(new_instance)
        before = len(local_paths_set); local_paths_set.add(hashable)
        if len(local_paths_set) == before: no_progress_count += 1
        else: no_progress_count = 0
        if no_progress_count > max_no_progress: break
    return [list(s) for s in local_paths_set], trials

configs = {
 "SecureHandshake": (['hello','cert','verify','key','ack','key','ack','cert','verify','key','ack'], ["ack","alert","cert","hello","key","retry","verify"], 7, 1000, 1000),
 "DocumentReleaseWorkflow": (['draft','review','review','review','approve','comment','comment','approve','comment','publish'], ["approve","assign","comment","draft","hold","publish","review","revise"], 5, 1000, 1000),
 "MultiObligationOrder": (['pick','blue','green','move','drop','dock','yellow'], ["blue","dock","drop","green","move","pick","wait","yellow"], 5, 1000, 1000),
 "mnist": (['R','R','R','R','D','D','L','D','D','L','D','D'], ["R","U","L","D"], 3, 500, 1000),
 "ECG": (['VL','M','M','M','H','H','SH','SL','SH','VL','SL'], ["VL","L","SL","M","SH","H","VH"], 2, 500, 1000),
 "wafer": (['VL','VH','VH','SL','M','SH','SH','SH','SH','SH','SH','SH','SL','L','L','L','L'], ["VL","L","SL","M","SH","H","VH"], 2, 500, 1000),
}
for name,(inst, alpha, ed, init_n, batch) in configs.items():
    r = random.Random(42)
    init, t0 = perturbation(inst, alpha, ed, init_n, r)
    counts=[]; trials=[]; overlaps=[]; le1_in_init=0
    init_set = set(map(tuple, init))
    for _ in range(20):
        b, t = perturbation(inst, alpha, ed, batch, r)
        counts.append(len(b)); trials.append(t)
        overlaps.append(len(init_set & set(map(tuple,b))))
    # count how many members of init set are within edit distance <=1 (crude: length diff<=1 and hamming<=1 when same length)
    def within1(a,b):
        if a==b: return True
        if len(a)==len(b): return sum(x!=y for x,y in zip(a,b))<=1
        if abs(len(a)-len(b))!=1: return False
        s,l=(a,b) if len(a)<len(b) else (b,a)
        for i in range(len(l)):
            if l[:i]+l[i+1:]==s: return True
        return False
    le1 = sum(1 for s in init_set if within1(list(s), inst))
    print(f"{name:24s} init draw: {len(init)}/{init_n} (trials={t0}); batch draws min/max={min(counts)}/{max(counts)} of {batch}, trials mean={statistics.mean(trials):.0f}; "
          f"overlap(init ∩ batch) mean={statistics.mean(overlaps):.0f} = {100*statistics.mean(overlaps)/len(init):.1f}% of init; init members within edit<=1 of instance: {le1}")
