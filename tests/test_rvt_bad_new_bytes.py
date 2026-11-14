"""c7x-rvtread2 596: the caller hands save() damaged 'new' bytes (empty, half, extra tail, CFB magic zeroed, wrong type, a different year's file): never accepted into the original; original byte-identical, no debris."""
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
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Bad bytes probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); b = open(o, 'rb').read(); os.remove(o); return b
CASES = {
 'empty': lambda n: b'', 'half': lambda n: n[:len(n) // 2], 'minus1': lambda n: n[:-1], 'tail4k': lambda n: n + b'\0' * 4096,
 'magic0': lambda n: b'\0' * 8 + n[8:], 'allzero': lambda n: bytes(len(n)), 'other_year': lambda n: None,
 'sector_flip': lambda n: n[:600] + bytes([n[600] ^ 0xFF]) + n[601:], 'text': lambda n: b'not a revit file' * 100,
}
@pytest.mark.parametrize('k', sorted(CASES))
@pytest.mark.parametrize('gate', [False, True])
@pytest.mark.parametrize('yr', ['2024', '2026'])
def test_bad(tmp_path, k, gate, yr):
    f = str(tmp_path / 'a.rfa'); shutil.copy(SRC[yr], f); raw = open(f, 'rb').read(); new = _good(tmp_path, f)
    bad = CASES[k](new) if k != 'other_year' else open(G if yr == '2024' else F, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=gate))
    try: sg.save(doc, bad, MAN); accepted = True
    except Exception: accepted = False
    now = open(f, 'rb').read()
    if accepted: pytest.fail('ESCAPE: damaged new bytes accepted (%s, gate=%s, same as good=%s)' % (k, gate, now == new))
    assert now == raw
    assert not [x for x in os.listdir(tmp_path) if x.endswith(('.sgtmp', '.part'))]
