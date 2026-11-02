"""c4x-rvtgap (queue 91): reference integration for the app. save_string_edits() builds the edit with the writer lab, derives the manifest (declared partitions,
element ids, expected field values) and saves through the gate. Anything raised leaves the original untouched."""
import os, sys, tempfile


def save_string_edits(path, edits, cfg=None, dest=None):
    """edits: [(element id, field name, new text)]. Overwrites `path` (or writes `dest` via save_as). Returns the gate's report."""
    import savegate as sg
    lib = os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
    for p in (lib, os.path.dirname(lib)):
        if p not in sys.path: sys.path.insert(0, p)
    # c4x-dwgreadfuzz 207: audit the container BEFORE the writer lab parses it (FAT loops, cross-linked chains, directory cycles reach the editor otherwise)
    if not (cfg is not None and getattr(cfg, 'allow_damaged_edit', False)):
        import rvt_integrity
        bad = rvt_integrity.audit(path)
        if bad:
            raise sg.VerifyFailed('the SOURCE file is damaged (%d container problem(s), first: %s %s); nothing was edited or written.' % (len(bad), bad[0][0], bad[0][1]), dict(source_damage=[list(x) for x in bad[:20]]))
    import wledit
    ed = wledit.Editor(path)
    parts = set(); expect = {}
    for eid, fld, txt in edits:
        parts.add(ed.trace(eid)[0]); expect.setdefault(eid, {})[fld] = txt
    ed.set_strings(list(edits))
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'out.rvt'); ed.save(out); new = open(out, 'rb').read()
    man = {'modified': sorted('stream:' + p for p in parts) + ['el:%d' % e for e in sorted(expect)], 'expect': expect}
    doc = sg.open_doc(path, None, cfg)
    return (sg.save_as(doc, new, dest, man) if dest else sg.save(doc, new, man))


_MSG = {
    'Conflict': 'The file changed on disk since it was opened. Nothing was saved. Reload it and repeat the edit.',
    'VerifyFailed': 'The edited file failed the safety check, so the original was NOT touched. Use Save As to write a copy, or report this file.',
    'UnsupportedVersion': 'This Revit version cannot be saved in place. Open it in Revit and Save As a supported year.',
    'GateClosed': 'Saving over the original is switched off. Use Save As.',
    'OverwriteDisabled': 'Saving over the original is switched off. Use Save As.',
    'Locked': 'Another save of this file is running. Nothing was written; try again in a moment.',
    'DiskError': 'The disk refused the write (full, read-only or name too long). The original is unchanged.',
    'Exists': 'A file with that name already exists. Nothing was written.',
    'HardlinkTarget': 'The file has other hard links; saving over it would detach them. Use Save As.',
    'ReadOnlyTarget': 'The file is read-only. Nothing was written.',
}


def user_message(exc):
    """text for the user for any exception from the gate; an unknown exception is reported as a refusal, never as success"""
    name = type(exc).__name__
    base = _MSG.get(name, 'The save failed (%s). The original was not touched.' % name)
    return base + (' Detail: ' + str(exc)[:300] if str(exc) else '')
