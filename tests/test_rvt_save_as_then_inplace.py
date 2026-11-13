"""c2x-rvtgap 107: save_as to a new path leaves the original byte-identical; a following in-place save on the copy changes only the copy; both outputs source_damage-clean; folder holds only the two files + .savegate."""
import os, sys, shutil, hashlib, pytest
import savegate as sg
from savegate.adapters import RvtAdapter
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_save_as_then_inplace(tmp_path):
    import wledit
    a = str(tmp_path / 'a.rfa'); b = str(tmp_path / 'b.rfa'); shutil.copy(F, a); h0 = h(a)
    def build(src, txt):
        ed = wledit.Editor(src); ed.set_strings([(7, 'FillPattern.m_name', txt)]); o = str(tmp_path / 'o.tmp.rfa'); ed.save(o)
        x = open(o, 'rb').read(); os.remove(o); return x
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    doc = sg.open_doc(a, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=3))
    assert sg.save_as(doc, build(a, 'AsCopy'), b, man).ok
    assert h(a) == h0 and RvtAdapter().source_damage(open(b, 'rb').read()) == []
    hb = h(b); docb = sg.open_doc(b, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=3))
    assert sg.save(docb, build(b, 'InPlaceOnCopy'), man).ok
    assert h(b) != hb and h(a) == h0 and RvtAdapter().source_damage(open(b, 'rb').read()) == []
    assert sorted(os.listdir(tmp_path)) == ['.savegate', 'a.rfa', 'b.rfa']
