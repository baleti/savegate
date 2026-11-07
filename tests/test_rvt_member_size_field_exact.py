"""c5x-rvtread2 item 123: a partition member whose u32 size field (at member start - 16) is off by one, or doubled, still inflated inside the slack and passed source_damage; the reader and the gate
then carried the wrong field into the saved file. In every real file measured (2011-2026 except the 2011 Nanjing layout) size-8 equals the real member length, so a member that deviates from the rest
of its stream is damage. Public 2024 family."""
import os, sys, struct, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
from savegate import adapters
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')


def _variant(f):
    import cfb, rvtw
    c = cfb.CFB(open(F, 'rb').read()); name = [n for n in c.streams() if n.startswith('Partitions/')][0]; e = c.streams()[name]
    st = rvtw.Stream(e.data); P = bytearray(st.payload); i = P.find(b'\x1f\x8b\x08\x00'); v = struct.unpack_from('<I', P, i - 16)[0]
    struct.pack_into('<I', P, i - 16, f(v)); e.data = st.build(bytes(P)); o = tempfile.mkdtemp() + '/v.rfa'; cfb.write(c, o); return open(o, 'rb').read()


def test_intact_is_clean():
    assert adapters.RvtAdapter().source_damage(_variant(lambda v: v)) == []


@pytest.mark.parametrize('f', [lambda v: v + 1, lambda v: v * 2, lambda v: v - 1], ids=['plus1', 'double', 'minus1'])
def test_wrong_member_size_field_is_reported(f):
    assert adapters.RvtAdapter().source_damage(_variant(f))
