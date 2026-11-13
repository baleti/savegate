"""c5x-rvtgap item 90: a SOURCE whose stream was renamed ('Contents' -> 'Contentt') was saved with the rename preserved. The gate must refuse it and leave the file untouched; the clean sample must still pass."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def _rename(good, old, new):
    enc = old.encode('utf-16le'); i = good.find(enc + b'\0\0')
    assert i >= 0
    d = bytearray(good); d[i:i + len(enc)] = new.encode('utf-16le'); return bytes(d)


def _edit(tmp_path, src=SRC):
    import wledit
    ed = wledit.Editor(src); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.rfa'); ed.save(o); return open(o, 'rb').read()


@pytest.mark.parametrize('old,new', [('Contents', 'Contentt'), ('PartAtom', 'PartAtoM'), ('TransmissionData', 'TransmissionDatb')])
def test_renamed_stream_in_source_refused(tmp_path, old, new):
    import savegate as sg
    good = open(SRC, 'rb').read(); bad = _rename(good, old, new)
    cur = str(tmp_path / 'c.rfa'); open(cur, 'wb').write(bad)
    with pytest.raises(sg.SaveError):
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), _edit(tmp_path, cur), {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == bad


def test_clean_sample_still_saves(tmp_path):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); open(cur, 'wb').write(open(SRC, 'rb').read()); nb = _edit(tmp_path)
    sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), nb, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == nb
