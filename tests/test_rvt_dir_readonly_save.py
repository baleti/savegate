"""c5x-rvtgap 126: target dir not writable (rename/temp impossible) but the file itself is writable: the save must refuse cleanly or succeed whole; the original is never left partial."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_dir_ro(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    d = tmp_path / 'd'; d.mkdir(); t = d / 'x.rfa'; shutil.copy(F, t)
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.tmp'); ed.save(o)
    new = open(o, 'rb').read(); orig = t.read_bytes()
    os.chmod(d, 0o500)
    try:
        doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
        try: ok = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}).ok; err = None
        except sg.SaveError as e: ok = False; err = e
        except Exception as e: ok = False; err = 'RAW %r' % e
        print('ok', ok, 'err', err)
        assert not isinstance(err, str), err
        assert t.read_bytes() in (orig, new)
        assert sorted(os.listdir(d)) in (['x.rfa'], ['.savegate', 'x.rfa'])
    finally:
        os.chmod(d, 0o700)
