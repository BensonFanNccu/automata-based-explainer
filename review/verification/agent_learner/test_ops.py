from harness import *
from learner.dfa_learner import _delete_candidate_from_state, _merge_candidate_from_pair, _delta_candidate_from_edge, _collect_cxp_records_for_path
import pickle, random, itertools
print("=== operator legality / copy / pickle / missing-edge / accept flip ===")
teacher, alphabet, predict_fn, sampler, learner, origin, init_samples, init_labels = build_init("SecureHandshake", seed=42, verbose=True)
data, labels = sampler(num_samples=1000, compute_labels=True)
labels = np.asarray(labels, dtype=np.float64)
alpha = sorted(get_alphabet(origin))
print("  origin alphabet:", alpha, "| sampler alphabet:", sorted(alphabet), "| origin complete over sampler alphabet:", not check_legal(origin, sorted(alphabet)))
print("  origin problems:", check_legal(origin, alpha))
print("  origin.states[0] is initial:", origin.states[0] is origin.initial_state)
# copy / pickle round trip keeps initial first?
c = origin.copy(); print("  copy(): states[0] is initial:", c.states[0] is c.initial_state, "| initial id:", c.initial_state.state_id)
p = pickle.loads(pickle.dumps(origin)); print("  pickle: states[0] is initial:", p.states[0] is p.initial_state, "| initial id:", p.initial_state.state_id)
# delete candidates
bad = 0; n = 0; init_kept = 0
for s in origin.states:
    cand = _delete_candidate_from_state((origin, s.state_id))
    if cand is None: continue
    n += 1
    probs = check_legal(cand, alpha)
    if probs: bad += 1; print("   DELETE problem", s.state_id, probs[:3])
    cc = pickle.loads(pickle.dumps(cand))
    if cc.states[0] is not cc.initial_state or cc.initial_state.state_id != origin.initial_state.state_id: print("   DELETE pickle initial mismatch!")
    if cand.initial_state.state_id == origin.initial_state.state_id: init_kept += 1
print(f"  DELETE: {n} candidates, {bad} illegal, initial preserved in {init_kept}")
# merge candidates
pairs, dist = learner.collect_merge_pairs_simple(origin, data, labels, max_pairs=10**9)
majority = {sid: (max(d, key=d.get) if d else 0) for sid, d in dist.items()}
bad = 0; n = 0; flips = 0; flip_examples = []
for a, b in pairs:
    if a is origin.initial_state or b is origin.initial_state: continue
    cand = _merge_candidate_from_pair((origin, a.state_id, b.state_id, majority))
    if cand is None: continue
    n += 1
    probs = check_legal(cand, alpha)
    if probs: bad += 1; print("   MERGE problem", a.state_id, b.state_id, probs[:3])
    merged = next(x for x in cand.states if x.state_id == a.state_id)
    if merged.is_accepting != a.is_accepting:
        flips += 1
        if len(flip_examples) < 3: flip_examples.append((a.state_id, b.state_id, a.is_accepting, b.is_accepting, merged.is_accepting, majority.get(a.state_id), majority.get(b.state_id)))
print(f"  MERGE: {n} candidates, {bad} illegal, accepting-status flipped vs both inputs in {flips}; examples (s1,s2,acc1,acc2,merged_acc,maj1,maj2): {flip_examples}")
# delta candidates: rewire
bad = 0; n = 0
edges = [(s.state_id, sym) for s in origin.states for sym in s.transitions][:30]
for sid, sym in edges:
    for t in origin.states[:5]:
        cand = _delta_candidate_from_edge((origin, sid, sym, t.state_id))
        if cand is None: continue
        n += 1
        probs = check_legal(cand, alpha)
        if probs: bad += 1; print("   DELTA problem", sid, sym, t.state_id, probs[:3])
