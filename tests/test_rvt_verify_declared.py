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


def test_gate_expect_with_wrong_declared_partition_is_refused(tmp_path):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    with pytest.raises(sg.VerifyFailed):
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), open(GEN1, 'rb').read(),
                {'modified': ['stream:Partitions/66', 'el:0'], 'expect': {0: {'SymbolInfo.m_name': 'LinearXY'}}})
    assert open(cur, 'rb').read() == open(SRC, 'rb').read()      # original untouched


def test_reference_app_path_edits_in_place_through_the_gate_and_save_as_keeps_original(tmp_path):
    import savegate as sg
    from savegate import rvt_save
    cur = str(tmp_path / 'f.rfa'); shutil.copy(SRC, cur)
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    cp = str(tmp_path / 'copy.rfa')
    rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalZ')], cfg, dest=cp)
    assert open(cur, 'rb').read() == open(SRC, 'rb').read() and open(cp, 'rb').read() != open(SRC, 'rb').read()
    V.verify_declared(SRC, cp, 7, {'FillPattern.m_name': 'HorizontalZ'})
    rvt_save.save_string_edits(cur, [(0, 'SymbolInfo.m_name', 'LinearQ'), (7, 'FillPattern.m_name', 'HorizontalZ')], cfg)
    V.verify_declared(SRC, cur, 0, {'SymbolInfo.m_name': 'LinearQ'})
    V.verify_declared(SRC, cur, 7, {'FillPattern.m_name': 'HorizontalZ'})


def test_every_gate_error_class_has_a_specific_user_message():
    from savegate import errors, rvt_save
    for n in dir(errors):
        c = getattr(errors, n)
        if isinstance(c, type) and issubclass(c, errors.SaveError) and c is not errors.SaveError:
            assert n in rvt_save._MSG, n
            assert 'original' in rvt_save.user_message(c('x')).lower() or 'nothing' in rvt_save.user_message(c('x')).lower() or 'save as' in rvt_save.user_message(c('x')).lower()
    assert 'not touched' in rvt_save.user_message(RuntimeError('boom'))


def test_rename_refused_by_the_os_leaves_original_and_no_debris(tmp_path, monkeypatch):
    import savegate as sg, errno
    from savegate import atomic, rvt_save
    cur = str(tmp_path / 'f.rfa'); shutil.copy(SRC, cur)
    real = os.replace
    def deny(a, b):
        if os.path.abspath(str(b)) == os.path.abspath(cur): raise PermissionError(errno.EACCES, 'denied (file open elsewhere)')
        return real(a, b)
    monkeypatch.setattr(os, 'replace', deny)
    with pytest.raises(sg.errors.SaveError) as ei:
        rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalZ')], sg.Config(allow_overwrite=True, require_gate=False))
    monkeypatch.undo()
    assert open(cur, 'rb').read() == open(SRC, 'rb').read()
    debris = [n for n in os.listdir(tmp_path) if n.endswith('.sgtmp') or n.startswith('.f.rfa.savegate')]
    assert not [n for n in debris if n.endswith('.sgtmp')], debris
    assert 'original' in rvt_save.user_message(ei.value).lower() or 'nothing' in rvt_save.user_message(ei.value).lower()


def test_four_chained_in_place_saves_on_the_2026_family(tmp_path):
    import savegate as sg
    from savegate import rvt_save
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
    if not os.path.exists(src): pytest.skip('2026 family absent')
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); cfg = sg.Config(allow_overwrite=True, require_gate=False)
    for e in ([(7, 'FillPattern.m_name', 'Horizontal1')], [(0, 'SymbolInfo.m_name', 'LinearA')], [(7, 'FillPattern.m_name', 'Horizontal22222')], [(7, 'FillPattern.m_name', 'Horizontal')]):
        rvt_save.save_string_edits(cur, e, cfg)
    assert V.field_diff(src, cur, 7)[0] == []      # reverted to the original value
    V.verify_declared(src, cur, 0, {'SymbolInfo.m_name': 'LinearA'})


def test_in_place_save_in_a_folder_and_file_name_with_spaces_and_non_ascii(tmp_path):
    import savegate as sg
    from savegate import rvt_save
    d = tmp_path / 'Modèle façade 日本 (v2)'; d.mkdir(); cur = str(d / 'Plän 1 final.rfa'); shutil.copy(SRC, cur)
    rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalU')], sg.Config(allow_overwrite=True, require_gate=False))
    V.verify_declared(SRC, cur, 7, {'FillPattern.m_name': 'HorizontalU'})
    assert 'Pl\u00e4n 1 final.rfa' in os.listdir(d) and not [n for n in os.listdir(d) if n.endswith('.sgtmp')]


