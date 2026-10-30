"""Untouched-object report (synthetic DWG, offline): after each edit op, how many objects are byte-identical (raw) between source and
output, per object type, and which untouched objects changed. Layouts, viewports, paper space, blocks, dictionaries included (wtest.layouts).
usage: untouched_report.py [version]"""
import os, sys, collections
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..'), os.path.expanduser('~/dwg-write')]
import dwgdoc, dwgxform as X, wtest, dwgmodel
v = sys.argv[1] if len(sys.argv) > 1 else '2018'
d0 = dwgdoc.Doc(open(os.path.expanduser('~/dwg-write/templates/blank_%s.dwg' % v), 'rb').read())
for f in (wtest.basic, wtest.blocks, wtest.more, wtest.dims, wtest.layouts, wtest.styles):
    try: f(d0)
    except Exception as e: print('build', f.__name__, type(e).__name__)
src = d0.save(); ms = dwgmodel.Model(src); b = dwgdoc.Doc(src); ents = {}
for h in b.entities('*Model_Space'): ents.setdefault(b.otype(h), h)
tot = collections.Counter(); worst = 0; bytype = collections.Counter()
for ot, h in sorted(ents.items()):
    for op in ('move', 'props', 'copy', 'erase'):
        d = dwgdoc.Doc(src)
        try:
            if op == 'move': d.transform(h, X.Transform.translate(7, 3))
            elif op == 'props': d.set_props(h, color=5)
            elif op == 'copy': d.copy_entity(h, X.Transform.translate(5, 5))
            else: d.erase(h)
            mo = dwgmodel.Model(d.save())
        except (NotImplementedError, KeyError): continue
        same = sum(1 for k, o in ms.objs.items() if k in mo.objs and mo.objs[k].raw == o.raw)
        chg = collections.Counter(o.type for k, o in ms.objs.items() if k in mo.objs and mo.objs[k].raw != o.raw)
        bytype.update(chg); tot['cases'] += 1; tot['objs'] += len(ms.objs); tot['identical'] += same
        worst = max(worst, sum(chg.values()))
        if sum(chg.values()) > 12: print('many changed', ot, op, dict(chg))
print(v, dict(tot), 'identical %.3f%%' % (100.0 * tot['identical'] / max(1, tot['objs'])), 'worst changed objects in one edit:', worst)
print('changed objects by type (type: count over all cases):', dict(bytype.most_common(8)))
