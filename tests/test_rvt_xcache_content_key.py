"""c4x-rvtgap: Python-fallback xcache was keyed by path+size+mtime-second (stale after a same-size edit in the same second) and unpickled unverified."""
import os, sys, shutil, pytest
import savegate  # noqa: first
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
def test_same_size_same_second_edit_changes_key(tmp_path):
    import rvt_xcache
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    f = str(tmp_path / 'a.rfa'); shutil.copy(src, f); st = os.stat(f); k1 = rvt_xcache.key_for(f)
    b = bytearray(open(f, 'rb').read()); b[100000] ^= 1; open(f, 'wb').write(bytes(b)); os.utime(f, (st.st_atime, st.st_mtime))
    assert os.stat(f).st_size == st.st_size and int(os.stat(f).st_mtime) == int(st.st_mtime)
    assert rvt_xcache.key_for(f) != k1
def test_corrupt_entry_rebuilt(tmp_path, monkeypatch):
    import rvt_xcache
    monkeypatch.setattr(rvt_xcache, 'D', str(tmp_path)); monkeypatch.setattr(rvt_xcache, '_F', None)
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    x1 = rvt_xcache.get_x(src); e = [n for n in os.listdir(tmp_path) if n.endswith('.pkl')]; assert len(e) == 1
    open(tmp_path / e[0], 'wb').write(b'junk' * 50)
    x2 = rvt_xcache.get_x(src); assert x2['recs'].keys() == x1['recs'].keys()

def test_rust_reader_not_stale_after_same_size_same_mtime_edit(tmp_path):
    sys.path.insert(0, os.path.expanduser('~/src/rvt-core/python'))
    import rvt_fast as F, wledit
    if not F.on(): pytest.skip('rust reader off')
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    f = str(tmp_path / 'a.rfa'); g = str(tmp_path / 'b.rfa')
    wledit.Editor(src).__class__  # noqa
    for dst, name in ((f, 'AAAA'), (g, 'BBBB')):
        ed = wledit.Editor(src); ed.set_strings([(7, 'FillPattern.m_name', name)]); ed.save(dst)
    st = os.stat(f); x1 = F.extract(f, want_all=True)
    open(f, 'wb').write(open(g, 'rb').read()); os.utime(f, (st.st_atime, st.st_mtime))
    assert os.stat(f).st_size == st.st_size and int(os.stat(f).st_mtime) == int(st.st_mtime)
    x2 = F.extract(f, want_all=True)
    assert any(x1['recs'][k] != x2['recs'].get(k) for k in x1['recs']), 'stale cache served after in-place edit'
