"""RVT edit chain (offline half): N chained spec-level edits of the writer scene; every step is built by write-lab (rvt_write scene), then saved
through savegate with the reader's own element diff as the manifest, the output of step i is the source of step i+1. Counts false alarms
(VerifyFailed with an exact manifest) and that an undeclared run is refused. usage: chain_rvt_spec.py YEAR SEED_SPEC.json N OUTDIR [--open]"""
import os, sys, json, random, subprocess, hashlib, time
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..')]
import savegate as sg
from savegate.adapters import RvtAdapter
from savegate import rvt_elements as E
WL = os.path.expanduser('~/rvt-research/write-lab')
year, seed, n, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
os.makedirs(out, exist_ok=True); os.environ['SAVEGATE_JOURNAL'] = out + '/journal'
rng = random.Random(int(year)); spec = json.load(open(seed)); cfg = sg.Config(allow_overwrite=True, require_gate=False)
def build(sp, path):
    json.dump(sp, open(path + '.json', 'w')); subprocess.run(['python3', 'rvt_write.py', 'scene', path + '.json', path, '--no-verify'], cwd=WL, check=True, capture_output=True, timeout=900)
    return open(path, 'rb').read()
cur = build(spec, out + '/s0.rte'); ea = E.elements(cur); C = {'ok': 0, 'false_alarm': 0, 'lie_refused': 0, 'lie_accepted': 0}; log = []
for i in range(1, n + 1):
    sp = json.loads(json.dumps(spec)); op = rng.choice(['column', 'mark', 'height', 'annex'])
    if op == 'column' and sp.get('columns'): sp['columns'][0]['x'] = sp['columns'][0]['x'] + rng.choice([1, -1, 2])
    elif op == 'mark': sp['walls'][0]['mark'] = 'W%d' % rng.randint(10, 99)
    elif op == 'height': sp['walls'][1]['height'] = sp['walls'][1]['height'] + rng.choice([1.0, -1.0])
    else: sp['walls'].append({'id': 'annex%d' % i, 'from': [100 + 3 * i, 26], 'to': [102 + 3 * i, 26], 'level': 'L1', 'height': 12.0, 'mark': 'A%d' % i})
    spec = sp; nxt = build(sp, out + '/s%d.rte' % i); eb = E.elements(nxt)
    mod = [k for k in ea if k in eb and ea[k] != eb[k]]; add = [k for k in eb if k not in ea]; dele = [k for k in ea if k not in eb]
    man = {'modified': ['el:%d' % k for k in mod], 'added': ['el:%d' % k for k in add], 'deleted': ['el:%d' % k for k in dele]}
    src = out + '/src.rte'; open(src, 'wb').write(cur)
    mk = lambda: sg.open_doc(src, RvtAdapter(elements_fn=lambda b: ea if b == cur else eb), cfg)
    try:
        with mk() as doc: sg.save_as(doc, nxt, out + '/o%d.rte' % i, man, overwrite=True); C['ok'] += 1
    except sg.VerifyFailed as e: C['false_alarm'] += 1; log.append((i, op, str(e)[:120]))
    if mod or add or dele:
        try:
            with mk() as doc: sg.save_as(doc, nxt, out + '/x%d.rte' % i, {}, overwrite=True); C['lie_accepted'] += 1
        except sg.VerifyFailed: C['lie_refused'] += 1
    print(i, op, 'mod', len(mod), 'add', len(add), 'del', len(dele), dict(C), flush=True)
    cur, ea = nxt, eb
print('FINAL', year, dict(C), log)
