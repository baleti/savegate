"""c5x-rvtread2 items 162-168 as regression tests (public 2024 family sample only): file mode kept, read-only refused, foreign change after open refused,
non-RVT content refused, restore chain byte-identical, damaged backup not restored, NaN/inf doubles refused."""
import os, sys, shutil, struct, stat, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')
CFG = lambda: sg.Config(allow_overwrite=True, require_gate=False)
MAN = {'modified': ['stream:Partitions/67', 'el:7']}

def _edited(path, text='Edge probe'):
    import wledit
    ed = wledit.Editor(path); ed.set_strings([(7, 'FillPattern.m_name', text)]); o = path + '.o.tmp'; ed.save(o); b = open(o, 'rb').read(); os.remove(o); return b

def _mk(tmp_path, name='a.rfa'):
    f = str(tmp_path / name); shutil.copy(F, f); return f

@pytest.mark.parametrize('mode', [0o644, 0o600, 0o664])
def test_mode_bits_kept(tmp_path, mode):
    f = _mk(tmp_path); os.chmod(f, mode); new = _edited(f)
    sg.save(sg.open_doc(f, None, CFG()), new, MAN)
    assert open(f, 'rb').read() == new and stat.S_IMODE(os.stat(f).st_mode) == mode

def test_readonly_refused(tmp_path):
    f = _mk(tmp_path); os.chmod(f, 0o444); new = _edited(f); src = open(f, 'rb').read()
    with pytest.raises(sg.SaveError): sg.save(sg.open_doc(f, None, CFG()), new, MAN)
    assert open(f, 'rb').read() == src

@pytest.mark.parametrize('how', ['append', 'flip', 'truncate'])
def test_foreign_change_after_open_refused(tmp_path, how):
    f = _mk(tmp_path); new = _edited(f); doc = sg.open_doc(f, None, CFG())
    b = bytearray(open(f, 'rb').read())
    if how == 'append': b += b'\0' * 10
    elif how == 'flip': b[-5] ^= 1
    else: b = b[:1000]
    open(f, 'wb').write(b); cur = bytes(b)
    with pytest.raises(sg.SaveError): sg.save(doc, new, MAN)
    assert open(f, 'rb').read() == cur

@pytest.mark.parametrize('blob', [b'', b'hello' * 100, b'\x89PNG\r\n\x1a\n' + bytes(300), b'PK\x03\x04' + bytes(300)])
def test_non_rvt_content_refused(tmp_path, blob):
    f = str(tmp_path / 'x.rvt'); open(f, 'wb').write(blob); new = _edited(F)
    with pytest.raises(sg.SaveError): sg.save(sg.open_doc(f, None, CFG()), new, MAN)
    assert open(f, 'rb').read() == blob

def test_restore_chain_and_damaged_backup(tmp_path):
    f = _mk(tmp_path); v0 = open(f, 'rb').read()
    n1 = _edited(f, 'V1 probe'); sg.save(sg.open_doc(f, None, CFG()), n1, MAN)
    n2 = _edited(f, 'V2 probe'); sg.save(sg.open_doc(f, None, CFG()), n2, MAN)
    assert open(f, 'rb').read() == n2
    sg.restore(f, 0); assert open(f, 'rb').read() == n1
    bl = sg.list_backups(f); orig = [p for _, p, *_ in bl if open(p, 'rb').read() == v0]
    assert orig, 'original not among backups'
    p = bl[0][1]; b = bytearray(open(p, 'rb').read()); b[5000] ^= 1; open(p, 'wb').write(b); cur = open(f, 'rb').read()
    with pytest.raises(sg.SaveError): sg.restore(f, 0)
    assert open(f, 'rb').read() == cur

@pytest.mark.parametrize('v', [float('nan'), float('inf'), float('-inf'), 1e300])
def test_nonfinite_double_refused(tmp_path, v):
    import wledit
    f = _mk(tmp_path); src = open(f, 'rb').read(); ed = wledit.Editor(f)
    x = [l for l in ed.trace(0)[3] if l[1] == 'FormatOptions.m_accuracy'][0]
    ed.modify(0, [(x[2], 8, struct.pack('<d', v))]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read()
    with pytest.raises(sg.SaveError): sg.save(sg.open_doc(f, None, CFG()), new, {'modified': ['el:0']})
    assert open(f, 'rb').read() == src
