"""c4x-rvtgap: file changed behind our back between open_doc and save: same-size byte change with the mtime restored, truncation, deletion, replacement by another valid file: all refused (Conflict/SaveError), nothing written by us, no resurrected file."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
F2 = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def _setup(tmp_path):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f)
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Conflict probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    return f, new, sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
MAN = {'modified': ['stream:Partitions/67', 'el:7']}
def test_same_size_change_mtime_restored(tmp_path):
    f, new, doc = _setup(tmp_path); st = os.stat(f); b = bytearray(open(f, 'rb').read()); b[1000] ^= 1; open(f, 'wb').write(bytes(b)); os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(sg.SaveError): sg.save(doc, new, MAN)
    assert bytes(open(f, 'rb').read()) == bytes(b)
def test_truncated(tmp_path):
    f, new, doc = _setup(tmp_path); b = open(f, 'rb').read()[:-4096]; open(f, 'wb').write(b)
    with pytest.raises(sg.SaveError): sg.save(doc, new, MAN)
    assert open(f, 'rb').read() == b
def test_deleted_is_not_resurrected(tmp_path):
    f, new, doc = _setup(tmp_path); os.remove(f)
    with pytest.raises(Exception): sg.save(doc, new, MAN)
    assert not os.path.exists(f)
@pytest.mark.skipif(not os.path.exists(F2), reason='no sample')
def test_replaced_by_other_valid_file(tmp_path):
    f, new, doc = _setup(tmp_path); shutil.copy(F2, f); other = open(f, 'rb').read()
    with pytest.raises(sg.SaveError): sg.save(doc, new, MAN)
    assert open(f, 'rb').read() == other
