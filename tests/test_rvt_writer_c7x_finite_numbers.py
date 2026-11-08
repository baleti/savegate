"""c7x-rvtread2 item 376: writer ops must refuse NaN/inf/absurd numbers before touching the file. SGPKG = savegate tree (patched with c7x-rvtread2-finite-numbers.diff). Without the patch NaN was packed into the wall record."""
import os, sys, pytest
sys.path.insert(0, os.environ.get('SGPKG', os.path.expanduser('~/src/savegate')))
from savegate import rvt_writer_ops as WO

@pytest.mark.parametrize('key,val', [('dx', float('nan')), ('dy', float('inf')), ('dz', -float('inf')), ('dx', 1e9), ('dx', 1e300)])
def test_bad_numbers_refused(key, val, tmp_path):
    with pytest.raises(ValueError, match='finite'):
        WO.run(str(tmp_path / 'missing.rvt'), [{'op': 'move_element', 'id': 1, key: val}], str(tmp_path / 'o.rvt'))

@pytest.mark.parametrize('op', [{'op': 'rotate_instance', 'id': 1, 'deg': float('nan')}, {'op': 'resize_wall', 'id': 1, 'height': float('inf')}, {'op': 'add_textnote', 'template': 1, 'x': float('nan'), 'y': 0, 'text': 'a'}])
def test_other_ops(op, tmp_path):
    with pytest.raises(ValueError, match='finite'):
        WO.run(str(tmp_path / 'missing.rvt'), [op], str(tmp_path / 'o.rvt'))

@pytest.mark.parametrize('op', [{'op': 'move_element', 'id': 585072, 'dx': '1e3'}, {'op': 'move_element', 'id': 585072, 'dx': True}, {'op': 'move_element', 'id': '585072', 'dx': 1.0},
                                {'op': 'move_element', 'id': 585072.7, 'dx': 1.0}, {'op': 'move_element', 'id': 0, 'dx': 1.0}, {'op': 'move_element', 'id': -5, 'dx': 1.0}, {'id': 1, 'dx': 1.0}])
def test_loose_types_refused(op, tmp_path):
    with pytest.raises(ValueError):
        WO.run(str(tmp_path / 'missing.rvt'), [op], str(tmp_path / 'o.rvt'))
