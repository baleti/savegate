"""Per-phase SAVE! latency (write_tmp, readback, verify, backup, commit; total) for DWG files: given files (local corpus: aggregate numbers only) or
synthetic drawings grown to several sizes. usage: perf_phases.py [FILE.dwg ...]  (no args: synthetic 2018 with N extra entities)"""
import os, sys, time, shutil, tempfile, statistics
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..'), os.path.expanduser('~/dwg-write')]
import savegate as sg, dwgdoc, dwgxform as X, wtest
cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2)
w = tempfile.mkdtemp(prefix='sgp', dir=os.environ.get('SG_TOOL_TMP')); os.environ['SAVEGATE_JOURNAL'] = w + '/j'; os.environ['SAVEGATE_CACHE'] = w + '/c'
files = sys.argv[1:]; rows = []
try:
    if not files:
        for n in (0, 500, 3000, 10000):
            d = dwgdoc.Doc(open(os.path.expanduser('~/dwg-write/templates/blank_2018.dwg'), 'rb').read()); wtest.basic(d)
            for i in range(n): d.add_line((i, 0), (i, 5))
            p = os.path.join(w, 'syn%d.dwg' % n); open(p, 'wb').write(d.save()); files.append(p)
    for f in files:
        p = os.path.join(w, os.path.basename(f))
        if p != f: shutil.copyfile(f, p)
        try: doc = sg.open_doc(p, None, cfg)
        except sg.UnsupportedVersion: print('skip (unsupported version)', os.path.basename(f)[:8]); continue
        with doc:
            d = dwgdoc.Doc(doc.buf); h = next(iter(d.entities('*Model_Space'))); t = time.time()
            try: d.transform(h, X.Transform.translate(1, 1)); man = {'modified': [h]}
            except Exception: man = {'added': [d.add_line((0, 0), (1, 1))]}
            out = d.save(); t_edit = time.time() - t
            r = sg.save(doc, out, man)
        tm = r.report['timing']; tm = {k: round(v, 2) for k, v in tm.items()}
        rows.append((len(doc.buf) // 1024, t_edit, r.elapsed, tm)); print('%6d kB edit+serialize %.2fs  save total %.2fs  %s' % (rows[-1][0], t_edit, r.elapsed, tm), flush=True)
finally: shutil.rmtree(w, ignore_errors=True)
