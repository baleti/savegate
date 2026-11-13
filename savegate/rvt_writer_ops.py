"""c5x-rvtgap: the trusted writer operations for RVT-EDIT rungs 2/3, built on the write lab's rvtgen.Gen (deterministic, Revit-validated in the lab). Used by the producer (the app) and by
RvtAdapter.verify_writer_ops, which recomputes the result from the source and demands byte equality. ops = [{'op': 'delete', 'id': N},
{'op': 'add_textnote', 'template': TID, 'x': .., 'y': .., 'text': '..'}, ...]; run() returns the list of new element ids."""
import re
import os, sys, struct


def _lab():
    wl = os.environ.get('SAVEGATE_RVT_WRITELAB') or os.path.expanduser('~/rvt-research/write-lab')
    for p in (wl, os.path.dirname(wl)):
        if p not in sys.path: sys.path.insert(0, p)


def _rtf_escape(text):
    """c7x-rvtread2 item 383: text for the body of the RTF stored in a TextNote. Backslash and the group braces are escaped (an unescaped } used to close the RTF document early),
    control characters (NUL, CR, LF, ...) are refused, anything outside cp1252 becomes a \\uN? escape (it used to be replaced by '?' silently), lone surrogates are refused."""
    out = bytearray()
    for ch in text:
        c = ord(ch)
        if c < 0x20 or c == 0x7f: raise ValueError('text note text contains control character U+%04X' % c)
        if 0xD800 <= c <= 0xDFFF: raise ValueError('text note text contains a lone surrogate U+%04X' % c)
        if ch in '\\{}': out += b'\\' + ch.encode('ascii')
        else:
            try: b1 = ch.encode('cp1252'); out += (b1 if b1[0] < 0x80 else b"\\'%02x" % b1[0])
            except UnicodeEncodeError:
                u = ch.encode('utf-16-le')
                for k in range(0, len(u), 2):
                    v = int.from_bytes(u[k:k + 2], 'little'); out += b'\\u%d?' % (v - 65536 if v > 32767 else v)
    return bytes(out)


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
    new = rtf[:i] + _rtf_escape(text) + rtf[j:]
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


CASCADE_CLASSES = ('IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol')      # annotations that Revit deletes together with their host

# c5x-rvtgap 83: delete_cascade is fail-closed on the TARGET class. The planner only sees id references, so it also accepted styles, view types, materials, patterns and phase filters,
# which Revit may rely on through non-id relations. Only user-content classes are allowed until a Revit verdict clears more (extend this tuple, with a test, after oracle evidence).
DELETE_TARGET_CLASSES = ('TextNote', 'IndependentTag', 'BeamSystemTag', 'SpanDirectionSymbol', 'FamilyInstance', 'ImageInstance', 'ParameterFilterElement', 'ExternalParamLock', 'RefPlane')


def cascade_plan(src_path, tid):
    """ids to delete together with element tid: tid plus every referrer whose class is an annotation in CASCADE_CLASSES (closed transitively). Any other referrer (a joist system, a joined wall,
    a dimension, a hosted instance, ...) makes the cascade refuse: ValueError."""
    sys.path.insert(0, os.path.expanduser('~/rvt-research'))
    import collections, rvt_xcache
    recs = rvt_xcache.get_x_ro(src_path)['recs']; cls = {k[0]: k[1] for k in recs}
    def refs(v, o, d=0):
        if d > 12: return
        if isinstance(v, dict):
            for q in v.values(): refs(q, o, d + 1)
        elif isinstance(v, (list, tuple)):
            for q in v: refs(q, o, d + 1)
        elif type(v).__name__ == 'EID': o.add(int(v))
    inb = collections.defaultdict(set)
    for (eid, c), r in recs.items():
        o = set(); refs(r.get('fields'), o)
        for v in o:
            if v != eid: inb[v].add(eid)
    if cls.get(int(tid)) not in DELETE_TARGET_CLASSES: raise ValueError('element %d is of class %s: deleting that class is not allowed (allowed: %s)' % (int(tid), cls.get(int(tid)), ', '.join(DELETE_TARGET_CLASSES)))
    todo = [int(tid)]; out = set()
    while todo:
        e = todo.pop()
        if e in out: continue
        out.add(e)
        for r in inb.get(e, ()):
            if r in out: continue
            if cls.get(r) in CASCADE_CLASSES: todo.append(r)
            else: raise ValueError('element %d is referenced by element %d (%s): cannot cascade-delete' % (e, r, cls.get(r)))
    return sorted(out)


