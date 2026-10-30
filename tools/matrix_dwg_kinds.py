"""DWG entity-kind coverage (offline, no AutoCAD): for every entity kind present in a synthetic drawing and every editor op
(move, props, copy, erase) run a real savegate save_as with an exact manifest. Reports PASS / UNSUPPORTED (editor raises
NotImplementedError/KeyError) / FAIL (VerifyFailed or other). usage: matrix_dwg_kinds.py [versions...]  (default 2000 2010 2018)"""
import os, sys, collections
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..'), os.path.expanduser('~/dwg-write')]
import tempfile, atexit, shutil
_dirs = []
atexit.register(lambda: [shutil.rmtree(d, ignore_errors=True) for d in _dirs])
def _mk(**kw):
    d = tempfile.mkdtemp(**kw); _dirs.append(d); return d
import savegate as sg, dwgdoc, dwgxform as X, wtest
YEARS = {'2000': 'AC1015', '2004': 'AC1018', '2010': 'AC1024', '2013': 'AC1027', '2018': 'AC1032'}
AUDIT = '--audit' in sys.argv; vers = [a for a in sys.argv[1:] if not a.startswith('--')] or ['2000', '2010', '2018']
OPS = ('move', 'props', 'copy', 'erase')
tot = collections.Counter(); fails = []
cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=1)
for v in vers:
    tpl = open(os.path.expanduser('~/dwg-write/templates/blank_%s.dwg' % v), 'rb').read()
    d = dwgdoc.Doc(tpl)
    for f in (wtest.basic, wtest.blocks, wtest.more, wtest.dims):
        try: f(d)
        except Exception as e: print('build', f.__name__, type(e).__name__, str(e)[:60])
    work = _mk(prefix='sgk', dir=os.environ.get('SG_TOOL_TMP')); src = os.path.join(work, 'src.dwg'); open(src, 'wb').write(d.save())
    os.environ['SAVEGATE_JOURNAL'] = work + '/j'
    kinds = {}
    for h in dwgdoc.Doc(open(src, 'rb').read()).entities('*Model_Space'): kinds.setdefault(dwgdoc.Doc(open(src, 'rb').read()).otype(h), h) if False else None
    base = dwgdoc.Doc(open(src, 'rb').read())
    for h in base.entities('*Model_Space'): kinds.setdefault(base.otype(h), h)
    with sg.open_doc(src, None, cfg) as doc:
        for ot, h in sorted(kinds.items()):
            for op in OPS:
                dd = dwgdoc.Doc(doc.buf); man = {'modified': [], 'added': [], 'deleted': []}
                try:
                    if op == 'move': dd.transform(h, X.Transform.translate(7, 3)); man['modified'] = [h]
                    elif op == 'props': dd.set_props(h, color=5); man['modified'] = [h]
                    elif op == 'copy': man['added'] = [dd.copy_entity(h, X.Transform.translate(5, 5))]
                    else: dd.erase(h); man['deleted'] = [h]
                    out = dd.save()
                except (NotImplementedError, KeyError) as e:
                    tot['UNSUPPORTED'] += 1; print(v, ot, op, 'UNSUPPORTED', type(e).__name__); continue
                try:
                    op_ = os.path.join(work, 'o.dwg'); sg.save_as(doc, out, op_, man, overwrite=True); tot['PASS'] += 1
                    if AUDIT and (not os.environ.get('AUDIT_KINDS') or str(ot) in os.environ['AUDIT_KINDS'].split(',')):
                        err = wtest.audit(op_, op_ + '.o'); tot['AUDIT_OK' if err is None else 'AUDIT_FAIL'] += 1
                        print(v, ot, op, 'AUDIT_OK' if err is None else 'AUDIT_FAIL ' + str(err)[:150], flush=True)
                except Exception as e:
                    tot['FAIL'] += 1; fails.append((v, ot, op, type(e).__name__, str(e)[:100])); print(v, ot, op, 'FAIL', type(e).__name__, str(e)[:100])
print(dict(tot)); sys.exit(1 if tot['FAIL'] else 0)