def _saver(cur, eid, fld, txt, q):
    import savegate as sg
    from savegate import rvt_save
    try:
        rvt_save.save_string_edits(cur, [(eid, fld, txt)], sg.Config(allow_overwrite=True, require_gate=False)); q.put((eid, 'saved'))
    except Exception as e: q.put((eid, type(e).__name__))


def test_two_processes_saving_the_same_file_never_lose_or_mix_edits(tmp_path):
    import multiprocessing as mp, savegate as sg
    cur = str(tmp_path / 'f.rfa'); shutil.copy(SRC, cur)
    ctx = mp.get_context('fork'); q = ctx.Queue()
    ps = [ctx.Process(target=_saver, args=(cur, 7, 'FillPattern.m_name', 'HorizontalP', q)), ctx.Process(target=_saver, args=(cur, 0, 'SymbolInfo.m_name', 'LinearP', q))]
    [p.start() for p in ps]; [p.join(120) for p in ps]
    res = dict(q.get(timeout=5) for _ in ps)
    assert set(res.values()) <= {'saved', 'Conflict', 'Locked'}, res
    assert 'saved' in res.values(), res
    d7 = V.field_diff(SRC, cur, 7)[0]; d0 = V.field_diff(SRC, cur, 0)[0]
    # each saved edit is present, each refused edit is absent, nothing else changed
    assert bool(d7) == (res[7] == 'saved') and bool(d0) == (res[0] == 'saved'), (res, d7, d0)
    assert not [n for n in os.listdir(tmp_path) if n.endswith('.sgtmp')]


@pytest.mark.parametrize('step', ['before_replace', 'after_replace'])
def test_kill9_during_an_rvt_save_leaves_old_or_new_and_the_next_save_works(tmp_path, step):
    import subprocess, signal
    cur = str(tmp_path / 'f.rfa'); shutil.copy(SRC, cur)
    code = ("import os,signal,sys\nsys.path.insert(0,%r)\nimport savegate as sg\nfrom savegate import atomic, rvt_save\n"
            "atomic._hook = lambda s: os.kill(os.getpid(), signal.SIGKILL) if s == %r else None\n"
            "rvt_save.save_string_edits(%r, [(7,'FillPattern.m_name','HorizontalK')], sg.Config(allow_overwrite=True, require_gate=False))\n") % (os.path.join(os.path.dirname(__file__), '..'), step, cur)
    r = subprocess.run([sys.executable, '-c', code], env=dict(os.environ), capture_output=True)
    assert r.returncode == -signal.SIGKILL, r.stderr[-300:]
    now = open(cur, 'rb').read()
    if now == open(SRC, 'rb').read(): pass      # old
    else: V.verify_declared(SRC, cur, 7, {'FillPattern.m_name': 'HorizontalK'})      # or fully new and valid
    import savegate as sg
    from savegate import rvt_save, atomic
    atomic.sweep_stale_temps(str(tmp_path), max_age=-1)
    rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalL')], sg.Config(allow_overwrite=True, require_gate=False))
    V.verify_declared(SRC, cur, 7, {'FillPattern.m_name': 'HorizontalL'})


def test_damaged_formats_latest_in_the_source_refuses_in_place_save_and_warns_on_save_as(tmp_path):
    import savegate as sg, olefile
    from savegate import rvt_save
    cur = str(tmp_path / 'f.rfa'); shutil.copy(SRC, cur)
    o = olefile.OleFileIO(cur, write_mode=True); d = bytearray(o.openstream('Formats/Latest').read()); d[len(d) // 2] ^= 0x10; o.write_stream('Formats/Latest', bytes(d)); o.close()
    before = open(cur, 'rb').read()
    with pytest.raises(sg.SaveError) as ei:
        rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalD')], sg.Config(allow_overwrite=True, require_gate=False))
    assert open(cur, 'rb').read() == before, 'the damaged original must stay as it was'
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)); dest = str(tmp_path / 'copy.rfa')
    res = sg.save_as(doc, before, dest, {})
    assert open(dest, 'rb').read() == before      # an unchanged rescue copy is allowed ...
    assert any('damaged' in w for w in res.report.get('warnings', [])), res.report      # ... but is flagged as carrying the damage


def test_save_as_with_edit_of_a_damaged_source_is_refused_unless_allowed(tmp_path):
    import savegate as sg, olefile
    cur = str(tmp_path / 'f.rfa'); shutil.copy(SRC, cur)
    o = olefile.OleFileIO(cur, write_mode=True); d = bytearray(o.openstream('Formats/Latest').read()); d[len(d) // 2] ^= 0x10; o.write_stream('Formats/Latest', bytes(d)); o.close()
    before = open(cur, 'rb').read(); edited = bytearray(before); edited[-1] ^= 1
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)); dest = str(tmp_path / 'e.rfa')
    with pytest.raises(sg.SaveError):
        sg.save_as(doc, bytes(edited), dest, {})
    assert not os.path.exists(dest) and open(cur, 'rb').read() == before


