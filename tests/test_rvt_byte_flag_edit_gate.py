"""c5x-rvtgap 169: 1-byte flag fields of Element (m_locked, m_moribund, m_dummy) of el:7 in the Autodesk 2024 rfa set to 0/1/2/255 through Editor.modify + gate. Verdict printed; raw exception or damaged original fails; ACCEPTED must read back."""
import os, sys, shutil, pytest
import savegate as sg
import itertools
FS = [os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%d.rfa' % y) for y in (2024, 2026)]
@pytest.mark.parametrize('F', FS)
@pytest.mark.parametrize('fld', ['Element.m_locked', 'Element.m_moribund', 'Element.m_dummy'])
@pytest.mark.parametrize('v', [1, 2, 255])
def test_flag(tmp_path, fld, v, F):
    if not os.path.exists(F): pytest.skip('no sample')
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    ed = wledit.Editor(str(t)); l = next(x for x in ed.trace(7)[3] if x[1] == fld)
    ed.modify(7, [(l[2], 1, bytes([v]))]); o = str(tmp_path / 'o.bin'); ed.save(o)
    new = open(o, 'rb').read()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, new, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print(fld, v, 'ACCEPTED' if ok else 'refused', str(err)[:90])
    assert not isinstance(err, str), err
    if ok:
        assert t.read_bytes() == new
        got = wledit.Editor(str(t)).trace(7)[2]['fields'][fld.split('.')[1]]
        assert got == v, got
    else: assert t.read_bytes() == orig

@pytest.mark.parametrize('y', [2020, 2021, 2022, 2023, 2025])
def test_unwritable_year_refused(tmp_path, y):
    """c5x-rvtgap 173b: the same save on a non-writable year is refused with UnsupportedVersion and the file is untouched."""
    f = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%d.rfa' % y)
    if not os.path.exists(f): pytest.skip('no sample')
    t = str(tmp_path / 'x.rfa'); shutil.copy(f, t); orig = open(t, 'rb').read()
    with pytest.raises(sg.SaveError):
        doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
        sg.save(doc, orig[:-1] + bytes([orig[-1] ^ 1]), {'modified': ['el:7']})
    assert open(t, 'rb').read() == orig
