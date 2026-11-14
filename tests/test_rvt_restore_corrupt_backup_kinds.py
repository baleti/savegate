"""c5x-rvtgap 133: truncated / empty / zero-filled backup next to a good one: restore of the bad one refused, target untouched, the good one still restorable."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('kind', ['truncated', 'empty', 'zeroed', 'appended'])
def test_corrupt_backup(tmp_path, kind):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    vers = [orig]
    for i in range(2):
        ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'E%d' % i)]); o = str(tmp_path / 'o.bin'); ed.save(o)
        new = open(o, 'rb').read(); os.remove(o)
        doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=5, journal_dir=str(tmp_path / 'j')))
        assert sg.save(doc, new, {'modified': ['el:7']}).ok; vers.append(new)
    bl = sg.backup.list_backups(str(t)); assert len(bl) == 2
    bad = bl[0][1]; b = open(bad, 'rb').read()
    open(bad, 'wb').write({'truncated': b[:len(b) // 2], 'empty': b'', 'zeroed': bytes(len(b)), 'appended': b + b'\0' * 512}[kind])
    cur = t.read_bytes()
    try: sg.restore(str(t), which=0); err = None
    except sg.SaveError as e: err = e
    except Exception as e: err = 'RAW %r' % e
    assert not isinstance(err, str), err
    assert err is not None, 'corrupt backup was restored'
    assert t.read_bytes() == cur
    sg.restore(str(t), which=1); assert t.read_bytes() == orig
