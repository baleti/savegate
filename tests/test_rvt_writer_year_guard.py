"""c7x-rvtread2 561: the raw writer API must refuse non-writable Revit years (2020 move used to write an unverified file)."""
import os, sys, glob, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
C = os.path.expanduser('~/rvt-research/corpus/')
S = sorted(glob.glob(C + '2020/*.rvt'))
pytestmark = pytest.mark.skipif(not S, reason='no Autodesk 2020 sample')

def _target(src):
    import rvt_xcache
    return int([k[0] for k in rvt_xcache.get_x_ro(src)['recs'] if k[1] in ('FamilyInstance', 'Wall', 'SWall')][0])

def test_old_year_refused_without_output(tmp_path):
    from savegate import rvt_writer_ops as WO
    from savegate.core import UnsupportedVersion
    out = str(tmp_path / 'o.rvt'); t = _target(S[0])
    with pytest.raises(UnsupportedVersion): WO.run(S[0], [{'op': 'move_element', 'allow_dependents': True, 'id': t, 'dx': 1.0, 'dy': 0.0}], out)
    assert not os.path.exists(out)

def test_lab_flag_still_writes(tmp_path):
    from savegate import rvt_writer_ops as WO
    out = str(tmp_path / 'o.rvt'); t = _target(S[0])
    WO.run(S[0], [{'op': 'move_element', 'allow_dependents': True, 'id': t, 'dx': 1.0, 'dy': 0.0}], out, lab=True)
    assert os.path.getsize(out) > 0
