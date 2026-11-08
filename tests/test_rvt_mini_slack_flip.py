"""c4x-rvtgap 151: a flip in the zero padding after a small stream's end (mini sector tail) or after the mini-stream size is refused (it was accepted 3/3 per stream before)."""
import os, sys, shutil, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no sample')

def test_mini_tail_flips_refused(tmp_path):
    import savegate as sg, wledit, cfb
    from savegate.adapters import RvtAdapter
    ed = wledit.Editor(SRC); PN = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Flip')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    good = open(o, 'rb').read(); c = cfb.CFB(good); ss = c.ss; off = lambda s: (s + 1) * ss
    chain = []; x = c.entries[0].start
    while x < 0xFFFFFFF0: chain.append(x); x = c.fat[x]
    mo = lambda m: off(chain[m // ss]) + m % ss
    def run(pos):
        bad = good[:pos] + bytes([good[pos] ^ 0x10]) + good[pos + 1:]
        cur = str(tmp_path / 'cur'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
        doc = sg.open_doc(cur, RvtAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
        try: sg.save(doc, bad, {'modified': ['stream:' + PN, 'el:7']}); return True
        except sg.SaveError: assert open(cur, 'rb').read() == before; return False
    root = c.entries[0]; acc = []
    for name, e in c.streams().items():
        if 0 < e.size < c.cutoff and e.size % 64:
            m = e.start
            while c.minifat[m] < 0xFFFFFFFA: m = c.minifat[m]
            acc += [(name, p) for p in (m * 64 + e.size % 64, (m + 1) * 64 - 1) if run(mo(p))]
    acc += [('tail', p) for p in (root.size, len(chain) * ss - 1) if root.size <= p < len(chain) * ss and run(mo(p))]
    assert not acc, acc
