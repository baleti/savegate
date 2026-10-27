import sys, os, time, resource; sys.path[:0] = [os.path.expanduser('~/src/savegate'), os.path.expanduser('~/dwg-write')]
import savegate as sg, dwgdoc, dwgxform as X
n = int(sys.argv[1]); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
os.environ['SAVEGATE_JOURNAL'] = out + '/j'
t = time.time(); d = dwgdoc.Doc(open(os.path.expanduser('~/dwg-write/templates/blank_2018.dwg'), 'rb').read())
for i in range(n): d.add_line((i, 0), (i, 10))
buf = d.save(); p = out + '/huge.dwg'; open(p, 'wb').write(buf)
print('build', n, 'lines', len(buf) >> 20, 'MB', round(time.time() - t, 1), 's', flush=True)
cfg = sg.Config(allow_overwrite=True, require_gate=False)
with sg.open_doc(p, None, cfg) as doc:
    d = dwgdoc.Doc(doc.buf); h = list(d.entities('*Model_Space'))[5]; d.transform(h, X.Transform.translate(1, 1)); out2 = d.save()
    t = time.time(); r = sg.save(doc, out2, {'modified': [h]}); print('save+verify', round(time.time() - t, 1), 's', r.size >> 20, 'MB', flush=True)
print('peak RSS MB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >> 10)