def deleted_ids(src_path, ops):
    """every element id the ops delete (plain deletes and cascade plans)"""
    out = set()
    for o in ops:
        if o['op'] == 'delete': out.add(int(o['id']))
        elif o['op'] == 'delete_cascade': out.update(cascade_plan(src_path, int(o['id'])))
    return out


NUMERIC_KEYS = ('dx', 'dy', 'dz', 'x', 'y', 'z', 'height', 'length_delta', 'deg')
MAX_ABS = 1.0e5          # feet; Revit refuses geometry far beyond ~20 miles from the origin


def _check_numbers(o):
    """c7x-rvtread2 item 376: NaN/inf/absurd numbers must never be packed into a record (NaN was written into a wall by move_element dx=nan)."""
    import math
    if not isinstance(o, dict) or not isinstance(o.get('op'), str): raise ValueError('op entry must be a dict with a string "op": %r' % (o,))
    for k in ('id', 'template', 'symbol'):
        if k in o and (type(o[k]) is not int or o[k] <= 0): raise ValueError('op %s: %s=%r must be a positive integer' % (o['op'], k, o[k]))
    for k in NUMERIC_KEYS:
        if k in o and o[k] is not None:
            if type(o[k]) not in (int, float): raise ValueError('op %s: %s=%r must be a number (int or float), not %s' % (o['op'], k, o[k], type(o[k]).__name__))
            v = float(o[k])
            if not math.isfinite(v) or (k != 'deg' and abs(v) > MAX_ABS): raise ValueError('op %s: %s=%r is not a finite value within +-%g' % (o.get('op'), k, o[k], MAX_ABS))


MODIFY_OPS = ('move_instance', 'move_element', 'rotate_instance', 'resize_wall', 'set_instance_type', 'move_textnote')


def _check_deleted_once(src_path, ops):
    """c7x-rvtread2 item 381: a second delete of the same id used to remove NEIGHBOURING records (delete+delete of TextNote 916133 lost 3 records: the TextNote, a Viewport and a FamilyInstance).
    An id may be deleted once per run and no later op may touch a deleted id."""
    gone = set(); modified = set()
    for o in ops:
        if o['op'] in MODIFY_OPS:
            if int(o['id']) in modified: raise ValueError('element %d is modified twice in one run (%s): edits of one element do not compose (the last one silently wins, item 395); combine them into one op or save twice' % (int(o['id']), o['op']))
            modified.add(int(o['id']))
        if o['op'] == 'delete':
            ids = [int(o['id'])]
            sys.path.insert(0, os.path.expanduser('~/rvt-research')); import rvt_xcache      # c5x-rvtgap 85: the plain delete obeys the same target-class allowlist as delete_cascade
            c = {k[0]: k[1] for k in rvt_xcache.get_x_ro(src_path)['recs']}.get(ids[0])
            if c not in DELETE_TARGET_CLASSES: raise ValueError('element %d is of class %s: deleting that class is not allowed (allowed: %s)' % (ids[0], c, ', '.join(DELETE_TARGET_CLASSES)))
        elif o['op'] == 'delete_cascade': ids = cascade_plan(src_path, int(o['id']))
        else:
            for k in ('id', 'template'):
                if k in o and int(o[k]) in gone: raise ValueError('op %s touches element %s deleted earlier in the same run' % (o['op'], o[k]))
            continue
        for i in ids:
            if i in gone: raise ValueError('element %d is deleted twice in one run' % i)
            gone.add(i)


