"""c7x-rvtread2 item 468/469: ids that hit a duplicate/phantom key (id 1 in Snowdon Structural 2026) must be refused with ValueError for every op (before: raw struct.error / KeyError)."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
from savegate import rvt_writer_ops as WO
S = os.path.expanduser('~/rvt-research/corpus/2026/55_Snowdon_Towers_Sample_Structural.rvt')
@pytest.mark.parametrize('op', [{'op': 'move_element', 'id': 1, 'dx': 1.0}, {'op': 'delete', 'id': 1}, {'op': 'set_instance_type', 'id': 1, 'symbol': 901053}, {'op': 'add_element', 'template': 1, 'dx': 1.0}])
def test_dup_id_is_valueerror(op, tmp_path):
    with pytest.raises(ValueError):
        WO.run(S, [op], str(tmp_path / 'o.rvt'))
