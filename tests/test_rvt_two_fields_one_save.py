"""c5x-rvtgap 176: two field edits inside one element record in one save (int FillPattern.m_fpOrientation + flag Element.m_locked of el:7, descending offsets) through writer and gate, Autodesk 2024/2026 rfa. Also pins that mixing set_strings with modify on the same record is refused by the writer lab (ValueError) before any output. ACCEPTED must read both fields back; otherwise original intact."""
import os, sys, struct, shutil, pytest
import savegate as sg
def _setup(tmp_path, y):
    F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%d.rfa' % y)
    if not os.path.exists(F): pytest.skip('no sample')
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t)
    ed = wledit.Editor(t); tr = ed.trace(7)[3]
    lo = next(x for x in tr if x[1] == 'FillPattern.m_fpOrientation'); lk = next(x for x in tr if x[1] == 'Element.m_locked')
    return wledit, t, ed, lo, lk
@pytest.mark.parametrize('y', [2024, 2026])
def test_two(tmp_path, y):
    wledit, t, ed, lo, lk = _setup(tmp_path, y); orig = open(t, 'rb').read()
    ed.modify(7, sorted([(lo[2], 4, struct.pack('<I', 1)), (lk[2], 1, b'\x01')], reverse=True))
    o = str(tmp_path / 'o.bin'); ed.save(o); new = open(o, 'rb').read()
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, new, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print(y, 'ACCEPTED' if ok else 'refused', str(err)[:120])
    assert not isinstance(err, str), err
    if ok:
        assert open(t, 'rb').read() == new
        f = wledit.Editor(t).trace(7)[2]['fields']
        assert f['m_locked'] == 1 and f['m_pFillPattern']['obj']['m_fpOrientation'] == 1
    else: assert open(t, 'rb').read() == orig
@pytest.mark.parametrize('y', [2024, 2026])
def test_string_plus_modify_refused_by_writer(tmp_path, y):
    wledit, t, ed, lo, lk = _setup(tmp_path, y); orig = open(t, 'rb').read()
    ed.modify(7, [(lk[2], 1, b'\x01')])
    with pytest.raises(ValueError):
        ed.set_strings([(7, 'FillPattern.m_name', 'xé')])
    assert open(t, 'rb').read() == orig