print(f"  DELTA rewire: {n} candidates, {bad} illegal")
# missing-edge branch
d2 = origin.copy()
src = d2.states[3]; sym = alpha[0]
del src.transitions[sym]
res = [_delta_candidate_from_edge((d2, src.state_id, sym, t.state_id)) for t in d2.states]
print(f"  DELTA missing-edge: src={src.state_id} sym={sym} removed; candidates over all targets -> non-None count = {sum(r is not None for r in res)} (expected 0 => branch dead)")
# does _collect_cxp_records_for_path record the missing transition?
from learner.dfa_learner import _collect_cxp_records_for_path
path = None
cur = d2.initial_state
# find a data path hitting the missing edge
for seq in data:
    c = d2.initial_state; hit = False
    for x in seq:
        if x not in c.transitions: hit = (c is src); break
        c = c.transitions[x]
    if hit: path = seq; break
if path:
    cx, miss = _collect_cxp_records_for_path((d2, path, {a:i for i,a in enumerate(alpha)}, "/dev/null", True))
    print(f"  _collect_cxp_records_for_path on a path hitting the missing edge -> cxp={cx} missing={miss}")
# is_valid_dfa on 1-state
print("  is_valid_dfa(origin):", is_valid_dfa(origin))
# to_state_setup stale prefix: mutate then copy
m = origin.copy()
victim = next(s for s in m.states if s is not m.initial_state and not s.is_accepting)
mm = _delete_candidate_from_state((m, victim.state_id))
print("  after delete, stale prefixes present:", any(s.prefix for s in mm.states), "| copy() keeps initial first:", mm.copy().states[0].state_id == mm.initial_state.state_id)
# combinations order: does initial come first?
print("  combinations(dfa.states,2) first 3 pairs:", [(a.state_id,b.state_id) for a,b in itertools.islice(itertools.combinations(origin.states,2),3)])
print("=== SA/GA/PSO single-op variants ===")
import random
random.seed(0)
seen = set(); bad = 0; n = 0; same = 0
for i in range(60):
    c = learner._propose_delete_single(origin, random.randrange(len(origin.states)), data, labels, seen)
    if c is origin: same += 1; continue
    n += 1; p = check_legal(c, alpha)
    if p: bad += 1; print("   delete_single problem", p[:3])
print(f"  _propose_delete_single: {n} new, {same} returned original, {bad} illegal")
seen = set(); bad = 0; n = 0; same = 0; flips = 0
for i in range(60):
    a = random.randrange(len(origin.states)); b = random.randrange(len(origin.states))
    c = learner._propose_merge_single(origin, a, b, data, labels, seen)
    if c is origin: same += 1; continue
    n += 1; p = check_legal(c, alpha)
    if p: bad += 1; print("   merge_single problem", p[:3])
print(f"  _propose_merge_single: {n} new, {same} returned original, {bad} illegal")
seen = set(); bad = 0; n = 0; same = 0
for i in range(60):
    c = learner._propose_delta_single(origin, random.randrange(len(origin.states)), random.randrange(len(origin.states)), data, labels, seen)
    if c is origin: same += 1; continue
    n += 1; p = check_legal(c, alpha)
    if p: bad += 1; print("   delta_single problem", p[:3])
print(f"  _propose_delta_single: {n} new, {same} returned original, {bad} illegal")
print("=== teachers loaded from DOT ===")
for fn in ["secure_handshake.dot", "document_release_workflow.dot", "multi_obligation_color_order.dot"]:
    t = load_dfa_from_dot(fn)
    al = sorted(get_alphabet(t))
    ids = sorted(s.state_id for s in t.states)
    phantom = [s.state_id for s in t.states if not s.transitions and not any(s in x.transitions.values() for x in t.states)]
    incomplete = [s.state_id for s in t.states if s.transitions and any(a not in s.transitions for a in al)]
    print(f"  {fn}: states={len(t.states)} alphabet={al} initial={t.initial_state.state_id} phantom(no in/out edges)={phantom} states_with_missing_symbols={len(incomplete)} e.g. {incomplete[:3]}")
