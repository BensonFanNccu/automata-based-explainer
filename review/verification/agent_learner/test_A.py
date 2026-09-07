from harness import *
import random, pickle, collections
print("=== (A) perturbation edge cases ===")
def try_case(instance, alphabet, ed, n=1000, seed=0):
    s = DFASampler(predictor=lambda seqs: np.zeros(len(seqs), dtype=int), alphabet=alphabet, seed=seed, edit_distance=ed)
    s.instance = list(instance); s.instance_label = 0
    try:
        paths, _ = s.perturbation(n)
        return f"OK ({len(paths)} samples)"
    except Exception as e:
        return f"CRASH {type(e).__name__}: {e}"
for inst, ed in [([], 1), (['a'], 1), (['a'], 2), (['a','b'], 2), (['a','b'], 3), (['a','b','c'], 3), (['a','b','c'], 4), (['a']*7, 7), (['a']*6, 7), (['a']*11, 7)]:
    print(f"  len={len(inst):2d} ed={ed}: {try_case(inst, ['a','b','c'], ed)}")
print("  single-symbol alphabet len=5 ed=2:", try_case(['a']*5, ['a'], 2))
print("  single-symbol alphabet len=5 ed=2 requesting 1000:", try_case(['a']*5, ['a'], 2, n=1000))
# probability of crash per sample for len==ed-1
print("=== crash probability estimate per perturbation() call of 1000 samples, over 200 trials ===")
for L, ed in [(1,2),(2,3),(6,7),(7,7),(4,5)]:
    crashes = 0
    for t in range(200):
        r = try_case(['a']*L, ['a','b','c'], ed, seed=t)
        crashes += r.startswith("CRASH")
    print(f"  len={L} ed={ed}: {crashes}/200 calls crashed")
print("=== real-world X_train lengths (models/*_train_test_split.pkl) ===")
for name in ["mnist", "ECG", "wafer"]:
    with open(f"/home/fbi0826/automata-based-explainer/models/{name}_train_test_split.pkl", "rb") as f:
        split = pickle.load(f)
    X_train = split["X_train"]
    lens = [len(x) for x in X_train]
    c = collections.Counter(lens)
    print(f"  {name}: n={len(X_train)} min_len={min(lens)} max_len={max(lens)} first10_lens={lens[:10]} X_train[23]_len={lens[23] if len(lens)>23 else None} count(len<=3)={sum(1 for l in lens if l<=3)} count(len<=2)={sum(1 for l in lens if l<=2)}")
    alph = sorted(set(tok for seq in X_train for tok in seq))
    print(f"     alphabet from X_train = {alph}")
