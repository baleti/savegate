"""c7x-rvtread2 61: the public Autodesk 2026 sample has nonzero slack after the end of Partitions/69; a no-edit save must work (it was VerifyFailed), while NEW slack must still be refused."""
import os, sys, pytest
from savegate import adapters, core
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')

def test_noedit_save_of_sample_with_source_slack(tmp_path):
    A = adapters.RvtAdapter(); b = open(F, 'rb').read(); p = str(tmp_path / 'in.rfa'); open(p, 'wb').write(b)
    core.save_as(core.open_doc(p, A, journal=False), b, str(tmp_path / 'out.rfa'))
    import cfb; assert cfb.CFB(open(str(tmp_path / 'out.rfa'), 'rb').read()).streams().keys() == cfb.CFB(b).streams().keys()
