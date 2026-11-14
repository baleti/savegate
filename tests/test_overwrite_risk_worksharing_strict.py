"""c7x-rvtread2 687/688: the Worksharing value must be matched strictly. Real wording is exactly 'Not enabled' (in 2 of ~1000 local files directly followed by 'Username:' without a line break). Loose values that are neither must be refused (fail closed); they are ALLOWED by the prefix rule 'startswith(not enabled)' on HEAD, so those cases are xfail until the strict rule (~/demo-state/suggested_savegate_c7x_worksharing_strict.diff) is applied."""
import os, sys, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from savegate import adapters
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')

def _patched(value):
    cfb = pytest.importorskip('cfb'); c = cfb.CFB(open(F, 'rb').read()); e = c.streams()['BasicFileInfo']
    a = ('Worksharing: Not enabled').encode('utf-16le'); assert a in e.data
    e.data = e.data.replace(a, ('Worksharing: ' + value).encode('utf-16le'), 1)
    o = tempfile.mkdtemp() + '/w.rfa'; cfb.write(c, o); return open(o, 'rb').read()

pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')

def test_exact_value_allowed():
    assert adapters.RvtAdapter().overwrite_risks(_patched('Not enabled')) == []

@pytest.mark.parametrize('v', ['Central', 'Local', 'Not enabled'])
def test_other_values_refused(v):
    assert adapters.RvtAdapter().overwrite_risks(_patched(v))

@pytest.mark.xfail(reason='prefix rule on HEAD allows these; strict rule pending (c7x 687)', strict=False)
@pytest.mark.parametrize('v', ['not enabled', 'Not enabledX', 'Not enabled (x)', 'Not enabled but central'])
def test_loose_values_refused(v):
    assert adapters.RvtAdapter().overwrite_risks(_patched(v))
