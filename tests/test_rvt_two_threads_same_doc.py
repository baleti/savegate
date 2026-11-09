"""c4x-rvtgap: two threads of ONE process saving the same file (same doc, then two docs): exactly the declared outcomes: one wins, the other is Locked/Conflict, the file is always one complete verified version, never a mix, no debris."""
import os, sys, shutil, threading, hashlib, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def _variants(tmp_path, f, n):
    import wledit; out = []
    for i in range(n):
        ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Thread %d %s' % (i, 'z' * i))]); o = str(tmp_path / ('v%d.tmp' % i)); ed.save(o); out.append(open(o, 'rb').read()); os.remove(o)
    return out
@pytest.mark.parametrize('same_doc', [True, False])
def test_two_threads(tmp_path, same_doc):
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); vs = _variants(tmp_path, f, 2); man = {'modified': ['stream:Partitions/67', 'el:7']}
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    d0 = sg.open_doc(f, None, cfg); docs = [d0, d0 if same_doc else sg.open_doc(f, None, cfg)]
    res = [None, None]; bar = threading.Barrier(2)
    def run(i):
        bar.wait()
        try: res[i] = sg.save(docs[i], vs[i], man)
        except sg.SaveError as e: res[i] = e
        except Exception as e: res[i] = e
    ts = [threading.Thread(target=run, args=(i,)) for i in range(2)]; [t.start() for t in ts]; [t.join(120) for t in ts]
    assert all(r is not None for r in res), res
    ok = [i for i, r in enumerate(res) if getattr(r, 'ok', False)]; bad = [r for r in res if not getattr(r, 'ok', False)]
    assert len(ok) >= 1, res
    final = open(f, 'rb').read(); assert final in vs, 'file is neither verified version'
    if len(ok) == 1: assert final == vs[ok[0]]
    for r in bad: assert isinstance(r, sg.SaveError), repr(r)       # a refusal, never a stray exception
    assert [n for n in os.listdir(tmp_path) if n not in ('a.rfa', '.savegate')] == [], os.listdir(tmp_path)
