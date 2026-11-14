"""c5x-rvtgap 132: restore with odd `which` values and a foreign file in the backup dir never damages the target and never raises a raw error."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_restore_which(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o)
    new = open(o, 'rb').read()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    assert sg.save(doc, new, {'modified': ['el:7']}).ok
    d = tmp_path / '.savegate'; (d / 'junk.txt').write_text('foreign'); (d / 'x.rfa.bak').write_bytes(b'garbage')
    for w in [-1, 99, '0', 1.5, True, [0], 'abc']:
        before = t.read_bytes()
        try: sg.restore(str(t), which=w); err = None
        except sg.SaveError as e: err = e
        except Exception as e: err = 'RAW %r' % e
        print(repr(w), 'raw' if isinstance(err, str) else ('refused' if err else 'restored'))
        assert not isinstance(err, str), (w, err)
        now = t.read_bytes()
        assert now in (orig, new, before), w      # only a genuine version may ever be there
