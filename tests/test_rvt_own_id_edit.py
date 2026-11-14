"""c5x-rvtgap 185: the element's own id (Element.m_id) rewritten inside its record (to another existing id, to a fresh id, to the invalid sentinel) on the Autodesk 2024 rfa, writer + gate. A record whose stored id differs from its ElemTable row is an identity corruption: the gate must refuse; the test records the verdict, fails on a raw exception or damaged original, and fails if ACCEPTED."""
import os, sys, struct, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('newid', [17, 99999999, 2**64 - 1, 0])
def test_own_id(tmp_path, newid):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read()
    ed = wledit.Editor(t); l = next(x for x in ed.trace(7)[3] if x[1] == 'Element.m_id')
    ed.modify(7, [(l[2], 8, struct.pack('<Q', newid))]); o = str(tmp_path / 'o.bin'); ed.save(o); new = open(o, 'rb').read()
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, new, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print(newid, 'ACCEPTED' if ok else 'refused', str(err)[:110])
    assert not isinstance(err, str), err
    assert not ok, 'own id rewritten and accepted'
    assert open(t, 'rb').read() == orig
