"""c2x-rvtgap 124: a reader polling the target while gate saves run only ever sees the exact old or new bytes (never a torn/partial file)."""
import os, sys, shutil, threading, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_reader_sees_old_or_new(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t)
    seen = set(); bad = []; stop = threading.Event(); allowed = {open(F, 'rb').read()}
    def reader():
        while not stop.is_set():
            try: d = open(t, 'rb').read()
            except FileNotFoundError: bad.append('missing'); continue
            seen.add(d)
            if d not in allowed: bad.append(len(d))
    th = threading.Thread(target=reader); th.start()
    try:
        for i in range(8):
            ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', 'R%d' % i)]); o = str(tmp_path / 'o.tmp'); ed.save(o)
            new = open(o, 'rb').read(); os.remove(o); allowed.add(new)
            doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
            assert sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}).ok
    finally:
        stop.set(); th.join()
    assert not bad, bad[:5]
    assert len(seen) >= 2
