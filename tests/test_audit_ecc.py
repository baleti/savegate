"""c7x-rvtread2 84: rvt_integrity.audit must include the page ECC check (bytes appended to a partition have no valid ECC)."""
import os, sys, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('junk', [b'\x5a' * 16, bytes(16), b'\xa5' * 4096])
def test_audit_flags_ecc_bad_page(junk):
    cfb = pytest.importorskip('cfb'); R = pytest.importorskip('rvt_integrity')
    assert R.audit(F) == []
    c = cfb.CFB(open(F, 'rb').read()); n = sorted(x for x in c.streams() if x.startswith('Partitions/'))[-1]
    c.streams()[n].data += junk; o = tempfile.mkdtemp() + '/z.rfa'; cfb.write(c, o)
    assert any(x[0] == 'ecc' for x in R.audit(o))