def run(src_path, ops, dst_path, check_source=True, lab=False):
    _lab(); import rvtgen
    for o in ops: _check_numbers(o)      # pure input validation first: no file needed (test_rvt_writer_c7x_finite_numbers expects ValueError, not FileNotFoundError)
    if not lab:      # c7x-rvtread2 561: the writer is fitted and oracle-tested for the writable years only; other years would produce unverified files (the save path refuses them, the raw API did not)
        from .adapters import RvtAdapter
        with open(src_path, 'rb') as _f: RvtAdapter().sniff(_f.read())      # raises UnsupportedVersion
    if check_source:      # never write a new file from a damaged source (damage would be carried forward or hidden)
        from .adapters import RvtAdapter
        with open(src_path, 'rb') as _f: _d = RvtAdapter().source_damage(_f.read())
        if _d: raise ValueError('source file is damaged (%d finding(s), first: %s): refusing to write' % (len(_d), str(_d[0])[:120]))
    import os as _os
    if _os.path.exists(dst_path) and _os.path.samefile(src_path, dst_path): raise ValueError('output path is the source file: WO.run writes non-atomically, use the gate (temp copy + atomic replace)')
    for o in ops: _check_numbers(o)
    _check_deleted_once(src_path, ops)
    g = rvtgen.Gen(src_path); new_ids = []
    try:
      _apply_ops(g, src_path, ops, new_ids)
    except (struct.error, KeyError, IndexError, OverflowError) as e:   # an id that does not map to a clean record (duplicate/phantom key) must be a loud ValueError, never a raw low-level crash
        raise ValueError('writer op refused: element record not usable for this op (%s: %s)' % (type(e).__name__, str(e)[:80]))
    g.commit(dst_path)
    return new_ids


# c5x-rvtgap 91: POSITIVE allowlists (the item 86 denylist still let move_element shift view crops, dimension anchors and style offsets: 149 of 291 classes accepted).
# FamilySymbol stays for the older chain tests on the Autodesk template (no placed instances there); unverified in Revit. ElementGroup is listed so that the group-specific refusals keep their own messages.
MOVE_TARGET_CLASSES = ('FamilyInstance', 'SWall', 'Wall', 'Grid', 'Level', 'TextNote', 'ImageInstance', 'RefPlane', 'IndependentTag', 'FamilySymbol', 'ElementGroup')
CLONE_TARGET_CLASSES = ('FamilyInstance', 'SWall', 'Wall', 'TextNote', 'ImageInstance', 'FamilySymbol', 'ElementGroup')


def _check_placed_class(src_path, eid, op):
    sys.path.insert(0, os.path.expanduser('~/rvt-research')); import rvt_xcache
    c = {k[0]: k[1] for k in rvt_xcache.get_x_ro(src_path)['recs']}.get(int(eid))
    ok = CLONE_TARGET_CLASSES if op in ('add_instance', 'add_element') else MOVE_TARGET_CLASSES
    if c not in ok:
        raise ValueError('op %s: element %s is of class %s, not an element placed in the model that this op may edit (allowed: %s)' % (op, eid, c, ', '.join(ok)))


def _find_key(x, key):
    """first value stored under dict key `key` anywhere inside the decoded record (m_groupId sits in a nested base object, not at top level)"""
    if isinstance(x, dict):
        if key in x: return x[key]
        for v in x.values():
            r = _find_key(v, key)
            if r is not None: return r
    elif isinstance(x, (list, tuple)):
        for v in x:
            r = _find_key(v, key)
            if r is not None: return r
    return None


GROUP_CLASSES = ('ElementGroup', 'ElementGroupAssociation', 'GroupBase', 'AssemblyInstance')   # c7x-rvtread2 items 513/515; self-contained so the guard does not depend on the move/clone allowlists


