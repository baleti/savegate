"""c5x-rvtread2 item 184: the gate's element view must not leave the reader's per-file record cache (rvt_fast._SHARED) alive after each call (~490 MB on a 22 MB project)."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research')); sys.path.insert(0, os.path.expanduser('~/src/rvt-core/python'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_shared_cache_released_after_element_view():
    from savegate import adapters
    fn = adapters._default_rvt_elements()
    if fn is None: pytest.skip('no reader')
    els = fn(open(F, 'rb').read()); assert els
    m = sys.modules.get('rvt_fast')
    if m is None or not isinstance(getattr(m, '_SHARED', None), dict): pytest.skip('rvt_fast not in use')
    assert not m._SHARED
