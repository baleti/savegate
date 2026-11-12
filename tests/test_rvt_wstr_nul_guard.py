"""c4x-rvtgap 354: Editor refuses a string edit on a field whose current value carries NUL (misparsed record, 2026 Precast CHS template el 0 AnalyticalModel.m_comments);
before the guard the write damaged neighbouring records (gate: 'lost el:39271'). A real name field (el 12 LinePattern.m_name) is still editable."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/75_Precast_Detailing-DefaultMetricCHS.rte')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')

def test_misparsed_field_refused_and_real_name_still_editable(tmp_path):
    import wledit
    ed = wledit.Editor(SRC)
    with pytest.raises(ValueError): ed.set_strings([(0, 'AnalyticalModel.m_comments', 'x')])
    ed2 = wledit.Editor(SRC); ed2.set_strings([(12, 'LinePattern.m_name', '划线Z')]); ed2.save(str(tmp_path / 'o.rte'))
