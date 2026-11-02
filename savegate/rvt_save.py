"""c4x-rvtgap (queue 91): reference integration for the app. save_string_edits() builds the edit with the writer lab, derives the manifest (declared partitions,
element ids, expected field values) and saves through the gate. Anything raised leaves the original untouched."""
import os, sys, tempfile


def save_string_edits(path, edits, cfg=None, dest=None):
    """edits: [(element id, field name, new text)]. Overwrites `path` (or writes `dest` via save_as). Returns the gate's report."""
    import savegate as sg
    lib = os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
    for p in (lib, os.path.dirname(lib)):
        if p not in sys.path: sys.path.insert(0, p)
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
