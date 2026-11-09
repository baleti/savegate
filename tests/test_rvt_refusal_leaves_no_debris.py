"""c4x-rvtgap: after a REFUSED in-place save (collateral change, structural damage, declared metadata edit, truncated bytes) the folder holds exactly the original (plus at most the .savegate store): no tmp/part/lock file, no backup of a save that never happened, and the per-process scratch dir is empty."""
import os, sys, shutil, glob, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
def _cases(good):
    b = bytearray(good); b[len(b) // 3] ^= 1
    yield 'collateral_flip', bytes(b)
    yield 'truncated', good[:len(good) // 2]
    yield 'junk', b'not a file at all' * 50
    yield 'tail_zeros', good + b'\0' * 4096
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_no_debris(tmp_path):
    import wledit
    ed = wledit.Editor(F); ed.set_strings([(7, 'FillPattern.m_name', 'Debris probe')]); o = str(tmp_path / 'o.rfa'); ed.save(o); good = open(o, 'rb').read(); os.remove(o)
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    for name, data in _cases(good):
        d = tmp_path / name; d.mkdir(); f = str(d / 'a.rfa'); shutil.copy(F, f); before = open(f, 'rb').read()
        doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
        with pytest.raises(sg.SaveError): sg.save(doc, data, man)
        assert open(f, 'rb').read() == before, name
        left = sorted(os.listdir(d)); assert left == ['a.rfa'], (name, left)      # verify runs before any backup: a refusal leaves nothing
        assert not glob.glob(str(d / '*.lock')) and not glob.glob(str(d / '*.tmp'))
    mine = glob.glob(os.path.join(os.environ.get('TMPDIR', '/tmp'), 'savegate-%d-*' % os.getpid()))
    assert all(not os.listdir(m) for m in mine), [(m, os.listdir(m)) for m in mine if os.listdir(m)]
