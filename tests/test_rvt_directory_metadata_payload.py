"""c7x-rvtread2 613/614: a payload that changes only CFB directory metadata (root CLSID, root ctime/mtime, a stream entry ctime, entry state bits) next to a valid declared edit is refused (VerifyFailed meta:dirmeta), original intact. 2024/2026 Autodesk sample families."""
import os, sys, shutil, struct, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
CASES = {'clsid': (0x50, 0), 'root_ctime': (0x64, 0), 'root_mtime': (0x6C, 0), 'entry_ctime': (0x64, 128), 'entry_state': (0x60, 128)}
@pytest.mark.parametrize('k', sorted(CASES))
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_dirmeta(tmp_path, year, k):
    import wledit
    if not os.path.exists(R % year): pytest.skip('no sample')
    t = str(tmp_path / 'a.rfa'); shutil.copy(R % year, t); raw = open(t, 'rb').read()
    ed = wledit.Editor(t); pn = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Dirmeta probe')]); o = str(tmp_path / 'o'); ed.save(o); new = open(o, 'rb').read()
    ss = 1 << struct.unpack_from('<H', new, 0x1E)[0]; dr = (struct.unpack_from('<I', new, 0x30)[0] + 1) * ss
    off, base = CASES[k]; p = dr + base + off; bad = new[:p] + bytes([new[p] ^ 1]) + new[p + 1:]
    man = {'modified': ['stream:' + pn, 'el:7']}
    with pytest.raises(sg.SaveError) as ei: sg.save(sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False)), bad, man)
    assert type(ei.value).__name__ not in ('GateClosed', 'LowMemory')
    assert open(t, 'rb').read() == raw
    sg.save(sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False)), new, man)      # control: the edit alone is accepted
    assert open(t, 'rb').read() == new
