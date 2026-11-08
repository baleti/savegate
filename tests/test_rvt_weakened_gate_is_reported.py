"""c4x-rvtgap 185: a save that ran with a weaker gate (no element view, id check switched off) says so in SaveResult.report['weakened']."""
import os, glob, shutil, pytest
from savegate import adapters, core
FAM = glob.glob(os.path.expanduser('~/rvt-research/**/racbasicsamplefamily-2024.rfa'), recursive=True)
pytestmark = pytest.mark.skipif(not FAM, reason='no Autodesk sample family')

def _save(tmp_path):
    p = str(tmp_path / 'in.rfa'); shutil.copy(FAM[0], p); b = open(p, 'rb').read()
    return core.save_as(core.open_doc(p, adapters.RvtAdapter(), journal=False), b, str(tmp_path / 'out.rfa'))

def test_no_element_view_and_idcheck_off_are_reported(tmp_path, monkeypatch):
    monkeypatch.setenv('SAVEGATE_RVT_IDCHECK', '0')
    w = _save(tmp_path).report.get('weakened', [])
    assert any('IDCHECK' in x for x in w) and any('element view' in x for x in w), w

def test_full_gate_reports_nothing(tmp_path):
    p = str(tmp_path / 'in.rfa'); shutil.copy(FAM[0], p); b = open(p, 'rb').read()
    a = adapters.RvtAdapter(); a.elements_fn = adapters._default_rvt_elements()
    assert 'weakened' not in core.save_as(core.open_doc(p, a, journal=False), b, str(tmp_path / 'out.rfa')).report