def _group_guard(src_path, o):
    """c7x-rvtread2 item 515: an element whose FamilyInstance.m_groupId names a group is a MEMBER: its group (member records, ElementGroupType.m_definingGroupInstId) is not updated by any writer op,
    so move / delete / clone / retype / rotate of a member (or of the defining instance) would leave the group inconsistent. Refused until a Revit verdict."""
    ids = [int(o[k]) for k in ('id', 'template') if o.get(k) is not None]
    if o['op'] == 'delete_cascade' and ids: ids = sorted(set(ids) | set(cascade_plan(src_path, ids[0])))
    if not ids: return
    sys.path.insert(0, os.path.expanduser('~/rvt-research')); import rvt_xcache
    allrecs = rvt_xcache.get_x_ro(src_path)['recs']
    recs = {k[0]: v for k, v in allrecs.items()}; cls = {k[0]: k[1] for k in allrecs}
    for i in ids:
        if cls.get(i) in GROUP_CLASSES: raise ValueError('op %s: element %d is of class %s (group / assembly): its members have their own records and would not follow, refused until a Revit verdict (c7x-rvtread2 item 514)' % (o['op'], i, cls.get(i)))
        gid = _find_key((recs.get(i) or {}).get('fields', {}), 'm_groupId')
        m = re.match(r'EID\((\d+)\)', str(gid)) if gid is not None else None
        if m and cls.get(int(m.group(1))) in GROUP_CLASSES:     # m_groupId of sketch curves / dimension strings names a VarSketch (not a group): only group classes count
            raise ValueError('op %s: element %d is a member of group %s: members cannot be edited alone (group not updated), refused' % (o['op'], i, gid))


DEPENDENT_CLASSES = ('FamilyInstance', 'SWall', 'Wall', 'ArcWall', 'Floor', 'ContFooting', 'Rebar', 'Alignment')   # plus every class whose name contains 'Dim'


def _dependents_guard(src_path, o):
    """c5x-rvtgap 76: move / rotate / resize change the geometry of ONE element; dimensions anchored to it, walls joined to it and instances hosted on it are NOT updated by any writer op, so the saved
    model would be semantically stale (dimension values, joins, floating doors) although structurally valid. Fail closed: refuse unless the op carries allow_dependents=true (explicit, for oracle tests)."""
    if o.get('allow_dependents') is True or o.get('id') is None: return
    sys.path.insert(0, os.path.expanduser('~/rvt-research')); import collections, rvt_xcache
    recs = rvt_xcache.get_x_ro(src_path)['recs']; cls = {k[0]: k[1] for k in recs}; tid = int(o['id']); found = collections.Counter()
    def refs(v, out, d=0):
        if d > 12: return
        if isinstance(v, dict):
            for q in v.values(): refs(q, out, d + 1)
        elif isinstance(v, (list, tuple)):
            for q in v: refs(q, out, d + 1)
        elif type(v).__name__ == 'EID': out.add(int(v))
    for (eid, c), r in recs.items():
        if eid == tid or not (c in DEPENDENT_CLASSES or 'Dim' in str(c)): continue
        out = set(); refs(r.get('fields'), out)
        if tid in out: found[c] += 1
    if found: raise ValueError('op %s: element %d has dependents the writer does not update (%s): dimensions, joins or hosted instances would go stale; refused (set allow_dependents=true to override for a Revit-VM test)' % (o['op'], tid, ', '.join('%s x%d' % kv for kv in sorted(found.items()))))


