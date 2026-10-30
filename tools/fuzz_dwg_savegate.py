"""DWG chained-edit fuzz through savegate (offline verify, no AutoCAD): per version and seed, STEPS chained saves of 1-3 random ops
(move/props/copy/erase on ANY entity kind incl. dimensions, inserts, polylines, plus added line/circle/text) with exact tracked manifests.
Counts: saves, false alarms (VerifyFailed with an exact manifest), and for every 5th save a lying manifest (declared edit omitted)
that MUST be refused. usage: fuzz_dwg_savegate.py SEEDS STEPS [versions...]"""
import os, sys, random, tempfile, collections
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..'), os.path.expanduser('~/dwg-write')]
import savegate as sg, dwgdoc, dwgxform as X, wtest
seeds, steps = int(sys.argv[1]), int(sys.argv[2]); vers = sys.argv[3:] or ['2000', '2004', '2010', '2013', '2018']
cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=1)
C = collections.Counter(); bad = []
for v in vers:
    tpl = open(os.path.expanduser('~/dwg-write/templates/blank_%s.dwg' % v), 'rb').read()
    d0 = dwgdoc.Doc(tpl)
    for f in (wtest.basic, wtest.blocks, wtest.more, wtest.dims):
        try: f(d0)
        except Exception: pass
    seedbuf = d0.save()
    for seed in range(seeds):
        rng = random.Random(seed * 1009 + int(v)); w = tempfile.mkdtemp(prefix='sgf'); os.environ['SAVEGATE_JOURNAL'] = w + '/j'
        p = os.path.join(w, 'f.dwg'); open(p, 'wb').write(seedbuf)
        with sg.open_doc(p, None, cfg) as doc:
            for i in range(steps):
                ops_log = []; d = dwgdoc.Doc(doc.buf); es = list(d.entities('*Model_Space')); man = {'modified': [], 'added': [], 'deleted': []}
                for _ in range(rng.randint(1, 3)):
                    op = rng.choice(['move', 'props', 'copy', 'erase', 'line', 'circle', 'text'])
                    ops_log.append(op)
                    try:
                        if op == 'line': man['added'].append(d.add_line((0, 0), (rng.random() * 9, 3)))
                        elif op == 'circle': man['added'].append(d.add_circle((1, 1), 1 + rng.random()))
                        elif op == 'text': man['added'].append(d.add_text((0, 0), 'fz%d' % rng.randint(0, 99), 2.5))
                        else:
                            h = rng.choice(es)
                            if h in man['deleted'] or h in man['added'] or h in man['modified']: continue
                            if op == 'move': d.transform(h, X.Transform.translate(rng.random(), 1)); man['modified'].append(h)
                            elif op == 'props': d.set_props(h, color=rng.randint(1, 200)); man['modified'].append(h)
                            elif op == 'copy': man['added'].append(d.copy_entity(h, X.Transform.translate(5, 5)))
                            else: d.erase(h); es.remove(h); man['deleted'].append(h)
                    except (NotImplementedError, KeyError): C['unsupported_op'] += 1; d = dwgdoc.Doc(doc.buf); man = {'modified': [], 'added': [], 'deleted': []}; break
                if not any(man.values()): continue
                out = d.save()
                if i % 5 == 4 and man['modified']:      # lying manifest must be refused (the doc is not advanced)
                    lie = {'modified': man['modified'][1:], 'added': man['added'], 'deleted': man['deleted']}
                    try: sg.save_as(doc, out, os.path.join(w, 'lie.dwg'), lie, overwrite=True); C['LIE_ACCEPTED'] += 1; bad.append((v, seed, i, 'lie accepted'))
                    except sg.VerifyFailed: C['lie_refused'] += 1
                try: sg.save(doc, out, man); C['saves_ok'] += 1
                except Exception as e: C['FALSE_ALARM'] += 1; bad.append((v, seed, i, ops_log, [d.otype(h) for h in man['added']], type(e).__name__, str(e)[:100], getattr(e, 'report', None) and e.report.get('unexpected'))); break
    print(v, dict(C), flush=True)
for b in bad[:20]: print(b)
print('TOTAL', dict(C)); sys.exit(1 if bad else 0)
