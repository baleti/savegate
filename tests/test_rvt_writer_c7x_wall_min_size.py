"""c7x-rvtread2 item 389: resize_wall refuses zero/negative length and height. SGPKG = tree with c7x-rvtread2-finite-and-delete-once.diff (unguarded walls need the min-size check, so this uses wall 935922 which has dependents: on the full stack the dependents guard may fire first, either message is a refusal; on HEAD both are ACCEPTED)."""
import os, sys, pytest
sys.path.insert(0, os.environ.get('SGPKG', os.path.expanduser('~/src/savegate')))
S = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(S), reason='public Autodesk sample missing')

@pytest.mark.parametrize('op', [{'length_delta': -11.3}, {'length_delta': -11.26}, {'height': 0.0}, {'height': -3.0}])
def test_degenerate_wall_refused(op, tmp_path):
    from savegate import rvt_writer_ops as WO
    with pytest.raises(ValueError):
        WO.run(S, [dict(op='resize_wall', id=935922, **op)], str(tmp_path / 'o.rvt'))
