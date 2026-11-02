import os, shutil, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
GEN1 = os.path.expanduser('~/demo-state/oracle-files/c4x_2024_family_edit_gen1.rfa')
pytestmark = pytest.mark.skipif(not (os.path.exists(SRC) and os.path.exists(GEN1) and os.path.isdir(os.path.expanduser('~/rvt-research/write-lab'))), reason='needs the public 2024 family sample and the writer lab')
from savegate import rvt_verify as V


def test_intended_edit_passes_and_unexpected_or_wrong_value_fails():
    assert V.verify_declared(SRC, GEN1, 0, {'SymbolInfo.m_name': 'LinearXY'})
    with pytest.raises(ValueError): V.verify_declared(SRC, GEN1, 0, {'SymbolInfo.m_name': 'Other'})
    with pytest.raises(ValueError): V.verify_declared(SRC, SRC, 0, {'SymbolInfo.m_name': 'LinearXY'})


def test_flip_inside_the_declared_record_is_caught(tmp_path):
    import cfb, rvtw, wlpart
    c = cfb.CFB(open(GEN1, 'rb').read()); pn = 'Partitions/67'; st = rvtw.Stream(c.streams()[pn].data); pt = wlpart.Partition(st)
    import wlrec
    b = wlrec.Model(GEN1); _, i, _, log, q = list(b.find(0))[0]
    offs = 0; hit = None
    for k, m in enumerate(pt.mem):
        if offs <= i + 20 < offs + len(m['raw']): hit = (k, i + 20 - offs); break
        offs += len(m['raw'])
    k, pos = hit; raw = bytearray(pt.mem[k]['raw']); raw[pos] ^= 0x01; pt.mem[k]['raw'] = raw; pt.mem[k]['dirty'] = True
    P2 = pt.rebuild(); pad = (-len(P2)) % rvtw.PAGE_PAYLOAD if len(P2) > st.full * rvtw.PAGE_PAYLOAD + getattr(st, 'cap_last', 0) else 0
    c.streams()[pn].data = st.build(P2 + b'\0' * pad, keep_spare=False); o = str(tmp_path / 'flip.rfa'); cfb.write(c, o)
    try: V.verify_declared(SRC, o, 0, {'SymbolInfo.m_name': 'LinearXY'})
    except ValueError: return
    except Exception: return      # undecodable after the flip is also a refusal
    pytest.fail('a bit flip inside the declared record passed verify_declared')
