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

def test_element_view_failure_on_the_output_does_not_poison_the_next_save(tmp_path):
    import savegate as sg
    from savegate import adapters
    a = adapters.RvtAdapter(); real = adapters._default_rvt_elements(); n = {'c': 0}
    def flaky(buf):
        n['c'] += 1
        if n['c'] == 2: raise RuntimeError('simulated element view failure on the output')
        return real(buf)
    a.elements_fn = flaky
    sec = _second(SRC)
    if not sec: pytest.skip('no second named element')
    bad = _edit(SRC, [(7, 'FillPattern.m_name', 'A'), (sec[0], sec[1], 'B')], str(tmp_path / 'bad.rfa'))
    good = _edit(SRC, [(7, 'FillPattern.m_name', 'Reuse OK')], str(tmp_path / 'good.rfa'))
    cur, doc = _doc(a, SRC, tmp_path, 'c.rfa'); before = open(cur, 'rb').read()
    with pytest.raises(sg.SaveError): sg.save(doc, good, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before
    a.elements_fn = real
    cur, doc = _doc(a, SRC, tmp_path, 'c2.rfa')
    assert sg.save(doc, good, {'modified': ['stream:Partitions/67', 'el:7']}).ok
    cur, doc = _doc(a, SRC, tmp_path, 'c3.rfa'); before = open(cur, 'rb').read()
    with pytest.raises(sg.SaveError): sg.save(doc, bad, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before

def test_reference_scan_that_cannot_run_refuses_and_the_next_scan_still_works(monkeypatch):
    import rvt_xcache
    from savegate import adapters
    a = adapters.RvtAdapter(); a._src_buf = open(SRC26, 'rb').read()
    real = rvt_xcache.get_x_ro
    def boom(p): raise RuntimeError('simulated reader failure')
    monkeypatch.setattr(rvt_xcache, 'get_x_ro', boom)
    r = a._delete_reference_checks({'deleted': ['el:11']})
    assert r and r[0][0] == 'delete_references_unchecked', r
    monkeypatch.setattr(rvt_xcache, 'get_x_ro', real)
    r2 = a._delete_reference_checks({'deleted': ['el:11']})
    assert r2 and r2[0][0] in ('dangling_after_delete',), r2      # el:11 is referenced in the family (c2x-rvtgap 17)

@pytest.mark.parametrize('nth', [1, 2, 3, 4])
def test_no_space_for_temp_copies_leaves_the_original_untouched(tmp_path, monkeypatch, nth):
    """c4x-rvtgap 194: /tmp is a 16 GB tmpfs on remote-host and the gate writes several temp copies of the file; ENOSPC at the n-th temp copy must refuse/abort, never damage the original, and the next save works."""
    import errno, tempfile, savegate as sg
    from savegate import adapters
    good = _edit(SRC, [(7, 'FillPattern.m_name', 'Space OK')], str(tmp_path / 'good.rfa'))
    cur, doc = _doc(None, SRC, tmp_path, 'c.rfa'); before = open(cur, 'rb').read()
    real = tempfile.mkstemp; n = {'c': 0}
    def flaky(*a, **k):
        if k.get('suffix') == '.rvt':
            n['c'] += 1
            if n['c'] == nth: raise OSError(errno.ENOSPC, 'No space left on device')
        return real(*a, **k)
    monkeypatch.setattr(tempfile, 'mkstemp', flaky)
    try: r = sg.save(doc, good, {'modified': ['stream:Partitions/67', 'el:7']}); failed = False
    except (sg.SaveError, OSError): failed = True
    after = open(cur, 'rb').read()
    if n['c'] < nth: pytest.skip('this save makes only %d temp copies' % n['c'])
    assert failed, 'ENOSPC at temp copy %d was swallowed and the save went on' % nth
    if failed: assert after == before
    monkeypatch.setattr(tempfile, 'mkstemp', real)
    cur2, doc2 = _doc(None, SRC, tmp_path, 'c2.rfa')
    assert sg.save(doc2, good, {'modified': ['stream:Partitions/67', 'el:7']}).ok
