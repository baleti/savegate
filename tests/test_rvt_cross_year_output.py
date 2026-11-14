"""c5x-rvtgap 160: output bytes of another Revit year (2026 rfa over a 2024 rfa source, and the reverse), declared as a plain edit: refused, original intact."""
import os, shutil, pytest
import savegate as sg
A = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
B = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
@pytest.mark.skipif(not (os.path.exists(A) and os.path.exists(B)), reason='no sample')
@pytest.mark.parametrize('src,out', [(A, B), (B, A)])
@pytest.mark.parametrize('man', [{'modified': ['el:7']}, {'modified': ['file']}, {'modified': ['stream:Partitions/67', 'el:7']}])
def test_cross_year(tmp_path, src, out, man):
    t = tmp_path / 'x.rfa'; shutil.copy(src, t); orig = t.read_bytes()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, open(out, 'rb').read(), man).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print('ACCEPTED' if ok else 'refused', str(err)[:100])
    assert not isinstance(err, str), err
    assert not ok and t.read_bytes() == orig
