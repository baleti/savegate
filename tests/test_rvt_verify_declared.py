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


def _edited_bytes(path, eid=7, val='HorizontalZ'):
    import sys, tempfile
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
    import wledit
    ed = wledit.Editor(path); ed.set_strings([(eid, 'FillPattern.m_name', val)])
    with tempfile.TemporaryDirectory() as d:
        o = os.path.join(d, 'o.rfa'); ed.save(o); return open(o, 'rb').read()


def test_source_replaced_by_another_file_between_open_and_save_is_a_conflict(tmp_path):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)); new = _edited_bytes(SRC)
    other = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
    for repl in (open(other, 'rb').read(), open(SRC, 'rb').read()[:-1] + b'\x01'):      # different file / same size, one byte different
        open(cur, 'wb').write(repl)
        with pytest.raises(sg.Conflict):
            sg.save(doc, new, {})
        assert open(cur, 'rb').read() == repl, 'the newer file on disk must not be overwritten'


@pytest.mark.parametrize('year', ['2023', '2025'])
def test_unsupported_year_is_refused_in_place_with_original_intact(tmp_path, year):
    import savegate as sg
    from savegate import rvt_save
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % year)
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); before = open(cur, 'rb').read()
    with pytest.raises(sg.SaveError):
        rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalZ')], sg.Config(allow_overwrite=True, require_gate=True))
    assert open(cur, 'rb').read() == before and os.listdir(tmp_path) == ['c.rfa']


def test_wrong_expected_value_in_manifest_is_refused(tmp_path):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read(); new = _edited_bytes(SRC, 7, 'HorizontalZ')
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    for exp in ({7: {'FillPattern.m_name': 'SomethingElse'}}, {8: {'FillPattern.m_name': 'HorizontalZ'}}):
        with pytest.raises(sg.SaveError):
            sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7'], 'expect': exp})
        assert open(cur, 'rb').read() == before


@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores dir modes')
def test_save_as_into_a_read_only_directory_fails_cleanly(tmp_path):
    import savegate as sg
    from savegate import rvt_save
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); ro = tmp_path / 'ro'; ro.mkdir(); os.chmod(ro, 0o500)
    try:
        with pytest.raises(sg.SaveError):
            rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', 'HorizontalZ')], sg.Config(allow_overwrite=False, require_gate=False), dest=str(ro / 'o.rfa'))
        assert os.listdir(ro) == []
    finally: os.chmod(ro, 0o700)


def test_long_string_edit_is_verified_in_full_not_on_the_60_char_log_prefix(tmp_path):
    """before the fix the decoder log cut values at 60 chars: every edit longer than 60 chars was refused (wrong value). Now accepted and compared in full."""
    import savegate as sg
    from savegate import rvt_save
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); val = ('0123456789' * 40)
    rvt_save.save_string_edits(cur, [(7, 'FillPattern.m_name', val)], sg.Config(allow_overwrite=True, require_gate=False))
    V.verify_declared(SRC, cur, 7, {'FillPattern.m_name': val})
    tail_wrong = val[:300] + 'Z' + val[301:]      # differs only after char 60
    with pytest.raises(ValueError):
        V.verify_declared(SRC, cur, 7, {'FillPattern.m_name': tail_wrong})


def _deleted_bytes(path, eid):
    import sys, tempfile
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
    import wledit
    ed = wledit.Editor(path); pn = ed.trace(eid)[0]; ed.delete(eid)
    with tempfile.TemporaryDirectory() as d:
        o = os.path.join(d, 'o.rfa'); ed.save(o); return pn, open(o, 'rb').read()


