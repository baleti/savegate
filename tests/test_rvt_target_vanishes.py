"""c5x-rvtgap 128: target deleted or replaced by a directory / other file between open_doc and save: refuse, write nothing elsewhere."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('how', ['deleted', 'dir', 'other_bytes'])
def test_vanish(tmp_path, how):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    d = tmp_path / 'd'; d.mkdir(); t = d / 'x.rfa'; shutil.copy(F, t)
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o)
    new = open(o, 'rb').read()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    os.remove(t)
    if how == 'dir': t.mkdir(); (t / 'keep.txt').write_text('k')
    if how == 'other_bytes': t.write_bytes(b'someone else wrote this' * 10)
    try: ok = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    assert not isinstance(err, str), err
    assert not ok, 'save accepted although the target vanished/changed'
    if how == 'deleted': assert not t.exists()
    if how == 'dir': assert t.is_dir() and (t / 'keep.txt').read_text() == 'k'
    if how == 'other_bytes': assert t.read_bytes() == b'someone else wrote this' * 10
    assert not [n for n in os.listdir(d) if n.endswith('.sgtmp')]
