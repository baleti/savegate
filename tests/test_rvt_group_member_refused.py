"""c7x-rvtread2 item 515: members of a group (FamilyInstance.m_groupId set) cannot be moved/deleted/cloned/retyped/rotated alone: the group (member records, ElementGroupType.m_definingGroupInstId)
is not updated by any writer op. On HEAD before the fix all of these were ACCEPTED (source_damage clean) on the public 2024 HVAC sample: member 1421734 of group 1421744, and 1421752 = the defining
instance of group type 1421745 (deleting it leaves m_definingGroupInstId dangling). Fails without _group_guard."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/42_Snowdon_Towers_Sample_HVAC.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
CASES = [{'op': 'move_element', 'id': 1421734, 'dx': 1.0}, {'op': 'delete', 'id': 1421734}, {'op': 'delete', 'id': 1421752}, {'op': 'delete_cascade', 'id': 1421752},
         {'op': 'add_element', 'template': 1421734, 'dx': 2.0}, {'op': 'rotate_instance', 'id': 1421734, 'deg': 15.0}]


@pytest.mark.parametrize('op', CASES, ids=lambda o: '%s_%s' % (o['op'], o.get('id', o.get('template'))))
def test_group_member_refused(tmp_path, op):
    from savegate import rvt_writer_ops as WO
    out = str(tmp_path / 'o.rvt')
    with pytest.raises(ValueError, match='member of group|cannot cascade-delete'):
        WO.run(SRC, [op], out)
    assert not os.path.exists(out)
