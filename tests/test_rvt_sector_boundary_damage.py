"""c7x-rvtread2 608: payload truncated at, or with one 512-byte sector zeroed at, 16 spread sector boundaries (2024/2026 families): never accepted, original intact, refusal not GateClosed/LowMemory."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
G = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
SRC = {'2024': F, '2026': G}
pytestmark = pytest.mark.skipif(not (os.path.exists(F) and os.path.exists(G)), reason='no sample')
MAN = {'modified': ['stream:Partitions/67', 'el:7']}
def _good(tmp_path, f):
    import wledit
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Sector probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); b = open(o, 'rb').read(); os.remove(o); return b
@pytest.mark.parametrize('mode', ['trunc', 'zero'])
@pytest.mark.parametrize('yr', ['2024', '2026'])
def test_sector(tmp_path, mode, yr):
    f = str(tmp_path / 'a.rfa'); shutil.copy(SRC[yr], f); raw = open(f, 'rb').read(); new = _good(tmp_path, f)
    ns = len(new) // 512; accepted = []
    for k in range(16):
        s = max(1, ns * (k + 1) // 17)
        bad = new[:s * 512] if mode == 'trunc' else new[:s * 512] + bytes(512) + new[s * 512 + 512:]
        if bad == new: continue
        doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
        try: sg.save(doc, bad, MAN); accepted.append(s)
        except Exception as e:
            assert type(e).__name__ not in ('GateClosed', 'LowMemory'), type(e).__name__
        assert open(f, 'rb').read() == raw, 'original changed at sector %d' % s
        if accepted: break
    assert not accepted, 'ESCAPE at sectors %s' % accepted
    assert not [x for x in os.listdir(tmp_path) if x.endswith(('.sgtmp', '.part'))]
