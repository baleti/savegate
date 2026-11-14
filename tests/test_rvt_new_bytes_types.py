"""c5x-rvtgap 164: new_bytes of odd types never crash with a raw error and never modify the original (str, None, int, list, empty bytes, memoryview/bytearray of the valid edit)."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('kind', ['str', 'none', 'int', 'list', 'empty', 'memoryview', 'bytearray', 'bytes_ok'])
@pytest.mark.parametrize('fn', ['save', 'save_as'])
def test_types(tmp_path, kind, fn):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o); good = open(o, 'rb').read()
    nb = {'str': 'text', 'none': None, 'int': 5, 'list': [1, 2], 'empty': b'', 'memoryview': memoryview(good), 'bytearray': bytearray(good), 'bytes_ok': good}[kind]
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    dest = str(tmp_path / 'y.rfa')
    try:
        r = sg.save(doc, nb, {'modified': ['el:7']}) if fn == 'save' else sg.save_as(doc, nb, dest, {'modified': ['el:7']}); ok = r.ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %s %s' % (type(e).__name__, str(e)[:60])
    print(fn, kind, 'accepted' if ok else 'refused', str(err)[:70])
    assert t.read_bytes() == (good if (ok and fn == 'save') else orig)
    if ok: assert open(t if fn == 'save' else dest, 'rb').read() == good
    if kind in ('str', 'none', 'int', 'list', 'empty'): assert not ok
    assert not isinstance(err, str), err
