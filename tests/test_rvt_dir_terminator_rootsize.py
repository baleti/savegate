"""c4x-rvtgap 154/155: in a gated edited output of the 2026 family, a flip of a directory entry's name terminator bytes or of the Root Entry mini-stream size (bytes 120..127) is refused."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no sample')

def test_terminator_and_rootsize_flips_refused(tmp_path):
    import savegate as sg, wledit, cfb
    from savegate.adapters import RvtAdapter
    ed = wledit.Editor(SRC); PN = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Flip')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    good = open(o, 'rb').read(); ss = cfb.CFB(good).ss; base = (1 + int.from_bytes(good[48:52], 'little')) * ss
    def run(bad):
        cur = str(tmp_path / 'cur'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
        doc = sg.open_doc(cur, RvtAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
        try: sg.save(doc, bad, {'modified': ['stream:' + PN, 'el:7']}); return True
        except sg.SaveError: assert open(cur, 'rb').read() == before; return False
    assert run(good)
    offs = [20, 21, 14 + 128, 15 + 128, 120, 122, 127]   # entry 0 terminator, entry 1 terminator, root size low/high bytes
    acc = [i for i in offs if run(good[:base + i] + bytes([good[base + i] ^ 0x10]) + good[base + i + 1:])]
    assert not acc, acc
    free = [i for i, e in enumerate(cfb.CFB(good).entries) if e.type == 0]; assert free
    acc = [b for b in (100, 110, 116, 120, 127) if run(good[:base + free[0] * 128 + b] + bytes([good[base + free[0] * 128 + b] ^ 0x10]) + good[base + free[0] * 128 + b + 1:])]   # queue 152: free directory entry times/start/size
    assert not acc, acc
