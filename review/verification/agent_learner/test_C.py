from harness import *
import itertools, random
print("=== (C) merge-pair starvation with default regular configs ===")
def merge_report(learner, dfa, data, labels, tag):
    pairs, dist = learner.collect_merge_pairs_simple(dfa, data, labels, max_pairs=20)
    n_init = sum(1 for a, b in pairs if a is dfa.initial_state or b is dfa.initial_state)
    mergeable = [(a,b) for a,b in pairs if a is not dfa.initial_state and b is not dfa.initial_state]
    # how many total same-main-label, same-accepting non-initial pairs exist?
    def main_label(sid):
        d = dist[sid]; return max(d, key=d.get) if d else None
    init = dfa.initial_state
    n_init_eligible = sum(1 for s in dfa.states if s is not init and s.is_accepting == init.is_accepting and main_label(s.state_id) == main_label(init.state_id))
    n_acc = sum(s.is_accepting for s in dfa.states)
    print(f"  {tag}: states={len(dfa.states)} accepting={n_acc} init_is_accepting={init.is_accepting} init_main_label={main_label(init.state_id)} | top20 pairs={len(pairs)} involving_initial={n_init} mergeable_after_filter={len(mergeable)} | states eligible to pair with initial at score 1.0 = {n_init_eligible}")
    return mergeable
for name in REG_CFG:
    for seed in (42, 7):
        try:
            teacher, alphabet, predict_fn, sampler, learner, origin, init_samples, init_labels = build_init(name, seed=seed, verbose=True)
        except RuntimeError as e:
            print(f"  [{name} seed={seed}] {e}"); continue
        data, labels = sampler(num_samples=1000, compute_labels=True)
        labels = np.asarray(labels, dtype=np.float64)
        dfa = origin
        # mini beam loop with beam_size=1, no KL-LUCB: DELTA skipped (no Explaining-FA), DELETE+MERGE
        for it in range(4):
            mergeable = merge_report(learner, dfa, data, labels, f"[{name} seed={seed} round {it}]")
            state = {'current_idx': len(data), 'data': data, 'labels': labels}
            dels = learner._propose_delete(dfa, state, data, labels, set(), 1)
            mers = learner._propose_merge(dfa, state, data, labels, set(), 1)
            print(f"      -> _propose_delete produced {len(dels)} candidates, _propose_merge produced {len(mers)} candidates")
            cands = dels + mers
            if not cands: break
            agr = [learner.compute_agreement(c, data, labels) for c in cands]
            best = cands[int(np.argmax(agr))]
            dfa = best
