"""c5x-rvtgap RVT-EDIT rung 2: DELETE an element nothing else references (Autodesk Snowdon Towers Structural 2024: TextNote 916133, loose FamilyInstance 664857). The editor removes the
record (its ElemTable row stays without a framed record, like the 8 such rows already in the pristine file); the gate accepts it in strict mode (declared deleted, no derived_ok); the
element is gone from the output, every other record decodes as before. A referenced element (level 32567) stays refused. Local gate-level checks; Revit-VM verdict separate."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


def _try(tmp_path, el):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); pn = ed.trace(el)[0]; ed.delete(el); o = str(tmp_path / 'o.rvt'); ed.save(o); nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'modified': ['stream:' + pn], 'deleted': ['el:%d' % el]}); ok = True
    except sg.SaveError as e:
        if type(e).__name__ == 'LowMemory': pytest.skip('gate memory preflight refused on this host (needs ~2 GB free for a 26 MB file); rerun with free memory or SAVEGATE_MEM_FACTOR=0 under a 3 GB cap')
        ok = False
    return ok, cur, before, nb


@pytest.mark.parametrize('el', [916133, 664857])
def test_unreferenced_element_delete_accepted_and_gone(tmp_path, el):
    import wledit
    ok, cur, before, nb = _try(tmp_path, el)
    assert ok and open(cur, 'rb').read() == nb
    with pytest.raises(IndexError): wledit.Editor(cur).trace(el)          # no framed record any more


def test_referenced_element_delete_refused(tmp_path):
    ok, cur, before, nb = _try(tmp_path, 32567)
    assert not ok and open(cur, 'rb').read() == before
