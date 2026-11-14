"""c5x-rvtgap 140: out-of-range values written into an int/enum field (FillPattern.m_fpOrientation) through Editor.modify + gate. Records the verdict; any ACCEPTED value is reported (semantic validity in Revit unproven); refusals leave the original intact."""
import os, sys, struct, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('v', [0, 1, 7, -1, 2**31 - 1, -2**31, 2**32 - 1, 255])
def test_int(tmp_path, v):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    ed = wledit.Editor(str(t)); l = next(x for x in ed.trace(7)[3] if x[1] == 'FillPattern.m_fpOrientation')
    ed.modify(7, [(l[2], 4, struct.pack('<I', v & 0xFFFFFFFF))]); o = str(tmp_path / 'o.bin'); ed.save(o)
    new = open(o, 'rb').read()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, new, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print(v, 'ACCEPTED' if ok else 'refused', str(err)[:90])
    assert not isinstance(err, str), err
    if ok:
        assert t.read_bytes() == new
        got = wledit.Editor(str(t)).trace(7)[2]['fields']['m_pFillPattern']['obj']['m_fpOrientation']
        assert got & 0xFFFFFFFF == v & 0xFFFFFFFF
    else: assert t.read_bytes() == orig
