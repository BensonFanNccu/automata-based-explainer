"""Extract KL-LUCB helpers from automata_beam.py via ast and verify them numerically."""
import ast, math, numpy as np
src = open('/home/fbi0826/automata-based-explainer/src/explainer/automata_beam.py').read()
tree = ast.parse(src)
want = {'kl_bernoulli','dup_bernoulli','dlow_bernoulli','compute_beta','select_critical_arms','to_sample'}
mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want], type_ignores=[])
ns = {'np': np, 'namedtuple': __import__('collections').namedtuple}
exec(compile(mod, 'beam_funcs', 'exec'), ns)
kl, dup, dlow, beta_fn, sel, to_sample = (ns[k] for k in ['kl_bernoulli','dup_bernoulli','dlow_bernoulli','compute_beta','select_critical_arms','to_sample'])

def kl_scalar(p, q):
    eps = 1e-12
    p = min(max(p, eps), 1-eps); q = min(max(q, eps), 1-eps)
    return p*math.log(p/q) + (1-p)*math.log((1-p)/(1-q))

def exact_up(p, level, iters=200):
    lo, hi = p, 1.0
    for _ in range(iters):
        mid = (lo+hi)/2
        if kl_scalar(p, mid) > level: hi = mid
        else: lo = mid
    return (lo+hi)/2

def exact_low(p, level, iters=200):
    lo, hi = 0.0, p
    for _ in range(iters):
        mid = (lo+hi)/2
        if kl_scalar(p, mid) > level: lo = mid
        else: hi = mid
    return (lo+hi)/2

print("== compute_beta vs KL-LUCB paper beta(t,delta)=log(k1*K*t^alpha/delta)+loglog(...)")
for K,t,d in [(1,1,0.01),(40,1,0.01),(40,50,0.01),(60,1000,0.01)]:
    b = beta_fn(K,t,d); tmp = math.log(405.5*K*t**1.1/d); ref = tmp+math.log(tmp)
    print(f"  K={K:3d} t={t:5d} delta={d}: code={b:.6f} ref={ref:.6f} diff={b-ref:.2e}")

print("== dup/dlow (n_iter=10) vs 200-iter bisection; error and sign")
worst_up = worst_low = 0.0; sign_up_ok = sign_low_ok = True
for p in [0.0, 0.3, 0.5, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0]:
    for n in [1, 10, 100, 1000, 5000, 20000]:
        for beta in [math.log(1/0.01), beta_fn(40,1,0.01), beta_fn(60,200,0.01)]:
            lvl = beta/n
            u = float(dup(np.array([p]), np.array([lvl]))[0]); l = float(dlow(np.array([p]), np.array([lvl]))[0])
            ue = exact_up(p,lvl); le = exact_low(p,lvl)
            worst_up = max(worst_up, abs(u-ue)); worst_low = max(worst_low, abs(l-le))
            if u < ue - 1e-12: sign_up_ok = False
            if l > le + 1e-12: sign_low_ok = False
print(f"  max |ub - exact| = {worst_up:.3e}; ub always >= exact (conservative)? {sign_up_ok}")
print(f"  max |lb - exact| = {worst_low:.3e}; lb always <= exact (conservative)? {sign_low_ok}")
# typical experiment scale
for p,n in [(0.9,1000),(0.9,2000),(0.8655,1000)]:
    beta = math.log(1/0.01)
    l = float(dlow(np.array([p]), np.array([beta/n]))[0]); u=float(dup(np.array([p]), np.array([beta/n]))[0])
    print(f"  p={p} n={n} beta=log(1/0.01): lb={l:.4f} ub={u:.4f} (exact lb={exact_low(p,beta/n):.4f})")

print("== coverage sanity: P(true mean < lb) with lb from dlow at n=1000, beta=log(1/delta), delta=0.01 (Monte Carlo)")
rng = np.random.default_rng(0)
for p_true in [0.85, 0.9, 0.95]:
    n=1000; trials=20000
    x = rng.binomial(n, p_true, size=trials)/n
    lb = dlow(x, np.full(trials, math.log(1/0.01)/n))
    print(f"  p_true={p_true}: empirical P(lb > p_true) = {np.mean(lb > p_true):.4f} (nominal <= 0.01)")

print("== to_sample loop semantics")
thr, eps_stop = 0.9, 0.05
for mean, ub, lb in [(0.95,0.97,0.93),(0.95,0.97,0.84),(0.88,0.91,0.84),(0.88,0.89,0.84),(0.86,0.89,0.86)]:
    r = bool(to_sample(np.array([mean]), np.array([ub]), np.array([lb]), thr, eps_stop)[0])
    print(f"  mean={mean} ub={ub} lb={lb}: continue={r}")

print("== select_critical_arms: modifies ub/lb in place only for rest/top sets")
means = np.array([0.5,0.9,0.7,0.95]); n = np.array([10.,10.,10.,10.]); ub=np.zeros(4); lb=np.zeros(4)
c = sel(means, ub, lb, n, 0.01, 1, 1)
print("  crit=",c, "ub=",np.round(ub,3), "lb=",np.round(lb,3))
