"""c5x-rvtgap 172: in-place save replaces the file atomically; do user extended attributes (e.g. downloaded-from marks, backup tags) survive? Records the behaviour; pins it."""
import os, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_xattr(tmp_path):
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t)
    try: os.setxattr(t, 'user.c5x', b'tag')
    except OSError as e: pytest.skip('no user xattr: %r' % e)
    orig = open(t, 'rb').read()
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    import sys; sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit, struct
    ed = wledit.Editor(t); l = next(x for x in ed.trace(7)[3] if x[1] == 'FillPattern.m_fpOrientation')
    ed.modify(7, [(l[2], 4, struct.pack('<I', 1))]); o = str(tmp_path / 'o.bin'); ed.save(o); new = open(o, 'rb').read()
    assert sg.save(doc, new, {'modified': ['el:7']}).ok and open(t, 'rb').read() == new
    kept = os.listxattr(t)
    print('xattrs after save:', kept)
    assert 'user.c5x' in kept and os.getxattr(t, 'user.c5x') == b'tag'
