import sys, os, types
SCRATCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRATCH, 'pylibs'))
sys.path.insert(0, os.path.join(SCRATCH, 'aalpy_src'))
sys.path.insert(0, '/home/fbi0826/automata-based-explainer/src')
pydot = types.ModuleType('pydot')
for n in ['Dot','Node','Edge','graph_from_dot_file','graph_from_dot_data']:
    setattr(pydot, n, object)
sys.modules['pydot'] = pydot
mpl = types.ModuleType('matplotlib'); plt = types.ModuleType('matplotlib.pyplot')
mpl.pyplot = plt; sys.modules['matplotlib'] = mpl; sys.modules['matplotlib.pyplot'] = plt
import numpy as np
from aalpy.automata.Dfa import Dfa, DfaState
from aalpy.learning_algs import run_RPNI
from automaton.load_dfa import load_dfa_from_dot, create_automata_dfa_predictor
from automaton.dfa_utils import get_alphabet, serialize_dfa, is_valid_dfa, check_dfa_path_accepted
from learner.dfa_learner import DFASampler, DFALearner, _delete_candidate_from_state, _merge_candidate_from_pair, _delta_candidate_from_edge

REG_CFG = {
    "SecureHandshake": dict(filename="secure_handshake.dot", edit_distance=7,
        test_instance=['hello','cert','verify','key','ack','key','ack','cert','verify','key','ack']),
    "DocumentReleaseWorkflow": dict(filename="document_release_workflow.dot", edit_distance=5,
        test_instance=['draft','review','review','review','approve','comment','comment','approve','comment','publish']),
    "MultiObligationOrder": dict(filename="multi_obligation_color_order.dot", edit_distance=5,
        test_instance=['pick','blue','green','move','drop','dock','yellow']),
}

def build_init(name, seed=42, init_num_samples=1000, init_state_range=(25,65), max_init_attempts=40, verbose=False):
    cfg = REG_CFG[name]
    teacher = load_dfa_from_dot(cfg["filename"])
    alphabet = get_alphabet(teacher)
    predict_fn = create_automata_dfa_predictor(teacher)
    sampler = DFASampler(predictor=predict_fn, alphabet=list(alphabet), seed=seed, edit_distance=cfg["edit_distance"])
    sampler.set_instance_label(list(cfg["test_instance"]))
    learner = DFALearner()
    origin = None; tried = []
    for attempt in range(1, max_init_attempts+1):
        init_samples, init_labels = sampler(num_samples=init_num_samples, compute_labels=True)
        pos = [s for s, l in zip(init_samples, init_labels) if int(l) == 1]
        neg = [s for s, l in zip(init_samples, init_labels) if int(l) == 0]
        cand = learner.create_init_automata("Tabular", pos, neg)
        tried.append(len(cand.states))
        if init_state_range[0] <= len(cand.states) <= init_state_range[1]:
            origin = cand; break
    if origin is None:
        raise RuntimeError(f"init failed, tried={tried}")
    origin.make_input_complete("sink_state")
    if verbose: print(f"[{name}] init attempts={len(tried)} states={tried} -> {len(origin.states)} states (with sink); instance_label={sampler.instance_label}")
    return teacher, alphabet, predict_fn, sampler, learner, origin, init_samples, init_labels

def check_legal(dfa, alphabet):
    """Return list of problems: determinism is implied by dict; check completeness, dangling targets, initial in states, accepting exists."""
    probs = []
    states = list(dfa.states)
    if dfa.initial_state not in states: probs.append("initial not in states")
    if not any(s.is_accepting for s in states): probs.append("no accepting")
    ids = [s.state_id for s in states]
    if len(ids) != len(set(ids)): probs.append("duplicate state ids")
    for s in states:
        for sym in alphabet:
            if sym not in s.transitions: probs.append(f"missing {s.state_id}/{sym}")
        for sym, t in s.transitions.items():
            if t not in states: probs.append(f"dangling {s.state_id}/{sym}->{t.state_id}")
    return probs
