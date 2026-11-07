"""c5x-rvtgap: the trusted writer operations for RVT-EDIT rungs 2/3, built on the write lab's rvtgen.Gen (deterministic, Revit-validated in the lab). Used by the producer (the app) and by
RvtAdapter.verify_writer_ops, which recomputes the result from the source and demands byte equality. ops = [{'op': 'delete', 'id': N},
{'op': 'add_textnote', 'template': TID, 'x': .., 'y': .., 'text': '..'}, ...]; run() returns the list of new element ids."""
import os, sys, struct


def _lab():
    wl = os.environ.get('SAVEGATE_RVT_WRITELAB') or os.path.expanduser('~/rvt-research/write-lab')
    for p in (wl, os.path.dirname(wl)):
        if p not in sys.path: sys.path.insert(0, p)


def make_textnote_rtf(g, T, nid, x, y, text, z=0.0):
    """clone a TextNote whose text lives in the rich-text stream only (empty fragment array, as in 2024 project files) with a new id, position and text"""
    _lab(); from genlib2 import rep, setphase, restamp
    W = 8; L = {n: (o, e) for n, o, e, _ in T['log']}; idb = nid.to_bytes(W, 'little'); rec = bytearray(T['rec'])
    f0, f1 = L['TextElement.m_arrTextFragments']
    if not (struct.unpack_from('<I', rec, f0)[0] == 0 and f1 - f0 == 4): raise ValueError('template text note has text fragments (only rich-text-only notes are supported)')
    rt0, rt1 = L['RtfData.m_arrRtfStream']; o0 = L['TextElement.m_orig'][0]
    rec[4:12] = idb; rec[L['Element.m_id'][0]:L['Element.m_id'][1]] = idb; struct.pack_into('<3d', rec, o0, x, y, z)
    rtf = bytes(rec[rt0 + 4:rt1]); i = rtf.index(b'\\fs') + 3
    while rtf[i:i + 1].isdigit(): i += 1
    i += 1; j = rtf.rindex(b'\\par')
    new = rtf[:i] + text.encode('cp1252', errors='replace').replace(b'\\', b'\\\\') + rtf[j:]
    rec = bytearray(rec[:rt0] + struct.pack('<I', len(new)) + new + rec[rt1:])
    hdr = bytearray(T['hdr']); hdr[0:W] = idb
    item = bytearray(T['item']); rep(item, T['tid'].to_bytes(W, 'little'), idb)
    rec = bytearray(g.stamp(bytes(rec))); setphase(hdr); setphase(rec); rec = g.stamp(bytes(rec)); setphase(item); item = restamp(bytes(item), W)
    return bytes(hdr), bytes(rec), bytes(item)


def run(src_path, ops, dst_path):
    _lab(); import rvtgen
    g = rvtgen.Gen(src_path); new_ids = []
    for o in ops:
        if o['op'] == 'delete': g.delete(int(o['id']))
        elif o['op'] == 'add_textnote':
            T = g.template(int(o['template'])); nid = g.nextid
            hdr, rec, item = make_textnote_rtf(g, T, nid, float(o['x']), float(o['y']), str(o['text']), float(o.get('z', 0.0)))
            row = bytearray(T['row']); idb = struct.pack('<Q', nid); row[0:8] = idb; row[20:28] = idb
            et = g._et(); n_ = struct.unpack_from('<I', et, 2)[0]
            best = max(range(n_), key=lambda k: (struct.unpack_from('<I', et, 6 + 40 * k + 12)[0], struct.unpack_from('<I', et, 6 + 40 * k + 8)[0]))
            ea, eb, _ = struct.unpack_from('<3I', et, 6 + 40 * best + 8); struct.pack_into('<3I', row, 8, ea, eb, eb)
            g.new.append((hdr, rec, item, nid)); g.rows.append(bytes(row)); g.nextid = nid + 1; new_ids.append(nid)
        else: raise ValueError('unknown writer op %r' % o.get('op'))
    g.commit(dst_path)
    return new_ids
