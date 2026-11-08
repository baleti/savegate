"""c7x-rvtread2 item 381: an id may be deleted only once per run (delete+delete of one TextNote removed 2 neighbouring records on the writer without the fix). SGPKG = tree patched with c7x-rvtread2-finite-and-delete-once.diff."""
import os, sys, pytest
sys.path.insert(0, os.environ.get('SGPKG', os.path.expanduser('~/src/savegate')))
from savegate import rvt_writer_ops as WO

def _run(tmp_path, ops):
    return WO.run(str(tmp_path / 'missing.rvt'), ops, str(tmp_path / 'o.rvt'))

def test_double_delete_refused(tmp_path):
    with pytest.raises(ValueError, match='twice'):
        _run(tmp_path, [{'op': 'delete', 'id': 916133}, {'op': 'delete', 'id': 916133}])

def test_move_after_delete_refused(tmp_path):
    with pytest.raises(ValueError, match='deleted earlier'):
        _run(tmp_path, [{'op': 'delete', 'id': 916133}, {'op': 'move_element', 'id': 916133, 'dx': 1.0}])

@pytest.mark.parametrize('a,b', [({'op': 'move_element', 'id': 5, 'dx': 1.0}, {'op': 'move_element', 'id': 5, 'dx': 2.0}),
                                 ({'op': 'move_element', 'id': 5, 'dx': 1.0}, {'op': 'rotate_instance', 'id': 5, 'deg': 10.0}),
                                 ({'op': 'resize_wall', 'id': 5, 'height': 9.0}, {'op': 'move_element', 'id': 5, 'dy': 1.0})])
def test_two_modifications_of_one_element_refused(a, b, tmp_path):
    with pytest.raises(ValueError, match='modified twice'):
        _run(tmp_path, [a, b])

def test_modifications_of_different_elements_pass_the_check(tmp_path):
    with pytest.raises(Exception) as ei:        # the source does not exist: any error EXCEPT the 'modified twice' refusal
        _run(tmp_path, [{'op': 'move_element', 'id': 5, 'dx': 1.0}, {'op': 'move_element', 'id': 6, 'dx': 2.0}])
    assert 'modified twice' not in str(ei.value)
