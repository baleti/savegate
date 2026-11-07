"""c5x-rvtread2 item 121: the 2011 Nanjing public sample was reported damaged ('member 47 ... size field 129019 beyond the stream') although its last partition member inflates completely with a valid
CRC/ISIZE and all 50,254 elements decode: in that layout the size field is not the compressed length. A member that inflates fully is intact; a truncated one must still be reported."""
import os, sys, glob, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research')); sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
S = glob.glob(os.path.expanduser('~/rvt-research/samples/2011_1_*.rvt'))
pytestmark = pytest.mark.skipif(not S, reason='no 2011 public sample')


def _tail_member(truncate):
    import cfb, rvt_integrity as R
    from rvtfmt import strip_pages
    st = cfb.CFB(open(S[0], 'rb').read()).streams()
    name = [n for n in st if n.startswith('Partitions/')][0]; d = strip_pages(st[name].data)
    return R, d[:len(d) - truncate] if truncate else d


def test_intact_2011_partition_is_not_damage():
    R, d = _tail_member(0); assert R.partition_member_problems(d) == []


def test_truncated_tail_member_is_still_damage():
    R, d = _tail_member(0); d = d[:6430554 + 10000]      # cut inside member 47 (compressed length ~27.9 KB)
    assert R.partition_member_problems(d)
