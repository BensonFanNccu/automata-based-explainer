from harness import *
print("=== (C) round-0 merge starvation across seeds (max_pairs=20, beam_size=1) ===")
for name in REG_CFG:
    rows = []
    for seed in range(10):
        try:
            teacher, alphabet, predict_fn, sampler, learner, origin, init_samples, init_labels = build_init(name, seed=seed)
        except RuntimeError as e:
            rows.append((seed, "init-fail")); continue
        data, labels = sampler(num_samples=1000, compute_labels=True)
        labels = np.asarray(labels, dtype=np.float64)
        pairs, dist = learner.collect_merge_pairs_simple(origin, data, labels, max_pairs=20)
        n_init = sum(1 for a, b in pairs if a is origin.initial_state or b is origin.initial_state)
        rows.append((seed, len(origin.states), n_init, 20 - n_init))
    print(f"  {name}: (seed, states, top20_pairs_involving_initial, usable_pairs) = {rows}")
