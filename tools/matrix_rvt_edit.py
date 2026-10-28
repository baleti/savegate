"""RVT edit rows: save a writer scene A -> edited scene B through savegate with the element manifest (reader-verified), then open the
result in the offline Revit VM. usage: matrix_rvt_edit.py OUTDIR A.rte B.rte ELEMENT_ID ROWNAME [--open]"""
import os, sys, time, hashlib, subprocess
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..')]
import savegate as sg
from savegate.adapters import RvtAdapter
from savegate import rvt_elements as E
WL = os.path.expanduser('~/rvt-research/write-lab')
out, a, b, eid, row = sys.argv[1:6]
os.makedirs(out, exist_ok=True); os.environ['SAVEGATE_JOURNAL'] = out + '/journal'
cfg = sg.Config(allow_overwrite=True, require_gate=False)
src = os.path.join(out, 'src.rte'); open(src, 'wb').write(open(a, 'rb').read())
with sg.open_doc(src, RvtAdapter(elements_fn=E.elements), cfg) as doc:
    p = os.path.join(out, '2024_writer_sg%s.rte' % row)
    r = sg.save_as(doc, open(b, 'rb').read(), p, {'modified': ['el:' + eid]}, overwrite=True)
sha = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:8]; res = 'not_run'
if '--open' in sys.argv:
    for att in range(3):
        time.sleep(20)
        o = subprocess.run(['python3', WL + '/tools/open_test.py', '2024', p, 'sg%s%s%d' % (row, sha, att)], capture_output=True, text=True, cwd=WL, timeout=1800)
        res = 'OPEN_OK' if 'ok=True' in o.stdout else 'FAIL ' + (o.stdout.strip().splitlines() or ['NO_OUTPUT'])[-1]
        if res == 'OPEN_OK': break
    if att: res += ' (attempt %d)' % (att + 1)
print(sha, 'RVT2024', row, res, time.strftime('%Y-%m-%d'), sep='\t')
