"""c4x-rvtgap 186: ONE RvtAdapter instance reused for several saves (a host app keeps it) must not carry state from a previous file or a refused save: refused / accepted / refused again."""
import os, sys, shutil, json, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
SRC26 = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
pytestmark = pytest.mark.skipif(not (os.path.exists(SRC) and os.path.exists(SRC26)), reason='no public samples')

def _edit(src, edits, out):
    import wledit
    ed = wledit.Editor(src); ed.set_strings(edits); ed.save(out); return open(out, 'rb').read()

def _second(src):
    import wledit
    b = wledit.Editor(src)
    for e in sorted(b.m.ids):
        if e == 7: continue
        for line in b.trace(e)[3]:
            if line[1].endswith('m_name'): return (e, line[1])

def _doc(a, src, tmp_path, name):
    import savegate as sg
    cur = str(tmp_path / name); shutil.copy(src, cur)
    return cur, sg.open_doc(cur, a, sg.Config(allow_overwrite=True, require_gate=False))

def test_refused_accepted_refused_with_one_adapter_across_two_years(tmp_path):
    import savegate as sg
    from savegate import adapters
    a = adapters.RvtAdapter(); a.elements_fn = adapters._default_rvt_elements()
    for src in (SRC, SRC26):
        sec = _second(src)
        if not sec: pytest.skip('no second named element')
        bad = _edit(src, [(7, 'FillPattern.m_name', 'A'), (sec[0], sec[1], 'B')], str(tmp_path / 'bad.rfa'))
        good = _edit(src, [(7, 'FillPattern.m_name', 'Reuse OK')], str(tmp_path / 'good.rfa'))
        part = [k for k in ('stream:Partitions/67', 'stream:Partitions/66') ]
        cur, doc = _doc(a, src, tmp_path, 'c.rfa'); before = open(cur, 'rb').read()
        with pytest.raises(sg.SaveError): sg.save(doc, bad, {'modified': ['stream:Partitions/67', 'el:7']})
        assert open(cur, 'rb').read() == before
        cur, doc = _doc(a, src, tmp_path, 'c2.rfa')
        assert sg.save(doc, good, {'modified': ['stream:Partitions/67', 'el:7']}).ok
        cur, doc = _doc(a, src, tmp_path, 'c3.rfa'); before = open(cur, 'rb').read()
        with pytest.raises(sg.SaveError): sg.save(doc, bad, {'modified': ['stream:Partitions/67', 'el:7']})
        assert open(cur, 'rb').read() == before

def test_exception_while_hashing_the_output_does_not_poison_the_next_save(tmp_path):
    import savegate as sg
    from savegate import adapters
    a = adapters.RvtAdapter(); a.elements_fn = adapters._default_rvt_elements()
    sec = _second(SRC)
    if not sec: pytest.skip('no second named element')
    bad = _edit(SRC, [(7, 'FillPattern.m_name', 'A'), (sec[0], sec[1], 'B')], str(tmp_path / 'bad.rfa'))
    good = _edit(SRC, [(7, 'FillPattern.m_name', 'Reuse OK')], str(tmp_path / 'good.rfa'))
    orig = a._member_hashes; n = {'c': 0}
    def flaky(c):
        n['c'] += 1
        if n['c'] == 2: raise RuntimeError('simulated failure while hashing the output')
        return orig(c)
    a._member_hashes = flaky
    cur, doc = _doc(a, SRC, tmp_path, 'c.rfa'); before = open(cur, 'rb').read()
    with pytest.raises(Exception): sg.save(doc, good, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before
    a._member_hashes = orig
    cur, doc = _doc(a, SRC, tmp_path, 'c2.rfa')
    assert sg.save(doc, good, {'modified': ['stream:Partitions/67', 'el:7']}).ok
    cur, doc = _doc(a, SRC, tmp_path, 'c3.rfa'); before = open(cur, 'rb').read()
    with pytest.raises(sg.SaveError): sg.save(doc, bad, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before
