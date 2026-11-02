import os, shutil, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
GEN1 = os.path.expanduser('~/demo-state/oracle-files/c4x_2024_family_edit_gen1.rfa')
pytestmark = pytest.mark.skipif(not (os.path.exists(SRC) and os.path.exists(GEN1) and os.path.isdir(os.path.expanduser('~/rvt-research/write-lab'))), reason='needs the public 2024 family sample and the writer lab')
from savegate import rvt_verify as V


def test_intended_edit_passes_and_unexpected_or_wrong_value_fails():
    assert V.verify_declared(SRC, GEN1, 0, {'SymbolInfo.m_name': 'LinearXY'})
    with pytest.raises(ValueError): V.verify_declared(SRC, GEN1, 0, {'SymbolInfo.m_name': 'Other'})
    with pytest.raises(ValueError): V.verify_declared(SRC, SRC, 0, {'SymbolInfo.m_name': 'LinearXY'})


def test_flip_inside_the_declared_record_is_caught(tmp_path):
    import cfb, rvtw, wlpart
    c = cfb.CFB(open(GEN1, 'rb').read()); pn = 'Partitions/67'; st = rvtw.Stream(c.streams()[pn].data); pt = wlpart.Partition(st)
    import wlrec
    b = wlrec.Model(GEN1); _, i, _, log, q = list(b.find(0))[0]
    offs = 0; hit = None
    for k, m in enumerate(pt.mem):
        if offs <= i + 20 < offs + len(m['raw']): hit = (k, i + 20 - offs); break
        offs += len(m['raw'])
    k, pos = hit; raw = bytearray(pt.mem[k]['raw']); raw[pos] ^= 0x01; pt.mem[k]['raw'] = raw; pt.mem[k]['dirty'] = True
    P2 = pt.rebuild(); pad = (-len(P2)) % rvtw.PAGE_PAYLOAD if len(P2) > st.full * rvtw.PAGE_PAYLOAD + getattr(st, 'cap_last', 0) else 0
    c.streams()[pn].data = st.build(P2 + b'\0' * pad, keep_spare=False); o = str(tmp_path / 'flip.rfa'); cfb.write(c, o)
    try: V.verify_declared(SRC, o, 0, {'SymbolInfo.m_name': 'LinearXY'})
    except ValueError: return
    except Exception: return      # undecodable after the flip is also a refusal
    pytest.fail('a bit flip inside the declared record passed verify_declared')


def _gate(tmp_path, expect):
    import savegate as sg
    cur = str(tmp_path / 'cur.rfa'); shutil.copy(SRC, cur)
    man = {'modified': ['stream:Partitions/67', 'el:0'], 'expect': expect}
    return sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), open(GEN1, 'rb').read(), man)


def test_gate_manifest_expect_accepts_the_intended_value_and_refuses_another(tmp_path):
    import savegate as sg
    _gate(tmp_path, {0: {'SymbolInfo.m_name': 'LinearXY'}})
    with pytest.raises(sg.VerifyFailed): _gate(tmp_path, {0: {'SymbolInfo.m_name': 'Linear2'}})


def test_verify_new_refuses_an_id_that_already_exists_in_the_source():
    with pytest.raises(ValueError): V.verify_new(SRC, GEN1, 0, None, {})


def test_verify_new_refuses_an_id_missing_from_the_output():
    with pytest.raises(ValueError): V.verify_new(SRC, GEN1, 99999999, None, {})


TPL = os.path.expanduser('~/rvt-research/corpus/2026/77_Construction-DefaultMetric.rte')
CLONE = os.path.expanduser('~/demo-state/oracle-files/c4x_2026_construction_template_clone1.rte')


@pytest.mark.skipif(not (os.path.exists(TPL) and os.path.exists(CLONE)), reason='needs the Autodesk 2026 template and the clone oracle file')
def test_verify_new_accepts_the_real_clone_and_refuses_a_wrong_clone_source():
    assert V.verify_new(TPL, CLONE, 302722, 2, {})
    with pytest.raises(ValueError): V.verify_new(TPL, CLONE, 302722, 3, {})


@pytest.mark.skipif(not (os.path.exists(TPL) and os.path.exists(CLONE)), reason='needs the Autodesk 2026 template and the clone oracle file')
def test_gate_clone_with_expect_accepts_true_clone_source_and_refuses_wrong_one(tmp_path):
    import savegate as sg
    def run(co):
        cur = str(tmp_path / 'c.rte'); shutil.copy(TPL, cur)
        man = {'added': ['el:302722'], 'modified': ['stream:Partitions/61', 'stream:Global/ElemTable'], 'expect': {302722: {'__clone_of__': co}}}
        return sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), open(CLONE, 'rb').read(), man)
    run(2)
    with pytest.raises(sg.VerifyFailed): run(3)


def test_gate_two_element_edit_with_expect(tmp_path):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC)
    ed.set_strings([(0, 'SymbolInfo.m_name', 'LinearXY'), (7, 'FillPattern.m_name', 'HorizontalX')])
    out = str(tmp_path / 'o.rfa'); ed.save(out); b = open(out, 'rb').read()
    def run(ex):
        cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
        return sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), b, {'modified': ['stream:Partitions/67', 'el:0', 'el:7'], 'expect': ex})
    run({0: {'SymbolInfo.m_name': 'LinearXY'}, 7: {'FillPattern.m_name': 'HorizontalX'}})
    with pytest.raises(sg.VerifyFailed): run({0: {'SymbolInfo.m_name': 'LinearXY'}, 7: {'FillPattern.m_name': 'Horizontal2'}})


def test_light_model_gives_the_same_fields_as_the_full_model():
    a = V.field_diff(SRC, GEN1, 0)[0]
    b = V.field_diff(SRC, GEN1, 0, only={'Partitions/67'})[0]
    assert a == b and a
    with pytest.raises(ValueError): V.field_diff(SRC, GEN1, 0, only={'Partitions/1'})      # element not in a loaded partition: not silently accepted
