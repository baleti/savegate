"""c2x-rvtgap: the declared name edit of element 7 goes through the FULL gate (sg.save, in-place, backup) on the writable years (2024, 2026) and the saved file reads back with the new name;
every other public sample year is refused with UnsupportedVersion and the file is untouched."""
import os, sys, glob, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = sorted(glob.glob(os.path.expanduser('~/rvt-research/samples-rfa/*.rfa')))
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no public samples')


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_declared_edit_saves_through_the_full_gate(path, tmp_path):
    import savegate as sg, wledit
    ed = wledit.Editor(path); pn = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'HorizontalZ')])
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(path, cur); before = open(cur, 'rb').read()
    if not any(y in path for y in ('2024', '2026')):      # writable years are 2024 and 2026 only: every other year is refused and the file is never touched
        with pytest.raises(sg.UnsupportedVersion):
            sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
        assert open(cur, 'rb').read() == before
        return
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, new, {'modified': ['stream:' + pn, 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
    assert open(cur, 'rb').read() == new and new != before
    assert wledit.Editor(cur).trace(7)[2]['fields']['m_pFillPattern']['obj']['m_name'] == 'HorizontalZ'
