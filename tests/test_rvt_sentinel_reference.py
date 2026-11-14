"""c5x-rvtgap 186: Element reference fields of el:7 (Autodesk 2024 rfa) set to the invalid sentinel (2^64-1) and to 0, including m_famId which holds 17 in the source, through writer + gate. Records the verdicts (printed); raw exception or damaged original fails; ACCEPTED must read back."""
import os, sys, struct, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('fld', ['m_assocLevelId', 'm_ownerDBViewId', 'm_createdPhaseId', 'm_designOptionId', 'm_unplacedOwnerId', 'm_famId'])
@pytest.mark.parametrize('target', [2**64 - 1, 0])
def test_sentinel(tmp_path, fld, target):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read()
    ed = wledit.Editor(t); l = next(x for x in ed.trace(7)[3] if x[1] == 'Element.' + fld)
    ed.modify(7, [(l[2], 8, struct.pack('<Q', target))]); o = str(tmp_path / 'o.bin'); ed.save(o); new = open(o, 'rb').read()
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, new, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print(fld, '->', target, 'ACCEPTED' if ok else 'refused', str(err)[:110])
    assert not isinstance(err, str), err
    if ok: assert open(t, 'rb').read() == new
    else: assert open(t, 'rb').read() == orig
