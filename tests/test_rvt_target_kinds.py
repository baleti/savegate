"""c2x-rvtgap: in-place gate save by target kind. Mode kept, symlink followed (link stays), read-only and hardlinked targets refused with the file untouched."""
import os, sys, shutil, hashlib, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
H = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _save(tmp_path, tgt):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Zed')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    new = open(o, 'rb').read()
    doc = sg.open_doc(tgt, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    return hashlib.sha256(new).hexdigest()


def _real(tmp_path):
    d = tmp_path / 't'; d.mkdir(); r = str(d / 'real.rfa'); shutil.copy(SRC, r); return r


def test_mode_kept(tmp_path):
    r = _real(tmp_path); os.chmod(r, 0o640); h = _save(tmp_path, r)
    assert H(r) == h and os.stat(r).st_mode & 0o777 == 0o640


def test_readonly_refused(tmp_path):
    import savegate as sg
    r = _real(tmp_path); os.chmod(r, 0o444); before = H(r)
    with pytest.raises(sg.SaveError): _save(tmp_path, r)
    assert H(r) == before


def test_symlink_followed(tmp_path):
    r = _real(tmp_path); l = str(tmp_path / 't' / 'link.rfa'); os.symlink(r, l); h = _save(tmp_path, l)
    assert os.path.islink(l) and H(r) == h


def test_hardlink_refused(tmp_path):
    import savegate as sg
    r = _real(tmp_path); l = str(tmp_path / 't' / 'hard.rfa'); os.link(r, l); before = H(r)
    with pytest.raises(sg.SaveError): _save(tmp_path, l)
    assert H(r) == before and H(l) == before
