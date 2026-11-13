"""c7x-rvtread2 item 514: move/clone of an ElementGroup is refused (it was accepted on HEAD before: 8 bytes patched, members not moved, no Revit verdict).
Public Autodesk 2024 Snowdon HVAC sample, ElementGroup 1421744. Fails without GROUP_CLASSES in rvt_writer_ops."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/42_Snowdon_Towers_Sample_HVAC.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


@pytest.mark.parametrize('op', [{'op': 'move_element', 'id': 1421744, 'dx': 1.0}, {'op': 'add_element', 'template': 1421744, 'dx': 1.0}])
def test_group_refused(tmp_path, op):
    from savegate import rvt_writer_ops as WO
    out = str(tmp_path / 'o.rvt')
    with pytest.raises(ValueError, match='group / assembly'):
        WO.run(SRC, [op], out)
    assert not os.path.exists(out)
