"""c7x-rvtread2 94: RvtAdapter.overwrite_risks refuses in-place overwrite of workshared (Central/Local) models; public 2024 sample with the BasicFileInfo field patched."""
import os, sys, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from savegate import adapters
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
OLD = 'Not enabled'

def _patched(value):
    cfb = pytest.importorskip('cfb'); c = cfb.CFB(open(F, 'rb').read()); e = c.streams()['BasicFileInfo']
    a = 'Worksharing: ' + OLD; b = 'Worksharing: ' + value.ljust(len(OLD))
    assert a.encode('utf-16le') in e.data
    e.data = e.data.replace(a.encode('utf-16le'), b.encode('utf-16le'), 1)
    o = tempfile.mkdtemp() + '/w.rfa'; cfb.write(c, o); return open(o, 'rb').read()

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
def test_not_enabled_allowed():
    assert adapters.RvtAdapter().overwrite_risks(open(F, 'rb').read()) == []

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('v', ['Central', 'Local'])
def test_workshared_refused(v):
    assert adapters.RvtAdapter().overwrite_risks(_patched(v))


@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('v', ['', 'Blank'])
def test_missing_or_empty_field_fails_closed(v):
    """c5x-rvtgap 67: an absent or empty Worksharing field must NOT read as 'not workshared'."""
    cfb = pytest.importorskip('cfb'); c = cfb.CFB(open(F, 'rb').read()); e = c.streams()['BasicFileInfo']
    a = 'Worksharing: ' + OLD
    if v == '': e.data = e.data.replace('Worksharing:'.encode('utf-16le'), 'Workshar1ng:'.encode('utf-16le'), 1)
    else: e.data = e.data.replace(a.encode('utf-16le'), ('Worksharing: ' + ' ' * len(OLD)).encode('utf-16le'), 1)
    o = tempfile.mkdtemp() + '/w.rfa'; cfb.write(c, o)
    assert adapters.RvtAdapter().overwrite_risks(open(o, 'rb').read())
