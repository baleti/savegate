"""c5x-rvtgap 163: the caller keeps mutating the bytearray it passed while the gate verifies/writes: the saved file must equal the snapshot taken at the call (the verified bytes)."""
import os, sys, shutil, threading, time, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('fn', ['save', 'save_as'])
def test_mutation(tmp_path, fn):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o); good = open(o, 'rb').read()
    ba = bytearray(good); stop = threading.Event(); started = threading.Event()
    def mutate():
        started.wait()
        while not stop.is_set():
            for i in range(0, len(ba), 4097): ba[i] ^= 0xFF
    th = threading.Thread(target=mutate, daemon=True); th.start()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    dest = str(tmp_path / 'y.rfa')
    orig_bytes = bytes
    snap_ok = []
    try:
        started.set()      # mutation runs from the very call on; the snapshot may already be a torn mix of good and flipped bytes
        try: r = sg.save(doc, ba, {'modified': ['el:7']}) if fn == 'save' else sg.save_as(doc, ba, dest, {'modified': ['el:7']}); ok = r.ok; err = None
        except sg.SaveError as e: ok = False; err = e
    finally: stop.set(); th.join(5)
    out = open(t if fn == 'save' else dest, 'rb').read() if ok or fn == 'save' else None
    print(fn, 'accepted' if ok else 'refused', str(err)[:80])
    if ok: assert out == good, 'accepted file differs from the unmutated edit: torn snapshot was accepted'
    else:
        if fn == 'save': assert out == orig
        else: assert not os.path.exists(dest)
