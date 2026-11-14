"""c5x-rvtgap 134: save_as to bad destinations: refusal each, source and any existing destination intact."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('kind', ['ro_dir', 'is_dir', 'existing_no_overwrite', 'hardlink_of_src', 'missing_parent', 'symlink_to_src'])
def test_dest(tmp_path, kind):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o)
    new = open(o, 'rb').read()
    dd = tmp_path / 'dd'; dd.mkdir(); dest = dd / 'y.rfa'; keep = None
    if kind == 'ro_dir': os.chmod(dd, 0o500)
    if kind == 'is_dir': dest = dd / 'sub'; dest.mkdir(); (dest / 'k').write_text('k')
    if kind == 'existing_no_overwrite': dest.write_bytes(b'precious'); keep = b'precious'
    if kind == 'hardlink_of_src': os.link(t, dest); keep = orig
    if kind == 'missing_parent': dest = dd / 'nope' / 'y.rfa'
    if kind == 'symlink_to_src': os.symlink(t, dest); keep = orig
    doc = sg.open_doc(str(t), None, sg.Config(require_gate=False, journal_dir=str(tmp_path / 'j')))
    try:
        try: r = sg.save_as(doc, new, str(dest), {'modified': ['el:7']}); ok = r.ok; err = None
        except sg.SaveError as e: ok = False; err = e
        except Exception as e: ok = False; err = 'RAW %r' % e
    finally: os.chmod(dd, 0o700)
    print(kind, 'ACCEPTED' if ok else 'refused', str(err)[:80])
    assert not isinstance(err, str), err
    assert not ok, 'accepted'
    assert t.read_bytes() == orig
    if keep is not None: assert dest.read_bytes() == keep
    if kind == 'is_dir': assert (dest / 'k').read_text() == 'k'
