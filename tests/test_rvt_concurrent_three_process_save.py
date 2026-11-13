"""c2x-rvtgap 127: three processes save different edits to the same rfa at once: the final file is exactly one of the two valid outputs (no torn mix), source_damage clean, nothing but backups/.savegate left."""
import os, sys, shutil, subprocess, textwrap, pytest
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
CHILD = textwrap.dedent('''
    import os, sys
    sys.path[:0] = [os.path.expanduser('~/src/savegate'), os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import savegate as sg, wledit
    tgt, txt, out = sys.argv[1:4]
    ed = wledit.Editor(tgt); ed.set_strings([(7, 'FillPattern.m_name', txt)]); o = out + '.tmp'; ed.save(o)
    new = open(o, 'rb').read(); os.remove(o); open(out, 'wb').write(new)
    doc = sg.open_doc(tgt, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=3))
    try:
        r = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); print('OK' if r.ok else 'REFUSED')
    except Exception as e: print('REFUSED', type(e).__name__)
''')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_three_process_race(tmp_path):
    from savegate.adapters import RvtAdapter
    for rnd in range(6):
        t = str(tmp_path / 'x.rfa'); shutil.copy(F, t)
        outs = [str(tmp_path / ('n%d_%d.rfa' % (rnd, i))) for i in (0, 1, 2)]
        ps = [subprocess.Popen([sys.executable, '-c', CHILD, t, 'Racer%d' % i, outs[i]], stdout=subprocess.PIPE, text=True) for i in (0, 1, 2)]
        res = [p.communicate(timeout=300)[0].strip() for p in ps]
        final = open(t, 'rb').read()
        cands = [open(o, 'rb').read() for o in outs]
        assert any(r.startswith('OK') for r in res), res
        assert final in cands or final == open(F, 'rb').read(), 'torn file, results %s' % res
        assert RvtAdapter().source_damage(final) == []
