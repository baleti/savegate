"""c5x-rvtgap 165: the target is changed by someone else AFTER open_doc, keeping size and mtime (utime restored). The save must notice (content hash) and refuse; the other writer's bytes must survive."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('where', ['first', 'middle', 'last'])
def test_same_size_mtime(tmp_path, where):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t)
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o); good = open(o, 'rb').read()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    st = os.stat(t); b = bytearray(t.read_bytes()); i = {'first': 0, 'middle': len(b) // 2, 'last': len(b) - 1}[where]; b[i] ^= 0x01
    with open(t, 'r+b') as f: f.write(bytes(b))
    os.utime(t, ns=(st.st_atime_ns, st.st_mtime_ns)); assert os.stat(t).st_size == st.st_size and os.stat(t).st_mtime_ns == st.st_mtime_ns
    other = t.read_bytes()
    try: ok = sg.save(doc, good, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    print(where, 'ACCEPTED' if ok else 'refused', type(err).__name__, str(err)[:70])
    assert not ok and t.read_bytes() == other
