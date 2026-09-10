"""Read hyperparameters out of torch checkpoints (zip format) without torch, by stubbing torch classes."""
import zipfile, pickle, collections

class Stub:
    def __init__(self, *a, **k): self.a = a
    def __setstate__(self, s): pass
    def __repr__(self): return "<tensor>"

class TorchStubUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module.startswith('torch'):
            if name == '_rebuild_tensor_v2': return lambda *a, **k: Stub()
            if name == 'OrderedDict': return collections.OrderedDict
            return Stub
        if module == 'collections' and name == 'OrderedDict':
            return collections.OrderedDict
        return super().find_class(module, name)
    def persistent_load(self, pid):
        return None

for name in ['mnist', 'ECG', 'wafer']:
    path = f'/home/fbi0826/automata-based-explainer/models/{name}_classifier_trained.pth'
    with zipfile.ZipFile(path) as z:
        pkl = [n for n in z.namelist() if n.endswith('data.pkl')][0]
        with z.open(pkl) as f:
            ck = TorchStubUnpickler(f).load()
    hp = {k: v for k, v in ck.items() if k != 'model_state'}
    print('=' * 60); print(name, hp)
    ms = ck['model_state']
    print('  state_dict keys:', list(ms.keys())[:12], '... total', len(ms))
