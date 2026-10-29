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
        if opn and row in os.environ.get('SG_ROWS', row).split(','):
            tmp = os.path.join(out, '%s_writer_sg%s%s.rte' % (year, row.replace('_', ''), sha))   # the write-lab guest job needs a '<year>_writer_*' style name (other names failed with the add-in port refused)
            open(tmp, 'wb').write(open(path, 'rb').read())
            for attempt in range(int(os.environ.get("SG_ATTEMPTS", "3"))):
                time.sleep(int(os.environ.get("SG_SETTLE", "20")))      # let the previous Revit instance and its add-in port settle (back-to-back fresh starts refused the port)     # the guest add-in port sometimes refuses right after a fresh Revit start: harness flake, retry (same bytes)
                r = subprocess.run(['python3', WL + '/tools/open_test.py', year, tmp, 'sg%s%s%d' % (row[:3], sha, attempt)], capture_output=True, text=True, cwd=WL, timeout=7200)
                res = (r.stdout.strip().splitlines() or ['NO_OUTPUT ' + r.stderr[-200:]])[-1]
                res = 'OPEN_OK' if 'ok=True' in res else 'FAIL ' + res
                if res == 'OPEN_OK': break
            if attempt: res += ' (attempt %d)' % (attempt + 1)
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
