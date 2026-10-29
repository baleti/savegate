"""RVT class edit rows: base scene A and variants (one spec key changed each, built by write-lab). The manifest is the reader's own
element diff (so the test checks the whole path: edit -> declared elements -> savegate verify -> Revit open).
usage: matrix_rvt_classes.py OUTDIR YEAR A.rte name=variant.rte ... [--open]"""
import os, sys, time, hashlib, subprocess
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..')]
import savegate as sg
from savegate.adapters import RvtAdapter
from savegate import rvt_elements as E
WL = os.path.expanduser('~/rvt-research/write-lab')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
out, year, a = args[:3]; variants = [v.split('=', 1) for v in args[3:]]
os.makedirs(out, exist_ok=True); os.environ['SAVEGATE_JOURNAL'] = out + '/journal'
cfg = sg.Config(allow_overwrite=True, require_gate=False)
A = open(a, 'rb').read(); ea = E.elements(A); rows = []
for name, vp in variants:
    B = open(vp, 'rb').read(); eb = E.elements(B)
    ids = [k for k in ea if ea[k] != eb.get(k)] + [k for k in eb if k not in ea]
    src = os.path.join(out, 'src.rte'); open(src, 'wb').write(A)
    with sg.open_doc(src, RvtAdapter(elements_fn=lambda b: ea if b == A else eb), cfg) as doc:
        p = os.path.join(out, '%s_writer_sgcls%s.rte' % (year, name))
        sg.save_as(doc, B, p, {'modified': ['el:%d' % i for i in ids]}, overwrite=True)
    try:   # an undeclared run must be refused
        with sg.open_doc(src, RvtAdapter(elements_fn=lambda b: ea if b == A else eb), cfg) as doc:
            sg.save_as(doc, B, p + '.x', {}, overwrite=True); refused = False
    except sg.VerifyFailed: refused = True
    sha = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:8]; res = 'not_run'
    if '--open' in sys.argv:
        for att in range(int(os.environ.get('SG_ATTEMPTS', '6'))):
            time.sleep(30)
            o = subprocess.run(['python3', os.environ.get('SG_OPEN_TOOL', WL + '/tools/open_test.py'), year, p, 'sgc%s%d' % (sha, att)], capture_output=True, text=True, cwd=WL, timeout=9000)
            res = 'OPEN_OK' if 'ok=True' in o.stdout else 'FAIL'
            if res == 'OPEN_OK': break
        res += ' (attempt %d)' % (att + 1)
    print(sha, 'RVT' + year, 'edit_' + name, res, 'n_el=%d undeclared_refused=%s' % (len(ids), refused), time.strftime('%Y-%m-%d'), sep='\t', flush=True)
