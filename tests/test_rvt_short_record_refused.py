"""c4x-rvtgap 433: wledit.modify must refuse short-form records (no real witness for their checksum layout)."""
import os, sys, pytest
for p in ('~/rvt-research', '~/rvt-research/write-lab'): sys.path.insert(0, os.path.expanduser(p))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')

def test_short_record_modify_refused():
    wledit = pytest.importorskip('wledit')
    if not os.path.exists(SRC): pytest.skip('no sample')
    ed = wledit.Editor(SRC)
    with pytest.raises(ValueError, match='short-form'):
        ed.modify(0, [], which=1)
