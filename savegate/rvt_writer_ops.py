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
        elif o['op'] in ('move_instance', 'move_element'):
            _move_instance(g, int(o['id']), (float(o.get('dx', 0)), float(o.get('dy', 0)), float(o.get('dz', 0))))
        elif o['op'] == 'rotate_instance':
            _rotate_instance(g, int(o['id']), float(o['deg']))
        else: raise ValueError('unknown writer op %r' % o.get('op'))
    g.commit(dst_path)
    return new_ids


MOVE_FIELDS = ('Trf.m_or', 'Plane.m_origin', 'GLine.m_origin')


def _move_instance(g, tid, d):
    """MOVE an element (instance, wall, grid, level, ...): every stored copy of its position moves together: all Trf.m_or / Plane.m_origin / GLine.m_origin triples (and m_instOrigin when set) in the
    record, Outline.m_minmax (bounding box) in the header entry when it has one, and the (x, y) pairs of the zone record that equal the first origin. Same-size edits; restamped (record
    Adler32 via the lab's stamp, zone item via restamp)."""
    _lab(); from genlib import restamp
    import rvtgen
    W = 8; T = g.template(tid); Lc = g.locate(tid); pt = g.pt
    rec = bytearray(T['rec']); first = None
    for n, o, e, _ in T['log']:
        if n in MOVE_FIELDS and e - o == 24:
            v = struct.unpack_from('<3d', rec, o); first = first or v
            struct.pack_into('<3d', rec, o, v[0] + d[0], v[1] + d[1], v[2] + d[2])
        elif n == 'FamilyInstance.m_instOrigin':
            v = struct.unpack_from('<3d', rec, o)
            if any(v): struct.pack_into('<3d', rec, o, v[0] + d[0], v[1] + d[1], v[2] + d[2])
    if first is None: raise ValueError('element %d has no movable origin field (%s)' % (tid, ', '.join(MOVE_FIELDS)))
    ox, oy, oz = first
    hdr = bytearray(T['hdr']); hl = {n: (o, e) for n, o, e, _ in T['hlog']}
    if 'Outline.m_minmax' in hl:
        a = hl['Outline.m_minmax'][0]; mm = struct.unpack_from('<6d', hdr, a)
        struct.pack_into('<6d', hdr, a, mm[0] + d[0], mm[1] + d[1], mm[2] + d[2], mm[3] + d[0], mm[4] + d[1], mm[5] + d[2])
    item = bytearray(T['item']); n_pairs = 0
    for off in range(0, len(item) - 16):
        if struct.unpack_from('<d', item, off)[0] == ox and struct.unpack_from('<d', item, off + 8)[0] == oy:
            struct.pack_into('<2d', item, off, ox + d[0], oy + d[1]); n_pairs += 1
    g.replace_existing(tid, hdr=bytes(hdr), rec=bytes(rec))
    if n_pairs:
        new_item = restamp(bytes(item), W); bj = g.bj
        assert len(new_item) == len(T['item'])
        for (st, ln) in Lc['zone']:
            if bytes(bj[st + 4:st + 4 + len(T['item'])]) == T['item']:
                g.edits = getattr(g, 'edits', []) + [(st + 4 + 0.5, lambda st=st, ni=new_item: pt.replace(st + 4, len(ni), ni))]
                break
        else: raise ValueError('zone record of element %d not found' % tid)


def _rotate_instance(g, tid, deg):
    """ROTATE a FamilyInstance about its own origin (Trf.m_or) around the Z axis by deg degrees (counter-clockwise, applied to the world-side of the stored 3x3: new = Rz * M column by column):
    Trf.m_3x3 and FamilyInstance.m_RefDir in the record, Outline.m_minmax in the header entry becomes the box of the four rotated corners (z unchanged). The origin, m_zAxis and the zone
    record do not change. Sign/transposition convention of the stored matrix is verified only by the Revit VM."""
    import math
    W = 8; T = g.template(tid); rec = bytearray(T['rec']); L = {n: (o, e) for n, o, e, _ in T['log']}
    c, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    def rz(v): return (c * v[0] - s_ * v[1], s_ * v[0] + c * v[1], v[2])
    ox, oy, oz = struct.unpack_from('<3d', rec, L['Trf.m_or'][0])
    o3 = L['Trf.m_3x3'][0]; M = struct.unpack_from('<9d', rec, o3)
    cols = [rz((M[0], M[3], M[6])), rz((M[1], M[4], M[7])), rz((M[2], M[5], M[8]))]
    struct.pack_into('<9d', rec, o3, cols[0][0], cols[1][0], cols[2][0], cols[0][1], cols[1][1], cols[2][1], cols[0][2], cols[1][2], cols[2][2])
    r0 = L['FamilyInstance.m_RefDir'][0]; struct.pack_into('<3d', rec, r0, *rz(struct.unpack_from('<3d', rec, r0)))
    hdr = bytearray(T['hdr']); hl = {n: (o, e) for n, o, e, _ in T['hlog']}
    if 'Outline.m_minmax' in hl:
        a = hl['Outline.m_minmax'][0]; mm = struct.unpack_from('<6d', hdr, a)
        pts = [rz((x - ox, y - oy, 0.0)) for x in (mm[0], mm[3]) for y in (mm[1], mm[4])]
        xs = [ox + p[0] for p in pts]; ys = [oy + p[1] for p in pts]
        struct.pack_into('<6d', hdr, a, min(xs), min(ys), mm[2], max(xs), max(ys), mm[5])
    g.replace_existing(tid, hdr=bytes(hdr), rec=bytes(rec))
