"""c5x-rvtgap: a save refuses up front, writing nothing, when a volume has less free space than the save needs (measured with a patched shutil.disk_usage)."""
import os, sys, shutil, collections
import pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
U = collections.namedtuple('U', 'total used free')


def _setup(tmp_path):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Zed')]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    os.remove(o); cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    return cur, new, sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))


def test_low_space_refuses_before_writing(tmp_path, monkeypatch):
    import savegate as sg
    cur, new, doc = _setup(tmp_path); before = sorted(os.listdir(tmp_path)); orig = open(cur, 'rb').read()
    monkeypatch.setattr(shutil, 'disk_usage', lambda d: U(10 ** 9, 10 ** 9 - 100, 100))
    with pytest.raises(sg.SaveError) as ei:
        sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert 'not enough free space' in str(ei.value)
    assert open(cur, 'rb').read() == orig and sorted(os.listdir(tmp_path)) == before


def test_enough_space_saves(tmp_path):
    import savegate as sg
    cur, new, doc = _setup(tmp_path)
    sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == new
