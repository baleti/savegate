"""Bit-flip power test of the DWG verify gate (synthetic data): flip one random bit in a writer output, save_as with the exact manifest;
ESCAPE = accepted although the decoded block names / entity count differ from the expected result. usage: gate_bitflip.py TRIALS [version]"""
import os, sys, random, tempfile
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..'), os.path.expanduser('~/dwg-write')]
import savegate as sg, dwgdoc, wtest, dwgmodel
n = int(sys.argv[1]); v = sys.argv[2] if len(sys.argv) > 2 else '2018'
d0 = dwgdoc.Doc(open(os.path.expanduser('~/dwg-write/templates/blank_%s.dwg' % v), 'rb').read())
for f in (wtest.basic, wtest.blocks, wtest.more, wtest.dims):
    try: f(d0)
    except Exception: pass
src = d0.save(); rng = random.Random(7); w = _mk(prefix='sgb', dir=os.environ.get('SG_TOOL_TMP')); os.environ['SAVEGATE_JOURNAL'] = w + '/j'
p = os.path.join(w, 'f.dwg'); open(p, 'wb').write(src); cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=1)
C = {'refused': 0, 'harmless': 0, 'ESCAPE': 0}
import dwgxform as X
dd = dwgdoc.Doc(src); bb = dwgdoc.Doc(src); kinds = {}
for h in bb.entities('*Model_Space'): kinds.setdefault(bb.otype(h), h)
man = {'added': [dd.copy_entity(kinds[7], X.Transform.translate(5, 5))], 'modified': [], 'deleted': []}
man['added'].append(dd.copy_entity(kinds[20], X.Transform.translate(5, 5)))   # INSERT + dimension copies: the tolerated structural side effects
good = dd.save(); names = {}
exp = dict(dwgmodel.Model(src).blocks)
try:
    with sg.open_doc(p, None, cfg) as doc: sg.save_as(doc, good, os.path.join(w, 'g.dwg'), man, overwrite=True); print('control ok')
except Exception as e: print('CONTROL FAILS', e)
for t in range(n):
    b = bytearray(good); i = rng.randrange(len(b)); b[i] ^= 1 << rng.randrange(8)
    try:
        with sg.open_doc(p, None, cfg) as doc: sg.save_as(doc, bytes(b), os.path.join(w, 'o.dwg'), man, overwrite=True)
    except Exception: C['refused'] += 1; continue
    try: nm = dict(dwgmodel.Model(open(os.path.join(w, 'o.dwg'), 'rb').read()).blocks)
    except Exception: nm = None
    if nm is not None and all(nm.get(h) == n for h, n in exp.items()): C['harmless'] += 1
    else: C['ESCAPE'] += 1; print('ESCAPE byte', i)
print(C); sys.exit(1 if C['ESCAPE'] else 0)