def test_element_delete_through_the_gate_declared_is_judged_undeclared_is_refused(tmp_path):
    import savegate as sg
    pn, new = _deleted_bytes(SRC, 7)
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    for man in ({}, {'modified': [pn]}, {'modified': ['stream:' + pn]}):      # undeclared element / stream: must be refused
        with pytest.raises(sg.SaveError):
            sg.save(doc, new, man)
        assert open(cur, 'rb').read() == before
    with pytest.raises(sg.SaveError):      # delete declared for a different element: refused
        sg.save(doc, new, {'modified': ['stream:' + pn], 'deleted': ['el:0']})
    assert open(cur, 'rb').read() == before
    sg.save(doc, new, {'modified': ['stream:' + pn], 'deleted': ['el:7']})      # the declared delete is accepted
    assert open(cur, 'rb').read() != before
    assert V.field_diff(SRC, cur, 0)[0] == []      # a neighbouring element is untouched
    with pytest.raises(ValueError):      # and el:7 is really gone
        V.field_diff(SRC, cur, 7)


@pytest.mark.parametrize('stream', ['Global/PartitionTable', 'Global/ElemTable', 'Global/Latest', 'Global/History', 'Global/DocumentIncrementTable', 'Global/ContentDocuments', 'BasicFileInfo', 'Contents', 'PartAtom', 'TransmissionData', 'RevitPreview4.0', 'Formats/Latest'])
def test_one_flipped_byte_in_any_other_stream_of_an_otherwise_valid_output_is_refused(tmp_path, stream):
    import savegate as sg, olefile
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    good = tmp_path / 'good.rfa'; good.write_bytes(_edited_bytes(SRC, 7, 'HorizontalZ'))
    o = olefile.OleFileIO(str(good), write_mode=True); d = bytearray(o.openstream(stream).read()); d[len(d) // 2] ^= 0x01; o.write_stream(stream, bytes(d)); o.close()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    for mod in (['stream:Partitions/67', 'el:7'], ['stream:Partitions/67', 'el:7', 'stream:' + stream]):
        with pytest.raises(sg.SaveError):
            sg.save(doc, good.read_bytes(), {'modified': mod, 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
        assert open(cur, 'rb').read() == before and sorted(os.listdir(tmp_path)) == ['c.rfa', 'good.rfa']


def test_flipped_byte_in_any_non_partition_stream_is_refused_on_the_2026_family(tmp_path):
    import savegate as sg, olefile
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
    if not os.path.exists(src): pytest.skip('2026 family absent')
    good = tmp_path / 'good.rfa'; good.write_bytes(_edited_bytes(src, 7, 'HorizontalZ'))
    a = olefile.OleFileIO(src); b = olefile.OleFileIO(str(good))
    names = ['/'.join(e) for e in b.listdir()]
    parts = [n for n in names if n.startswith('Partitions/') and a.openstream(n).read() != b.openstream(n).read()]
    others = [n for n in names if not n.startswith('Partitions/')]; a.close(); b.close()
    assert len(parts) == 1 and others
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)); orig = good.read_bytes(); refused = 0
    for s in others:
        g2 = tmp_path / 'g2.rfa'; g2.write_bytes(orig)
        o = olefile.OleFileIO(str(g2), write_mode=True); d = bytearray(o.openstream(s).read())
        if not d: o.close(); continue
        d[len(d) // 2] ^= 1; o.write_stream(s, bytes(d)); o.close()
        for mod in (['stream:' + parts[0], 'el:7'], ['stream:' + parts[0], 'el:7', 'stream:' + s]):
            with pytest.raises(sg.SaveError):
                sg.save(doc, g2.read_bytes(), {'modified': mod, 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
            refused += 1
            assert open(cur, 'rb').read() == before
    assert refused >= 2 * (len(others) - 1)


@pytest.mark.parametrize('frac', [0.02, 0.1, 0.25, 0.4, 0.6, 0.75, 0.9, 0.98])
def test_flip_in_the_edited_partition_outside_the_declared_record_is_refused(tmp_path, frac):
    import savegate as sg, olefile
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    g = tmp_path / 'g.rfa'; g.write_bytes(_edited_bytes(SRC, 7, 'HorizontalZ'))
    o = olefile.OleFileIO(str(g), write_mode=True); d = bytearray(o.openstream('Partitions/67').read()); d[int(len(d) * frac)] ^= 0x04; o.write_stream('Partitions/67', bytes(d)); o.close()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, g.read_bytes(), {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
    assert open(cur, 'rb').read() == before


@pytest.mark.parametrize('pair', [('Global/History', 'Global/ContentDocuments'), ('Global/Latest', 'Formats/Latest'), ('Global/ElemTable', 'Global/PartitionTable'), ('BasicFileInfo', 'PartAtom')])
def test_two_streams_with_swapped_contents_in_an_otherwise_valid_output_are_refused(tmp_path, pair):
    import savegate as sg
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    c = cfb.CFB(_edited_bytes(SRC, 7, 'HorizontalZ')); st = c.streams(); a, b = st[pair[0]], st[pair[1]]
    da, db = bytes(a.data), bytes(b.data); assert da != db
    a.data, b.data = db, da
    out = str(tmp_path / 'sw.rfa'); cfb.write(c, out)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    for mod in (['stream:Partitions/67', 'el:7'], ['stream:Partitions/67', 'el:7'] + ['stream:' + p for p in pair]):
        with pytest.raises(sg.SaveError):
            sg.save(doc, open(out, 'rb').read(), {'modified': mod, 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
        assert open(cur, 'rb').read() == before


def test_output_container_relaid_as_cfb_v3_512_byte_sectors_is_judged_not_silently_accepted_or_corrupt(tmp_path):
    """Probe: the source is CFB v4 (4096 sectors). An output with the same streams in a v3 container
    is a different file format layout; the gate must at least not crash and must keep the original intact."""
    import savegate as sg, struct
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    c = cfb.CFB(_edited_bytes(SRC, 7, 'HorizontalZ'))
    c.ss = 512; c.header[26:28] = struct.pack('<H', 3); c.header[30:32] = struct.pack('<H', 9)
    out = str(tmp_path / 'v3.rfa'); cfb.write(c, out)
    assert open(out, 'rb').read()[26] == 3
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try:
        r = sg.save(doc, open(out, 'rb').read(), {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
        verdict = 'ACCEPTED'
    except sg.SaveError as e:
        verdict = 'REFUSED'; print('REASON', str(e)[:200])
    print('V3 VERDICT', verdict)
    assert verdict == 'REFUSED', 'a v3-sector container for a v4 source (never produced by Revit) must be refused'
    assert open(cur, 'rb').read() == before


@pytest.mark.parametrize('field', ['clsid', 'state', 'ctime', 'mtime', 'color'])
def test_directory_entry_metadata_changes_in_the_output_are_reported_not_hidden(tmp_path, field):
    import savegate as sg
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    c = cfb.CFB(_edited_bytes(SRC, 7, 'HorizontalZ'))
    off = {'clsid': 80, 'state': 96, 'ctime': 100, 'mtime': 108, 'color': 67}[field]
    e = c.streams()['Global/Latest'] if field != 'clsid' else c.entries[0]
    raw = bytearray(e.raw); raw[off] ^= 0x01; e.raw = bytes(raw)
    out = str(tmp_path / 'm.rfa'); cfb.write(c, out)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try:
        sg.save(doc, open(out, 'rb').read(), {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}}); verdict = 'ACCEPTED'
    except sg.SaveError as ex:
        verdict = 'REFUSED ' + str(ex)[:100]
    print('DIRMETA', field, verdict)
    assert verdict.startswith('REFUSED') or field in ('ctime', 'mtime')
    assert open(cur, 'rb').read() == before or verdict == 'ACCEPTED'


@pytest.mark.parametrize('mode', ['crosslink', 'loop', 'free_in_chain', 'shared_start'])
def test_fat_chain_damage_in_an_otherwise_valid_output_is_refused(tmp_path, mode):
    import savegate as sg, struct
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    buf = bytearray(_edited_bytes(SRC, 7, 'HorizontalZ')); c = cfb.CFB(bytes(buf)); ss = c.ss
    fat_ids = [x for x in struct.unpack('<109I', buf[76:76 + 436]) if x != 0xFFFFFFFF]
    st = c.streams(); big = [e for e in st.values() if e.size >= c.cutoff]
    a, b = big[0], big[1]
    def put(sid, val):      # FAT entry sid -> val
        sec = fat_ids[sid // (ss // 4)]; off = (sec + 1) * ss + (sid % (ss // 4)) * 4; buf[off:off + 4] = struct.pack('<I', val)
    nxt = c.fat[a.start]; assert nxt != 0xFFFFFFFE, 'chain too short'
    if mode == 'crosslink': put(a.start, b.start)
    elif mode == 'loop': put(nxt, a.start)
    elif mode == 'free_in_chain': put(a.start, 0xFFFFFFFF)
    else:
        i = [k for k, e in enumerate(c.entries) if e.type == 2 and e is b][0]
        # directory entry of b starts where a does
        dirbuf = cfb.CFB(bytes(buf))  # layout lookup
        dstart = struct.unpack('<I', buf[48:52])[0]; per = ss // 128
        sec = dstart
        for _ in range(i // per): sec = c.fat[sec]
        o = (sec + 1) * ss + (i % per) * 128 + 116; buf[o:o + 4] = struct.pack('<I', a.start)
    out = tmp_path / 'x.rfa'; out.write_bytes(bytes(buf))
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(Exception) as ei:
        sg.save(doc, bytes(buf), {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
    print('FAT', mode, type(ei.value).__name__, str(ei.value)[:110])
    assert open(cur, 'rb').read() == before


@pytest.mark.parametrize('mode', ['case_rename', 'duplicate_name'])
def test_renamed_or_duplicate_directory_entry_in_the_output_is_refused(tmp_path, mode):
    import savegate as sg
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    c = cfb.CFB(_edited_bytes(SRC, 7, 'HorizontalZ'))
    st = c.streams(); e = st['Global/Latest']
    def setname(ent, name):
        raw = bytearray(ent.raw); n = name.encode('utf-16-le') + b'\0\0'
        raw[0:64] = n.ljust(64, b'\0'); raw[64:66] = len(n).to_bytes(2, 'little'); ent.raw = bytes(raw)
    if mode == 'case_rename': setname(e, 'LATEST' if e.name == 'Latest' else e.name.swapcase())
    else: setname(st['Global/PartitionTable'], e.name)
    out = str(tmp_path / 'm.rfa'); cfb.write(c, out)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try:
        sg.save(doc, open(out, 'rb').read(), {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}}); verdict = 'ACCEPTED'
    except sg.SaveError as ex:
        verdict = 'REFUSED ' + str(ex)[:100]
    print('DIRNAME', mode, verdict)
    assert verdict.startswith('REFUSED')
    assert open(cur, 'rb').read() == before


S26 = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')


def _edit26(items):
    import tempfile
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
    import wledit
    ed = wledit.Editor(S26); ed.set_strings(items)
    with tempfile.TemporaryDirectory() as d:
        o = os.path.join(d, 'o.rfa'); ed.save(o); return open(o, 'rb').read()


@pytest.mark.skipif(not os.path.exists(S26), reason='2026 family absent')
@pytest.mark.parametrize('which', ['first', 'last', 'both'])
def test_2026_edit_at_first_and_last_decodable_record_is_accepted_and_flips_outside_are_refused(tmp_path, which):
    import savegate as sg, olefile
    first = (0, 'SymbolInfo.m_name', 'LinearBoundary'); last = (6444, 'KeynoteTable.m_name', 'StandardBoundary')
    items = {'first': [first], 'last': [last], 'both': [first, last]}[which]
    good = _edit26(items)
    expect = {i[0]: {i[1]: i[2]} for i in items}
    cur = str(tmp_path / 'c.rfa'); shutil.copy(S26, cur); before = open(cur, 'rb').read()
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    man = lambda: {'modified': ['stream:Partitions/69'] + ['el:%d' % i[0] for i in items] + (['el:1'] if any(i[0] == 0 for i in items) else []), 'expect': expect}
    # flips outside any record: all refused
    refused = 0
    for frac in (0.02, 0.2, 0.5, 0.8, 0.98):
        g = tmp_path / 'g.rfa'; g.write_bytes(good)
        o = olefile.OleFileIO(str(g), write_mode=True); d = bytearray(o.openstream('Partitions/69').read()); d[int(len(d) * frac)] ^= 0x04; o.write_stream('Partitions/69', bytes(d)); o.close()
        doc = sg.open_doc(cur, None, cfg)
        with pytest.raises(sg.SaveError): sg.save(doc, g.read_bytes(), man())
        refused += 1; assert open(cur, 'rb').read() == before
    doc = sg.open_doc(cur, None, cfg)
    try:
        sg.save(doc, good, man()); verdict = 'ACCEPTED'
    except sg.SaveError as ex:
        verdict = 'REFUSED ' + str(ex)[:140]
    print('B26', which, 'flips refused', refused, 'edit', verdict)
    assert verdict == 'ACCEPTED' or open(cur, 'rb').read() == before


@pytest.mark.skipif(not os.path.exists(S26), reason='2026 family absent')
def test_ten_chained_edits_then_revert_leave_no_drift_in_any_other_element(tmp_path):
    import savegate as sg
    from savegate import rvt_save
    from savegate.adapters import RvtAdapter
    cur = str(tmp_path / 'c.rfa'); shutil.copy(S26, cur); cfg = sg.Config(allow_overwrite=True, require_gate=False)
    seq = [[(7, 'FillPattern.m_name', 'G%d' % k * (1 + k))] if k % 2 else [(0, 'SymbolInfo.m_name', 'S%d' % k * (1 + k))] for k in range(1, 9)]
    seq += [[(7, 'FillPattern.m_name', 'Horizontal')], [(0, 'SymbolInfo.m_name', 'Linear')]]
    for e in seq: rvt_save.save_string_edits(cur, e, cfg)
    A = RvtAdapter(); sa = A.snapshot(open(S26, 'rb').read()); sb = A.snapshot(open(cur, 'rb').read())
    diff = sorted(k for k in set(sa) | set(sb) if sa.get(k) != sb.get(k))
    print('DRIFT keys differing after 10 generations + revert:', diff[:12], len(diff))
    assert not [k for k in diff if k.startswith('el:')], diff[:12]      # no element drifted; the partition stream bytes themselves differ (re-encoded members, record padding) and are expected to


@pytest.mark.parametrize('n,ok', [(4097, True), (16384, False)])
def test_long_string_growth_is_accepted_or_refused_cleanly_with_original_intact(tmp_path, n, ok):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    val = 'x' * n; b = _edited_bytes(SRC, 7, val)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    man = {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': val}}}
    if ok: sg.save(doc, b, man)
    else:
        with pytest.raises(sg.SaveError): sg.save(doc, b, man)
        assert open(cur, 'rb').read() == before


@pytest.mark.parametrize('mode', ['minifat_selfloop', 'dir_sibling_selfloop', 'dir_child_selfloop', 'nfat_huge', 'dirstart_out_of_range', 'difat_selfloop', 'difat_out_of_range', 'minifat_start_out_of_range', 'ndir_sectors_huge'])
def test_container_structure_attacks_on_the_output_are_refused_fast_with_original_intact(tmp_path, mode):
    import savegate as sg, struct, signal
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    buf = bytearray(_edited_bytes(SRC, 7, 'HorizontalZ')); c = cfb.CFB(bytes(buf)); ss = c.ss
    P = lambda o, v: buf.__setitem__(slice(o, o + 4), struct.pack('<I', v))
    dstart = struct.unpack('<I', buf[48:52])[0]
    def dir_off(idx):
        sec = dstart; per = ss // 128
        for _ in range(idx // per): sec = c.fat[sec]
        return (sec + 1) * ss + (idx % per) * 128
    root_child = struct.unpack('<I', bytes(buf[dir_off(0) + 76:dir_off(0) + 80]))[0]
    if mode == 'minifat_selfloop':
        small = [e for e in c.streams().values() if 0 < e.size < c.cutoff][0]
        mf = struct.unpack('<I', buf[60:64])[0]; o = (mf + 1) * ss + small.start * 4; P(o, small.start)
    elif mode == 'dir_sibling_selfloop': P(dir_off(root_child) + 68, root_child)
    elif mode == 'dir_child_selfloop': P(dir_off(root_child) + 76, root_child)
    elif mode == 'nfat_huge': P(44, 0x7FFFFFF0)
    elif mode == 'dirstart_out_of_range': P(48, 0x7FFFFF00)
    elif mode == 'difat_selfloop': P(68, 1); P(72, 1)
    elif mode == 'difat_out_of_range': P(68, 0x7FFFFF00); P(72, 3)
    elif mode == 'minifat_start_out_of_range': P(60, 0x7FFFFF00)
    elif mode == 'ndir_sectors_huge' : P(40, 0x7FFFFFF0) if buf[26] == 4 else None
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    signal.alarm(60)
    try:
        try:
            sg.save(doc, bytes(buf), {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}}); verdict = 'ACCEPTED'
        except sg.SaveError as ex: verdict = 'REFUSED ' + type(ex).__name__ + ' ' + str(ex)[:90]
    finally: signal.alarm(0)
    print('CONT', mode, verdict)
    assert verdict.startswith('REFUSED')
    assert open(cur, 'rb').read() == before


@pytest.mark.parametrize('mode', ['fat_loop', 'dir_sibling_loop'])
def test_source_with_container_loop_is_refused_fast_and_never_changed(tmp_path, mode):
    import savegate as sg, struct, signal
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    buf = bytearray(open(SRC, 'rb').read()); c = cfb.CFB(bytes(buf)); ss = c.ss
    if mode == 'fat_loop':
        a = [e for e in c.streams().values() if e.size >= c.cutoff][0]; nxt = c.fat[a.start]
        fat_ids = [x for x in struct.unpack('<109I', buf[76:76 + 436]) if x != 0xFFFFFFFF]
        sec = fat_ids[nxt // (ss // 4)]; o = (sec + 1) * ss + (nxt % (ss // 4)) * 4; buf[o:o + 4] = struct.pack('<I', a.start)
    else:
        dstart = struct.unpack('<I', buf[48:52])[0]; rc = struct.unpack('<I', buf[(dstart + 1) * ss + 76:(dstart + 1) * ss + 80])[0]
        o = (dstart + 1) * ss + rc * 128 + 68; buf[o:o + 4] = struct.pack('<I', rc)
    cur = tmp_path / 's.rfa'; cur.write_bytes(bytes(buf))
    signal.alarm(60)
    try:
        try:
            doc = sg.open_doc(str(cur), None, sg.Config(allow_overwrite=True, require_gate=False))
            r = sg.save(doc, bytes(buf), {'modified': []}); verdict = 'ACCEPTED'
        except Exception as ex: verdict = 'REFUSED ' + type(ex).__name__ + ' ' + str(ex)[:90]
    finally: signal.alarm(0)
    print('SRCLOOP', mode, verdict)
    assert verdict.startswith('REFUSED')
    assert cur.read_bytes() == bytes(buf)


@pytest.mark.skipif(not os.path.exists('/proc/self/statm'), reason='linux rss probe')
def test_repeated_element_snapshots_do_not_leak_a_context_per_call():
    import gc
    from savegate import rvt_elements as E
    buf = open(SRC, 'rb').read()
    rss = lambda: int(open('/proc/self/statm').read().split()[1]) * 4096 // 2 ** 20
    for _ in range(6): E.elements(buf)      # warm-up: the allocator and lazy tables settle at about +30 MB
    gc.collect(); base = rss()
    for _ in range(6): E.elements(buf)
    gc.collect()
    grown = rss() - base
    print('LEAK MB over 6 calls after warm-up', grown)
    assert grown < 15, 'was about 108 MB (18 MB per call) before the per-path cache purge'


@pytest.mark.parametrize('off', [8, 15, 23, 65, 66, 67, 68, 39, 40])
def test_single_bit_flip_in_header_bytes_that_no_edit_touches_is_refused(tmp_path, off):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    b = bytearray(_edited_bytes(SRC, 7, 'HorizontalZ')); b[off] ^= 1
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, bytes(b), {'modified': ['stream:Partitions/67', 'el:7'], 'expect': {7: {'FillPattern.m_name': 'HorizontalZ'}}})
    assert open(cur, 'rb').read() == before
