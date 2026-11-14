"""c5x-rvtgap 143: an op that targets an element id deleted earlier (same op list, or in the saved output of a previous save) is refused by the writer; nothing is written."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/55_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk 2026 sample')
FOLLOW = [{'op': 'move_textnote', 'id': 916133, 'dx': 1.0, 'dy': 0.5}, {'op': 'delete', 'id': 916133},
          {'op': 'move_element', 'id': 916133, 'dx': 1.0}, {'op': 'rotate_instance', 'id': 916133, 'deg': 5.0}]

def test_same_list(tmp_path):
    from savegate import rvt_writer_ops as WO
    for f in FOLLOW:
        o = str(tmp_path / 'o.rvt')
        with pytest.raises(ValueError):
            WO.run(SRC, [{'op': 'delete', 'id': 916133}, dict(f, **({'allow_dependents': True} if f['op'] in ('move_element', 'rotate_instance') else {}))], o)
        assert not os.path.exists(o)

def test_second_save(tmp_path):
    from savegate import rvt_writer_ops as WO
    o1 = str(tmp_path / 'o1.rvt'); WO.run(SRC, [{'op': 'delete', 'id': 916133}], o1)
    for f in FOLLOW:
        if f['op'] == 'delete': pass
        o2 = str(tmp_path / 'o2.rvt')
        with pytest.raises(ValueError):
            WO.run(o1, [dict(f, **({'allow_dependents': True} if f['op'] in ('move_element', 'rotate_instance') else {}))], o2)
        assert not os.path.exists(o2)