def _apply_ops(g, src_path, ops, new_ids):
    for o in ops:
        _group_guard(src_path, o)
        if o['op'] in ('move_instance', 'move_element', 'rotate_instance', 'resize_wall'): _dependents_guard(src_path, o)
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
            _check_placed_class(src_path, o['id'], o['op'])
            _move_instance(g, int(o['id']), (float(o.get('dx', 0)), float(o.get('dy', 0)), float(o.get('dz', 0))))
        elif o['op'] in ('add_instance', 'add_element'):
            _check_placed_class(src_path, o['template'], o['op'])
            if not any(float(o.get(k, 0)) for k in ('dx', 'dy', 'dz')): raise ValueError('op %s: an all-zero offset would put the copy exactly on top of element %s; give a non-zero dx/dy/dz' % (o['op'], o.get('template')))
            new_ids.append(_add_instance(g, int(o['template']), (float(o.get('dx', 0)), float(o.get('dy', 0)), float(o.get('dz', 0)))))
        elif o['op'] == 'set_instance_type':
            _set_instance_type(g, src_path, int(o['id']), int(o['symbol']))
        elif o['op'] == 'delete_cascade':
            for i in cascade_plan(src_path, int(o['id'])): g.delete(i)
        elif o['op'] == 'move_textnote':
            _move_textnote(g, int(o['id']), float(o.get('dx', 0)), float(o.get('dy', 0)))
        elif o['op'] == 'resize_wall':
            _resize_wall(g, int(o['id']), o.get('height'), o.get('length_delta'))
        elif o['op'] == 'rotate_instance':
            _rotate_instance(g, int(o['id']), float(o['deg']))
        else: raise ValueError('unknown writer op %r' % o.get('op'))


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
    Trf.m_3x3 and FamilyInstance.m_RefDir in the record, Outline.m_minmax in the header entry becomes the box of the four rotated corners (z unchanged). The origin and the zone
    record do not change; m_zAxis turns with the matrix (identity for +Z instances). Sign/transposition convention of the stored matrix is verified only by the Revit VM."""
    import math
    W = 8; T = g.template(tid); rec = bytearray(T['rec']); L = {n: (o, e) for n, o, e, _ in T['log']}
    c, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    def rz(v): return (c * v[0] - s_ * v[1], s_ * v[0] + c * v[1], v[2])
    ox, oy, oz = struct.unpack_from('<3d', rec, L['Trf.m_or'][0])
    o3 = L['Trf.m_3x3'][0]; M = struct.unpack_from('<9d', rec, o3)
    cols = [rz((M[0], M[3], M[6])), rz((M[1], M[4], M[7])), rz((M[2], M[5], M[8]))]
    struct.pack_into('<9d', rec, o3, cols[0][0], cols[1][0], cols[2][0], cols[0][1], cols[1][1], cols[2][1], cols[0][2], cols[1][2], cols[2][2])
    r0 = L['FamilyInstance.m_RefDir'][0]; struct.pack_into('<3d', rec, r0, *rz(struct.unpack_from('<3d', rec, r0)))
    if 'FamilyInstance.m_zAxis' in L: z0 = L['FamilyInstance.m_zAxis'][0]; struct.pack_into('<3d', rec, z0, *rz(struct.unpack_from('<3d', rec, z0)))   # c7x-rvtread2 item 388: m_zAxis is the world direction of the local z (matrix column 3); it is horizontal for 10 of 1432 instances in the Snowdon Structural sample and must turn with them
    hdr = bytearray(T['hdr']); hl = {n: (o, e) for n, o, e, _ in T['hlog']}
    if 'Outline.m_minmax' in hl:
        a = hl['Outline.m_minmax'][0]; mm = struct.unpack_from('<6d', hdr, a)
        pts = [rz((x - ox, y - oy, 0.0)) for x in (mm[0], mm[3]) for y in (mm[1], mm[4])]
        xs = [ox + p[0] for p in pts]; ys = [oy + p[1] for p in pts]
        struct.pack_into('<6d', hdr, a, min(xs), min(ys), mm[2], max(xs), max(ys), mm[5])
    g.replace_existing(tid, hdr=bytes(hdr), rec=bytes(rec))


MIN_WALL_LENGTH = 0.1      # ft
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
        if float(height) < MIN_WALL_LENGTH: raise ValueError('resize_wall: height %.4f ft is below the minimum %.2f ft' % (float(height), MIN_WALL_LENGTH))
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
        p0, p1 = struct.unpack_from('<2d', rec, ep[0])
        if p1 + dl - p0 < MIN_WALL_LENGTH: raise ValueError('resize_wall: new length %.4f ft is below the minimum %.2f ft (c7x-rvtread2 item 389; a zero or negative length wall was accepted)' % (p1 + dl - p0, MIN_WALL_LENGTH))
        struct.pack_into('<2d', rec, ep[0], p0, p1 + dl)
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


def _family_of(src_path, sym):
    sys.path.insert(0, os.path.expanduser('~/rvt-research'))
    import rvt_xcache
    for (e, c), v in rvt_xcache.get_x_ro(src_path)['recs'].items():
        if e == sym: return c, int(v['fields'].get('m_familyId', -1)) if c == 'FamilySymbol' else None
    return None, None


def _set_instance_type(g, src_path, tid, new_sym):
    """CHANGE the type (FamilySymbol) of a FamilyInstance to another symbol of the SAME family: the old symbol id is replaced by the new one in FamilyInstance.m_masterSymbolId (record) and in the header
    entry (ElementParents.m_deletion and m_appearanceParents), same-size edits. The symbols' own header lists (instances of a type) are NOT updated: Revit-VM question."""
    T = g.template(tid); rec = bytearray(T['rec']); L = {n: (o, e) for n, o, e, _ in T['log']}
    o = L['FamilyInstance.m_masterSymbolId'][0]; old = struct.unpack_from('<Q', rec, o)[0]
    c1, f1 = _family_of(src_path, old); c2, f2 = _family_of(src_path, new_sym)
    if c2 != 'FamilySymbol' or f1 is None or f1 != f2: raise ValueError('symbol %d is not a FamilySymbol of the same family as the current type %d (families %s / %s)' % (new_sym, old, f1, f2))
    if old == new_sym: raise ValueError('instance %d already has type %d' % (tid, new_sym))
    ob, nb = struct.pack('<Q', old), struct.pack('<Q', new_sym)
    struct.pack_into('<Q', rec, o, new_sym)
    hdr = bytearray(T['hdr']); n_h = 0; k = hdr.find(ob)
    while k >= 0: hdr[k:k + 8] = nb; n_h += 1; k = hdr.find(ob, k + 8)
    if not n_h: raise ValueError('old symbol id not found in the header entry (layout differs)')
    g.replace_existing(tid, hdr=bytes(hdr), rec=bytes(rec))
    def latest(raw, tid=tid, old=old, new_sym=new_sym):
        """Global/Latest keeps per-type instance lists [count u32][ids u64..] sorted, STARTING with the symbol id: move tid from old's list(s) to new_sym's list(s)"""
        def lists(sym):
            out = []; pat = struct.pack('<Q', sym); k = -1
            while True:
                k = raw.find(pat, k + 1)
                if k < 0: break
                if k < 4: continue
                n = struct.unpack_from('<I', raw, k - 4)[0]
                if not 1 <= n < 20000 or k + 8 * n > len(raw): continue
                ids = list(struct.unpack_from('<%dQ' % n, raw, k))
                if ids[0] != sym or ids != sorted(ids) or any(i >= 1 << 40 for i in ids): continue
                out.append((k - 4, n, ids))
            return out
        lo = [l for l in lists(old) if tid in l[2]]; ln = lists(new_sym)
        if not lo: return raw          # the instance is in no per-type list of Global/Latest (Snowdon structural instances are not): nothing to move
        if len(lo) != len(ln): raise ValueError('cannot patch the Global/Latest instance lists: %d list(s) of the old type contain the instance, %d list(s) start with the new type' % (len(lo), len(ln)))
        ops = [(pos, 4 + 8 * n, struct.pack('<I', n - 1) + b''.join(struct.pack('<Q', i) for i in ids if i != tid)) for pos, n, ids in lo]
        ops += [(pos, 4 + 8 * n, struct.pack('<I', n + 1) + b''.join(struct.pack('<Q', i) for i in sorted(ids + [tid]))) for pos, n, ids in ln]
        out = bytearray(raw)
        for pos, dl, ins in sorted(ops, key=lambda o: -o[0]): out[pos:pos + dl] = ins
        return bytes(out)
    import rvtw
    _s = rvtw.Stream(g.e.m.c.streams()['Global/Latest'].data); _P = _s.payload; _raw, _ = rvtw.read_member(_P, _P.find(rvtw.GZ)); _new = latest(bytes(_raw))
    if _new != bytes(_raw): g.e.global_edit('Global/Latest', lambda raw: _new)      # only when a list really changes: an unneeded rewrite would recompress the stream for nothing


