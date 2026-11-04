"""c7x-rvtread2 76: rvt_integrity.audit (viewer open path) must flag an all-zero Global/ElemTable (valid zero ECC pages, no gzip member)."""
import os, sys, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('name', ['Global/ElemTable', 'Global/History', 'Global/Latest'])
def test_audit_flags_zeroed_global(name):
    cfb = pytest.importorskip('cfb'); R = pytest.importorskip('rvt_integrity')
    assert R.audit(F) == []
    c = cfb.CFB(open(F, 'rb').read()); e = c.streams()[name]; e.data = bytes(len(e.data))
    o = tempfile.mkdtemp() + '/z.rfa'; cfb.write(c, o)
    assert R.audit(o)
