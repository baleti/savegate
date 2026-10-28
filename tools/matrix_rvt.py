"""RVT oracle-gate matrix runner. usage: matrix_rvt.py OUTDIR [--open] [scene ...]
Scenes are the write-lab writers' own synthetic files (no Autodesk data). Builds files ONLY through savegate
(verify on): identity SAVEAS, 100x overwrite cycles, unicode+long path. --open then opens each file in the offline
Revit VM via write-lab tools/open_test.py (API open, audit off). Appends ledger rows to OUTDIR/ledger.tsv."""
import os, sys, time, hashlib, subprocess
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..')]
import savegate as sg
WL = os.path.expanduser('~/rvt-research/write-lab')
DEF = ['2024_writer_frame2', '2026_writer_frame2']

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; opn = '--open' in sys.argv
    out = a[0]; scenes = a[1:] or DEF
    os.makedirs(out, exist_ok=True)
    os.environ.setdefault('SAVEGATE_JOURNAL', os.path.join(out, 'journal'))
    cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=3)
    rows = []
    def emit(path, year, row):
        sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()[:8]; res = 'not_run'
        if opn:
            tmp = os.path.join(out, 'open_%s_%s.rte' % (row, sha)); open(tmp, 'wb').write(open(path, 'rb').read())   # ASCII name for the guest transfer
            r = subprocess.run(['python3', WL + '/tools/open_test.py', year, tmp, 'sg_%s_%s' % (row[:3], sha)], capture_output=True, text=True, cwd=WL, timeout=1800)
            res = (r.stdout.strip().splitlines() or ['NO_OUTPUT ' + r.stderr[-200:]])[-1]
            res = 'OPEN_OK' if 'ok=True' in res else 'FAIL ' + res
        rows.append((sha, 'RVT', year, row, res, time.strftime('%Y-%m-%d')))
        print(*rows[-1], sep='\t'); sys.stdout.flush()
    for sc in scenes:
        year = sc[:4]; src = open(f'{WL}/scenes/{sc}.rte', 'rb').read()
        base = os.path.join(out, sc + '.rte'); open(base, 'wb').write(src)
        with sg.open_doc(base, None, cfg) as doc:
            p = os.path.join(out, 'identity_' + sc + '.rte'); sg.save_as(doc, src, p, {}, overwrite=True); emit(p, year, 'identity')
            q = os.path.join(out, 'uniäö 日本 ' + 'x' * 120, 'identity_' + sc + '.rte'); os.makedirs(os.path.dirname(q), exist_ok=True)
            sg.save_as(doc, src, q, {}, overwrite=True); emit(q, year, 'unicode_long_path')
        cyc = os.path.join(out, 'cycles_' + sc + '.rte'); open(cyc, 'wb').write(src)
        with sg.open_doc(cyc, None, cfg) as doc:
            for i in range(100): sg.save(doc, src, {})
        emit(cyc, year, 'cycles100')
    open(os.path.join(out, 'ledger.tsv'), 'a').write(''.join('\t'.join(r) + '\n' for r in rows))

main()