def _add_instance(g, tid, d):
    """ADD an element (FamilyInstance, wall, ...): clone of the existing instance tid (same type, level, parameters) with a new id, placed at the template position + d (feet): record (id, Element.m_id, Trf.m_or and
    m_instOrigin when set), header entry (own id in its lists, Outline.m_minmax shifted), zone record (id, (x,y) pairs shifted), ElemTable row, and the Global/Latest id lists that start with the template id
    or with its type symbol id (the symbol's instance list). Returns the new id."""
    _lab(); import genlib, genlib2
    from genlib import restamp, rep
    W = 8; T = g.template(tid); nid = g.nextid; g.nextid += 1; idb = nid.to_bytes(W, 'little')
    rec = bytearray(T['rec']); L = {n: (o, e) for n, o, e, _ in T['log']}
    rec[4:12] = idb; rec[L['Element.m_id'][0]:L['Element.m_id'][1]] = idb
    first = None
    for n, o, e, _ in T['log']:
        if n in MOVE_FIELDS and e - o == 24:
            v = struct.unpack_from('<3d', rec, o); first = first or v; struct.pack_into('<3d', rec, o, v[0] + d[0], v[1] + d[1], v[2] + d[2])
        elif n == 'FamilyInstance.m_instOrigin':
            v = struct.unpack_from('<3d', rec, o)
            if any(v): struct.pack_into('<3d', rec, o, v[0] + d[0], v[1] + d[1], v[2] + d[2])
    if first is None: raise ValueError('element %d has no movable origin field (%s)' % (tid, ', '.join(MOVE_FIELDS)))
    ox, oy, oz = first
    sym = struct.unpack_from('<Q', rec, L['FamilyInstance.m_masterSymbolId'][0])[0] if 'FamilyInstance.m_masterSymbolId' in L else None
    hdr, hl = genlib2.hdr_ids(T, nid, W)
    if 'Outline.m_minmax' in hl:
        a = hl['Outline.m_minmax'][0]; mm = struct.unpack_from('<6d', hdr, a)
        struct.pack_into('<6d', hdr, a, mm[0] + d[0], mm[1] + d[1], mm[2] + d[2], mm[3] + d[0], mm[4] + d[1], mm[5] + d[2])
    item = bytearray(T['item']); rep(item, T['tid'].to_bytes(W, 'little'), idb)
    for off in range(0, len(item) - 16):
        if struct.unpack_from('<d', item, off)[0] == ox and struct.unpack_from('<d', item, off + 8)[0] == oy: struct.pack_into('<2d', item, off, ox + d[0], oy + d[1])
    rec = bytearray(g.stamp(bytes(rec))); genlib.setphase(hdr); genlib.setphase(rec); rec = g.stamp(bytes(rec)); genlib.setphase(item); item = restamp(bytes(item), W)
    et = g._et(); n_ = struct.unpack_from('<I', et, 2)[0]
    best = max(range(n_), key=lambda k: (struct.unpack_from('<I', et, 6 + 40 * k + 12)[0], struct.unpack_from('<I', et, 6 + 40 * k + 8)[0]))
    ea, eb, _ = struct.unpack_from('<3I', et, 6 + 40 * best + 8)
    g.new.append((bytes(hdr), bytes(rec), bytes(item), nid)); g.rows.append(genlib._row(g, T, nid, 8, (ea, eb, eb)))
    prev = list(getattr(g, 'latest_edits', []))
    def comp(raw, tid=tid, nid=nid, sym=sym):
        ops = genlib2.registry_ops(raw, tid, [nid]) + (genlib2.registry_ops(raw, sym, [nid], must=tid) if sym is not None else [])
        out = bytearray(raw)
        for pos, dl, ins in sorted(ops, key=lambda o: -o[0]): out[pos:pos + dl] = ins
        return bytes(out)
    g.latest_edits = prev + [('Latest', comp)]
    g.itag = T['item'][16:18]
    return nid
