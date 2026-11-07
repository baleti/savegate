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
    ox, oy, oz = struct.unpack_from('<3d', rec, o0); _shift_leaders(T, rec, x - ox, y - oy)
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


LEADER_FIELDS = ('Leader.m_end', 'Leader.m_elbow', 'Leader.m_anchor')


def _shift_leaders(T, rec, dx, dy):
    """leader points of a text note are stored in the same view coordinates as TextElement.m_orig (absolute): they move with the note"""
    for n, o, e, _ in T['log']:
        if n in LEADER_FIELDS and e - o == 24:
            v = struct.unpack_from('<3d', rec, o); struct.pack_into('<3d', rec, o, v[0] + dx, v[1] + dy, v[2])


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
        elif o['op'] == 'move_textnote':
            _move_textnote(g, int(o['id']), float(o.get('dx', 0)), float(o.get('dy', 0)))
        elif o['op'] == 'resize_wall':
            _resize_wall(g, int(o['id']), o.get('height'), o.get('length_delta'))
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


WALL_USER_HEIGHT = -1001105          # BuiltInParameter.WALL_USER_HEIGHT_PARAM (Unconnected Height)


def _resize_wall(g, tid, height=None, length_delta=None):
    """RESIZE a straight wall (axis-aligned: its location line runs along x or y). height = new unconnected height (ft): the parameter value -1001105, the top (v1) of the Envelope.m_corners of
    every face plane, and the z top of the header bounding box (zmin + height) change together. length_delta = change of the end parameter (ft, end side): GCurve.m_endParams[1], u1 of every
    envelope and the header bounding box along the wall direction. Joins, hosted openings and other dependents are NOT touched."""
    W = 8; T = g.template(tid); rec = bytearray(T['rec']); log = T['log']
    env = [o for n, o, e, _ in log if n == 'Envelope.m_corners']
    if not env: raise ValueError('element %d has no face envelopes (not a wall?)' % tid)
    ep = [o for n, o, e, _ in log if n == 'GCurve.m_endParams']; gl = [o for n, o, e, _ in log if n == 'GLine.m_dirVec']
    d = struct.unpack_from('<3d', rec, gl[0]) if gl else (1.0, 0.0, 0.0)
    if abs(d[2]) > 1e-9 or (abs(abs(d[0]) - 1) > 1e-9 and abs(abs(d[1]) - 1) > 1e-9): raise ValueError('only walls along x or y are supported (direction %s)' % (d,))
    hdr = bytearray(T['hdr']); hl = {n: (o, e) for n, o, e, _ in T['hlog']}; a = hl['Outline.m_minmax'][0]; mm = list(struct.unpack_from('<6d', hdr, a))
    if height is not None:
        h = float(height); last = None; done = 0
        for n, o, e, _ in log:
            if n == 'ParamValueDouble.m_paramId': last = struct.unpack_from('<q', rec, o)[0]
            elif n == 'ParamValueDouble.m_value' and last == WALL_USER_HEIGHT: struct.pack_into('<d', rec, o, h); done += 1
        if done != 1: raise ValueError('wall height parameter %d found %d times' % (WALL_USER_HEIGHT, done))
        for o in env: c = list(struct.unpack_from('<4d', rec, o)); c[3] = h; struct.pack_into('<4d', rec, o, *c)
        mm[5] = mm[2] + h
    if length_delta is not None:
        dl = float(length_delta)
        if not ep: raise ValueError('wall has no GCurve.m_endParams')
        p0, p1 = struct.unpack_from('<2d', rec, ep[0]); struct.pack_into('<2d', rec, ep[0], p0, p1 + dl)
        for o in env: c = list(struct.unpack_from('<4d', rec, o)); c[2] += dl; struct.pack_into('<4d', rec, o, *c)
        ax = 0 if abs(d[0]) > 0.5 else 1; sign = d[ax]
        if sign > 0: mm[3 + ax] += dl
        else: mm[ax] -= dl
    struct.pack_into('<6d', hdr, a, *mm)
    g.replace_existing(tid, hdr=bytes(hdr), rec=bytes(rec))


def _move_textnote(g, tid, dx, dy):
    """MOVE a TextNote in its view (feet, view coordinates): TextElement.m_orig and every leader point (end, elbow, anchor) move together; leader extension points are note-relative and stay.
    Annotations carry no header bounding box and no zone coordinates."""
    T = g.template(tid); rec = bytearray(T['rec']); o0 = [o for n, o, e, _ in T['log'] if n == 'TextElement.m_orig']
    if not o0: raise ValueError('element %d is not a text note' % tid)
    v = struct.unpack_from('<3d', rec, o0[0]); struct.pack_into('<3d', rec, o0[0], v[0] + dx, v[1] + dy, v[2]); _shift_leaders(T, rec, dx, dy)
    g.replace_existing(tid, rec=bytes(rec))