@pytest.mark.parametrize('how', ['truncate1', 'truncate_sector', 'trailing_zero_sector', 'trailing_junk'])
def test_truncated_or_padded_output_is_refused_by_the_gate(tmp_path, how):
    import savegate as sg
    cur = str(tmp_path / 'f.rfa'); shutil.copy(SRC, cur); src = open(cur, 'rb').read()
    out = {'truncate1': src[:-1], 'truncate_sector': src[:-512], 'trailing_zero_sector': src + b'\0' * 512, 'trailing_junk': src + b'JUNK' * 128}[how]
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)); dest = str(tmp_path / 'o.rfa')
    with pytest.raises(sg.SaveError):
        sg.save_as(doc, out, dest, {})
    assert not os.path.exists(dest) and open(cur, 'rb').read() == src


@pytest.mark.parametrize('val', ['A\x00B', 'line1\r\nline2', 'tab\there', 'sep x', '\x01\x1f', 'emoji\U0001F600', 'lone\ud800s'])
def test_control_and_odd_characters_in_an_edit_are_saved_exactly_or_refused_with_original_intact(tmp_path, val):
    import savegate as sg
    from savegate import rvt_save
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read(); cfg = sg.Config(allow_overwrite=True, require_gate=False)
    try:
        rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', val)], cfg)
    except Exception as e:
        assert open(cur, 'rb').read() == before, 'refused (%s) but the original changed' % type(e).__name__
        return
    V.verify_declared(SRC, cur, 7, {'FillPattern.m_name': val})      # accepted: must read back exactly


@pytest.mark.parametrize('content', [b'', b'not an ole file at all', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\0' * 100, open(SRC, 'rb').read()[:4096]])
def test_empty_or_non_ole_source_is_never_saved_over_or_changed(tmp_path, content):
    import savegate as sg
    from savegate import rvt_save
    cur = str(tmp_path / 'x.rfa'); open(cur, 'wb').write(content); cfg = sg.Config(allow_overwrite=True, require_gate=False)
    with pytest.raises(Exception):
        rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'Z')], cfg)
    assert open(cur, 'rb').read() == content
    assert os.listdir(tmp_path) == ['x.rfa'], os.listdir(tmp_path)      # no temp/backup debris
    with pytest.raises(Exception):
        rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'Z')], cfg, dest=str(tmp_path / 'o.rfa'))
    assert not os.path.exists(str(tmp_path / 'o.rfa'))


@pytest.mark.parametrize('spell', ['dotdot', 'symlink', 'hardlink', 'case'])
def test_save_as_onto_the_source_by_another_spelling_never_bypasses_the_overwrite_gate(tmp_path, spell):
    import savegate as sg
    from savegate import rvt_save
    d = tmp_path / 'a'; d.mkdir(); cur = str(d / 'f.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    if spell == 'dotdot': dest = str(d / '..' / 'a' / 'f.rfa')
    elif spell == 'symlink': dest = str(tmp_path / 'ln.rfa'); os.symlink(cur, dest)
    elif spell == 'hardlink': dest = str(tmp_path / 'hl.rfa'); os.link(cur, dest)
    else: dest = str(d / 'F.rfa')
    cfg = sg.Config(allow_overwrite=False, require_gate=False)      # overwrite OFF (the default)
    try: rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalZ')], cfg, dest=dest)
    except sg.SaveError: pass
    assert open(cur, 'rb').read() == before, 'Save As reached the source through %s while overwrite is OFF' % spell


def test_batch_with_one_invalid_edit_writes_nothing_all_or_none(tmp_path):
    import savegate as sg
    from savegate import rvt_save
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read(); cfg = sg.Config(allow_overwrite=True, require_gate=False)
    bad = [[(0, 'SymbolInfo.m_name', 'LinearQ'), (7, 'FillPattern.m_name', 'lone\ud800')],           # unencodable value
           [(0, 'SymbolInfo.m_name', 'LinearQ'), (7, 'NoSuch.field', 'x')],                         # unknown field
           [(0, 'SymbolInfo.m_name', 'LinearQ'), (99999999, 'FillPattern.m_name', 'x')]]            # unknown element id
    for edits in bad:
        with pytest.raises(Exception):
            rvt_save.save_string_edits(cur, edits, cfg)
        assert open(cur, 'rb').read() == before, 'a partial batch reached the file: %r' % (edits,)
        assert os.listdir(tmp_path) == ['c.rfa']
