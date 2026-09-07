"""Load models/*_train_test_split.pkl WITHOUT numpy by stubbing numpy classes in a custom Unpickler."""
import pickle, struct, sys, collections

class NDArrayStub:
    def __init__(self, *a, **k): self.data = None; self.dtype = None; self.shape = None
    def __setstate__(self, state):
        # numpy ndarray state: (version, shape, dtype, is_fortran, rawdata)
        if len(state) == 5:
            _, shape, dtype, _, raw = state
        else:
            shape, dtype, _, raw = state
        self.shape, self.dtype, self.data = shape, dtype, raw
    def tolist(self):
        if isinstance(self.data, list):
            return self.data
        d = self.dtype
        code = getattr(d, 'code', None)
        n = self.shape[0] if self.shape else 1
        if code in ('i8',):
            return list(struct.unpack('<%dq' % n, self.data))
        if code in ('i4',):
            return list(struct.unpack('<%di' % n, self.data))
        raise ValueError(f"unsupported dtype {code}")

class DtypeStub:
    def __init__(self, code, *a, **k): self.code = code
    def __setstate__(self, state): pass

def _reconstruct(cls, shape, dt):
    return NDArrayStub()

class StubUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module.startswith('numpy'):
            if name in ('_reconstruct',): return _reconstruct
            if name == 'ndarray': return NDArrayStub
            if name == 'dtype': return DtypeStub
            if name == 'scalar':
                return lambda dt, raw: struct.unpack('<q', raw)[0] if getattr(dt,'code','')=='i8' else raw
            return lambda *a, **k: None
        return super().find_class(module, name)

for name in ['mnist', 'ECG', 'wafer']:
    path = f'/home/fbi0826/automata-based-explainer/models/{name}_train_test_split.pkl'
    with open(path, 'rb') as f:
        d = StubUnpickler(f).load()
    print('=' * 70)
    print(name, 'keys:', {k: (v if not isinstance(v, NDArrayStub) else f'<ndarray shape={v.shape} dtype={getattr(v.dtype,"code",None)}>') for k, v in d.items()})
    Xtr = d['X_train'].tolist(); Xte = d['X_test'].tolist()
    ytr = d['y_train'].tolist(); yte = d['y_test'].tolist()
    print(f'  X_train={len(Xtr)} y_train={len(ytr)}  X_test={len(Xte)} y_test={len(yte)}')
    Ltr = [len(s) for s in Xtr]; Lte = [len(s) for s in Xte]
    print(f'  train len min/max/mean = {min(Ltr)}/{max(Ltr)}/{sum(Ltr)/len(Ltr):.2f}   test len min/max = {min(Lte)}/{max(Lte)}')
    alpha_tr = sorted(set(t for s in Xtr for t in s)); alpha_te = sorted(set(t for s in Xte for t in s))
    print(f'  alphabet(train)={alpha_tr}  alphabet(test)={alpha_te}')
    print(f'  label dist train={dict(collections.Counter(ytr))}  test={dict(collections.Counter(yte))}')
    Str = set(map(tuple, Xtr)); Ste = set(map(tuple, Xte))
    print(f'  unique train seqs={len(Str)}  unique test seqs={len(Ste)}  train∩test seqs={len(Str & Ste)}')
    # label consistency for duplicated sequences inside train
    lab = collections.defaultdict(set)
    for s, y in zip(Xtr, ytr): lab[tuple(s)].add(y)
    conflict = sum(1 for v in lab.values() if len(v) > 1)
    print(f'  train seqs with conflicting labels={conflict}')
    print(f'  X_train[0]={Xtr[0]} y={ytr[0]}')
    if name == 'mnist': print(f'  X_train[23]={Xtr[23]} y={ytr[23]}')
    # test instance in config present?
    cfg_inst = {'mnist': ['R','R','R','R','D','D','L','D','D','L','D','D'],
                'ECG': ['VL','M','M','M','H','H','SH','SL','SH','VL','SL'],
                'wafer': ['VL','VH','VH','SL','M','SH','SH','SH','SH','SH','SH','SH','SL','L','L','L','L']}[name]
    idx_tr = [i for i, s in enumerate(Xtr) if list(s) == cfg_inst]
    idx_te = [i for i, s in enumerate(Xte) if list(s) == cfg_inst]
    print(f'  cfg test_instance found in X_train at {idx_tr[:5]} (labels {[ytr[i] for i in idx_tr[:5]]}), in X_test at {idx_te[:5]}')
