"""Oracle-gate matrix runner (DWG). usage: matrix.py OUTDIR [--audit] [versions...]
Builds files ONLY through savegate (verify on), writes OUTDIR/ledger.tsv; --audit sends each file to the offline
AutoCAD VM via wtest.audit (dwgq) and records the result. Synthetic data only."""
import os, sys, time, random, hashlib
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..'), os.path.expanduser('~/dwg-write')]
import savegate as sg, dwgdoc, dwgxform as X, wtest

YEARS = {'2000': 'AC1015', '2004': 'AC1018', '2010': 'AC1024', '2013': 'AC1027', '2018': 'AC1032'}


def run(out, years, audit):
    os.makedirs(out, exist_ok=True)
    os.environ.setdefault('SAVEGATE_JOURNAL', os.path.join(out, 'journal'))
    rows = []
    cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=3)

    def emit(path, v, row):
        sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()[:8]
        res = 'not_run'
        if audit:
            err = wtest.audit(path, path + '.o'); res = 'AUDIT_OK' if err is None else 'FAIL ' + err
        rows.append((sha, YEARS[v], row, res, time.strftime('%Y-%m-%d')))
        print(*rows[-1], sep='\t'); sys.stdout.flush()

    for v in years:
        tpl = open(os.path.expanduser('~/dwg-write/templates/blank_%s.dwg' % v), 'rb').read()
        base = os.path.join(out, 'base_%s.dwg' % v)
        d = dwgdoc.Doc(tpl); wtest.basic(d); wtest.more(d); open(base, 'wb').write(d.save())
        # 1 identity
        with sg.open_doc(base, None, cfg) as doc:
            p = os.path.join(out, 'identity_%s.dwg' % v)
            sg.save_as(doc, dwgdoc.Doc(doc.buf).save(), p, {}, overwrite=True); emit(p, v, 'identity')
            # 2 edits: move / props / copy / erase / add, one file each
            ls = list(dwgdoc.Doc(doc.buf).entities('*Model_Space'))
            for name in ('move', 'props', 'copy', 'erase', 'add'):
                d = dwgdoc.Doc(doc.buf); h = ls[3]; man = {'modified': [], 'added': [], 'deleted': []}
                if name == 'move': d.transform(h, X.Transform.translate(7, 3)); man['modified'] = [h]
                elif name == 'props': d.set_props(h, color=5); man['modified'] = [h]
                elif name == 'copy': man['added'] = [d.copy_entity(h, X.Transform.translate(5, 5))]
                elif name == 'erase': d.erase(h); man['deleted'] = [h]
                else: man['added'] = [d.add_line((0, 0), (9, 9))]
                p = os.path.join(out, 'edit_%s_%s.dwg' % (name, v)); sg.save_as(doc, d.save(), p, man, overwrite=True); emit(p, v, 'edit_' + name)
        # 4 100x overwrite cycles of one file (real SAVE! path)
        cyc = os.path.join(out, 'cycles_%s.dwg' % v); open(cyc, 'wb').write(open(base, 'rb').read())
        rng = random.Random(int(v))
        with sg.open_doc(cyc, None, cfg) as doc:
            for i in range(100):
                d = dwgdoc.Doc(doc.buf); es = list(d.entities('*Model_Space')); man = {'modified': [], 'added': [], 'deleted': []}
                if i % 3 == 0 or len(es) < 5: man['added'] = [d.add_line((i, 0), (i, 5))]
                else:
                    while True:
                        h = rng.choice(es)
                        try: d.transform(h, X.Transform.translate(1, 0)); break
                        except (NotImplementedError, KeyError): d = dwgdoc.Doc(doc.buf)     # type not transformable by the editor: pick another
                    man['modified'] = [h]
                sg.save(doc, d.save(), man)
        emit(cyc, v, 'cycles100')
        # 3 fuzz chain endpoint (5 seeds, 8 chained saves each, tracked manifests), 5 unicode / long path name
        for seed in range(5):
            fz = os.path.join(out, 'fuzz%d_%s.dwg' % (seed, v)); open(fz, 'wb').write(open(base, 'rb').read())
            rng = random.Random(seed * 100 + int(v))
            with sg.open_doc(fz, None, cfg) as doc:
                for i in range(8):
                    d = dwgdoc.Doc(doc.buf); es = list(d.entities('*Model_Space')); man = {'modified': [], 'added': [], 'deleted': []}
                    for _ in range(rng.randint(1, 3)):
                        op = rng.choice(['move', 'props', 'copy', 'erase', 'line', 'circle', 'text'])
                        if op == 'line': man['added'].append(d.add_line((0, 0), (rng.random() * 9, 3)))
                        elif op == 'circle': man['added'].append(d.add_circle((1, 1), 1 + rng.random()))
                        elif op == 'text': man['added'].append(d.add_text((0, 0), 'fz%d' % rng.randint(0, 99), 2.5))
                        else:
                            h = rng.choice(es)
                            if h in man['deleted'] or h in man['added'] or h in man['modified']: continue
                            try:
                                if op == 'move': d.transform(h, X.Transform.translate(rng.random(), 1)); man['modified'].append(h)
                                elif op == 'props': d.set_props(h, color=rng.randint(1, 200)); man['modified'].append(h)
                                elif op == 'copy': man['added'].append(d.copy_entity(h, X.Transform.translate(5, 5)))
                                elif op == 'erase': d.erase(h); es.remove(h); man['deleted'].append(h)
                            except (NotImplementedError, KeyError): d = dwgdoc.Doc(doc.buf); man = {'modified': [], 'added': [], 'deleted': []}
                    sg.save(doc, d.save(), man)
            emit(fz, v, 'fuzz%d' % seed)
        with sg.open_doc(base, None, cfg) as doc:
            ud = os.path.join(out, 'Gebäude Süd 設計 ' + 'x' * 60); os.makedirs(ud, exist_ok=True)
            p = os.path.join(ud, 'Grundriß 平面図 (v2)_%s.dwg' % v); sg.save_as(doc, doc.buf, p, {}, overwrite=True); emit(p, v, 'unicode_path')
    with open(os.path.join(out, 'ledger.tsv'), 'w') as f:
        f.write('sha8\tversion\trow\tvm_result\tdate\n')
        for r in rows: f.write('\t'.join(r) + '\n')
    return rows


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    run(a[0], a[1:] or list(YEARS), '--audit' in sys.argv)
