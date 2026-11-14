"""c5x-rvtgap 161: output bytes of another file TYPE of the same year (2024 rte template over a 2024 rfa source and back): refused, original intact."""
import os, shutil, pytest
import savegate as sg
A = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
B = os.path.expanduser('~/rvt-research/corpus/2024/71_Construction-DefaultMetric.rte')
@pytest.mark.skipif(not (os.path.exists(A) and os.path.exists(B)), reason='no sample')
@pytest.mark.parametrize('src,out,ext', [(A, B, 'rfa'), (B, A, 'rte')])
@pytest.mark.parametrize('man', [{'modified': ['el:7']}, {'modified': ['file']}, {'modified': ['el:29339']}])
def test_cross_type(tmp_path, src, out, ext, man):
    t = tmp_path / ('x.' + ext); shutil.copy(src, t); orig = t.read_bytes()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, open(out, 'rb').read(), man).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print('ACCEPTED' if ok else 'refused', str(err)[:100])
    assert not isinstance(err, str), err
    assert not ok and t.read_bytes() == orig
