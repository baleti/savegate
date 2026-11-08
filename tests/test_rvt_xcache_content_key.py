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
