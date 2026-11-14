"""c7x-rvtread2 609-612: payload whose CFB structure is mutated (duplicated dir entry, FAT self-loop on the directory chain, DIFAT count, mini-stream cutoff, FAT count): never accepted, no hang, original intact, refusal not GateClosed/LowMemory."""
import os, sys, shutil, struct, time, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
G = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
SRC = {'2024': F, '2026': G}
pytestmark = pytest.mark.skipif(not (os.path.exists(F) and os.path.exists(G)), reason='no sample')
MAN = {'modified': ['stream:Partitions/67', 'el:7']}
def _good(tmp_path, f):
    import wledit
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'CFB probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); b = open(o, 'rb').read(); os.remove(o); return b
def _u32(b, o, v): return b[:o] + struct.pack('<I', v) + b[o + 4:]
def _g32(b, o): return struct.unpack_from('<I', b, o)[0]
def dup_dir(b):
    ss = 1 << struct.unpack_from('<H', b, 0x1E)[0]; d = (_g32(b, 0x30) + 1) * ss
    return b[:d + 256] + b[d + 128:d + 256] + b[d + 384:]
def fat_loop(b):
    ss = 1 << struct.unpack_from('<H', b, 0x1E)[0]; d = _g32(b, 0x30); f = (_g32(b, 0x4C) + 1) * ss
    return _u32(b, f + 4 * d, d)
CASES = {'dup_dir': dup_dir, 'fat_loop': fat_loop,
 'difat_count': lambda b: _u32(b, 0x48, _g32(b, 0x48) + 1), 'fat_count': lambda b: _u32(b, 0x2C, _g32(b, 0x2C) + 1),
 'mini_cutoff': lambda b: _u32(b, 0x38, 0x2000), 'first_dir_sector': lambda b: _u32(b, 0x30, _g32(b, 0x30) + 1),
 'minifat_start': lambda b: _u32(b, 0x3C, 0)}
@pytest.mark.parametrize('k', sorted(CASES))
@pytest.mark.parametrize('yr', ['2024', '2026'])
def test_cfb(tmp_path, k, yr):
    f = str(tmp_path / 'a.rfa'); shutil.copy(SRC[yr], f); raw = open(f, 'rb').read(); new = _good(tmp_path, f)
    bad = CASES[k](new); assert bad != new
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)); t = time.time(); acc = False
    try: sg.save(doc, bad, MAN); acc = True
    except Exception as e: assert type(e).__name__ not in ('GateClosed', 'LowMemory'), type(e).__name__
    assert time.time() - t < 120, 'hang'
    assert open(f, 'rb').read() == raw, 'original changed'
    assert not acc, 'ESCAPE: mutated CFB structure accepted (%s)' % k
    assert not [x for x in os.listdir(tmp_path) if x.endswith(('.sgtmp', '.part'))]
