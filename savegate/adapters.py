"""Format adapters: sniff version, snapshot (key -> comparable) for the verify diff, structural validate.
A snapshot key present in the source and output must be equal unless the manifest lists it as modified."""
import hashlib, os, sys, re
from .errors import UnsupportedVersion, VerifyFailed

DWG_WRITABLE = ('AC1015', 'AC1018', 'AC1024', 'AC1027', 'AC1032')
RVT_WRITABLE = ('2024', '2026')      # write-lab verified years; extend only with oracle evidence


def _h(b): return hashlib.sha1(b).hexdigest()


class RawAdapter:
    """no format knowledge: the whole file is one object (tests, unknown formats are refused by pick_adapter)"""
    name = 'raw'
    def sniff(self, buf): return 'raw'
    def snapshot(self, buf): return {'file': _h(buf)}
    def validate(self, buf):
        if not buf: raise VerifyFailed('empty output')
        return 'ok'


def _plain(v):
    """repr with the model's duplicate-name suffix '~<handle>' removed (two anonymous '*D' blocks are told apart by the model only while both exist)."""
    return re.sub(r"(\*[A-Za-z]+)~[0-9a-f]+", r"\1", repr(v) if not isinstance(v, str) else v)


_DWG_NAMES = {'AC1006': 'R10', 'AC1009': 'R11/R12', 'AC1012': 'R13', 'AC1014': 'R14', 'AC1015': '2000', 'AC1018': '2004', 'AC1021': '2007', 'AC1024': '2010', 'AC1027': '2013', 'AC1032': '2018+'}
_SUBENT = {2, 6, 10, 11, 12, 13, 14, 15}   # ATTRIB, SEQEND, VERTEX kinds


class DwgAdapter:
    name = 'dwg'
    def __init__(self, lib=None):
        lib = lib or os.environ.get('SAVEGATE_DWG_LIB') or os.path.expanduser('~/dwg-write')
        self.owners = {}; self.bheaders = {}; self.dimobjs = {}; self.blockhs = set()
        if lib not in sys.path: sys.path.insert(0, lib)

    def sniff(self, buf):
        v = buf[:6].decode('ascii', 'replace')
        if not re.fullmatch(r'AC10\d\d', v): return None
        if v not in DWG_WRITABLE:
            raise UnsupportedVersion('DWG %s (%s) cannot be saved: writable versions are %s. The file was not touched; export a copy as DXF or '
                                     'Save As one of the writable versions instead.' % (v, _DWG_NAMES.get(v, 'unknown'), ', '.join('%s (%s)' % (w, _DWG_NAMES[w]) for w in DWG_WRITABLE)))
        return v

    def _snap(self, m, same):
        out = {}
        ent_handles = set()
        for blk, e in m.entities():
            out['ent:%x' % e['handle']] = hashlib.blake2b((repr(sorted((k, _plain(v)) for k, v in e.items())) + '|' + _plain(blk)).encode(), digest_size=12).digest()
            ent_handles.add(e['handle']); self.owners[e['handle']] = e.get('owner')
            if str(e.get('kind', '')).startswith(('INSERT', 'MINSERT')) and isinstance(e.get('block_handle'), int): self.bheaders[e['handle']] = e['block_handle']
        self.blockhs |= set(getattr(m, 'blocks', {}))   # block records own entities but are not entities: declaring one must not excuse all its entities
        dimblk = {e['block_ref']: e['handle'] for blk, e in m.entities() if e.get('block_ref', '').startswith('*D')} if hasattr(m, 'entities') else {}
        self.dims = getattr(self, 'dims', set()) | set(dimblk.values())
        bhmap = {e['handle']: e.get('block_handle') for blk, e in m.entities() if e.get('block_ref', '').startswith('*D')} if dimblk else {}
        for bn, dh in dimblk.items():   # the anonymous block's own objects: BLOCK_HEADER, BLOCK, ENDBLK (adjacent handles)
            bh = bhmap.get(dh)
            if isinstance(bh, int):
                self.dimobjs[dh] = {'obj:%x' % x for x in range(bh, bh + 4) if x in m.objs and (x == bh or m.objs[x].type in (4, 5))}
        if dimblk:   # geometry of a dimension's anonymous block belongs to the dimension
            for blk, e in m.entities():
                if blk in dimblk and e['handle'] != dimblk[blk]: self.owners[e['handle']] = dimblk[blk]
        for h, o in m.objs.items():
            if h not in ent_handles:
                out['obj:%x' % h] = _h(o.raw)
                if o.type in _SUBENT and h not in self.owners:   # vertex / SEQEND / ATTRIB not emitted as entities (fast path skips): still owned by their parent
                    try:
                        par = [v for c, v in __import__('dwgmodel').owner_and_layer(o) if c == 4]
                        if par: self.owners[h] = par[0]
                    except Exception: pass
        for k, v in m.header().items():
            out['hdr:%s' % k] = repr(v)
        out['meta:version'] = m.version
        return out

    def snapshot_pair(self, src, out):
        """Fast path for verify: objects whose raw bytes are identical in source and output cannot differ when decoded
        (any cross-object change shows in the raw bytes of the object that changed), so only the others are decoded."""
        import dwgmodel as M
        ms, mo = M.Model(src), M.Model(out); self._pair = (ms, mo)
        same = {h for h, o in ms.objs.items() if h in mo.objs and mo.objs[h].raw == o.raw and mo.objs[h].type == o.type}
        saved = (dict(M.ENT_DECODERS), dict(M.CLASS_DECODERS), M._proxy_entity)
        def guard(f):
            def g(o, *a, **k):
                if o.handle in same: raise _Skip()
                return f(o, *a, **k)
            return g
        class _Skip(Exception): pass
        try:
            for d in (M.ENT_DECODERS, M.CLASS_DECODERS):
                for k in list(d): d[k] = guard(d[k])
            M._proxy_entity = guard(saved[2])
            snaps = [self._snap(m, same) for m in (ms, mo)]
        finally:
            M.ENT_DECODERS.clear(); M.ENT_DECODERS.update(saved[0]); M.CLASS_DECODERS.clear(); M.CLASS_DECODERS.update(saved[1]); M._proxy_entity = saved[2]
        return snaps

    def snapshot(self, buf):
        import dwgmodel
        return self._snap(dwgmodel.Model(buf), set())

    def expand(self, manifest):
        """handles (ints) in the manifest mean entity + object keys; structural side effects of add/delete
        (header HANDSEED, owner block table/object lists) are tolerated: the entity keys remain strict."""
        mod = set(); 
        for k in manifest.get('modified', ()):
            mod |= {k} if isinstance(k, str) else {'ent:%x' % k, 'obj:%x' % k}
        add = set(); dele = set()
        for k in manifest.get('added', ()):
            add |= {k} if isinstance(k, str) else {'ent:%x' % k, 'obj:%x' % k}
        for k in manifest.get('deleted', ()):
            dele |= {k} if isinstance(k, str) else {'ent:%x' % k, 'obj:%x' % k}
        return mod, add, dele


    def extra_checks(self, manifest):
        """Structural objects tolerated as side effects (block records, BLOCK/ENDBLK, tables) must keep their identity: a changed
        BLOCK/ENDBLK object is never a legitimate side effect (they are only added/removed with a dimension), and a changed BLOCK_HEADER
        must keep its decoded name (bit flip in a block name renames the block under its INSERTs; found by c8-perf gatepower 2026-10-30)."""
        pair = getattr(self, '_pair', None)
        if not pair: return
        ms, mo = pair; bad = []
        for h, o in ms.objs.items():
            p = mo.objs.get(h)
            if p is None or p.raw == o.raw: continue
            if o.type in (4, 5): bad.append(('struct_changed', 'obj:%x' % h))
            elif o.type == 49 and _plain(ms.blocks.get(h)) != _plain(mo.blocks.get(h)): bad.append(('block_renamed', 'obj:%x' % h))
        for h, n in ms.blocks.items():
            if h in mo.blocks and _plain(mo.blocks[h]) != _plain(n) and ('block_renamed', 'obj:%x' % h) not in bad: bad.append(('block_renamed', 'obj:%x' % h))
        # a block record that stops being listed turns every entity it owns into an orphan that no reader walks (entities silently vanish; c8-perf 2026-10-30):
        # allowed only for a declared deletion (a dimension's anonymous block) or when it was never a block of the source
        mod, add, dele = self.expand(manifest); ok = dele | self.side_effects(manifest)
        for h in ms.blocks:
            if h not in mo.blocks and 'obj:%x' % h not in ok: bad.append(('block_unlisted', 'obj:%x' % h))
        return bad

    # structural objects/header vars that legitimately change with add/delete/edit
    def side_effects(self, manifest):
        se = set()
        # owned sub-entities (POLYLINE vertices, SEQEND, INSERT attributes) belong to the declared entity
        decl = {k for kind in ('modified', 'added', 'deleted') for k in manifest.get(kind, ()) if isinstance(k, int)}
        for h, o in self.owners.items():
            if o in decl and o not in self.blockhs: se |= {'ent:%x' % h, 'obj:%x' % h}
        for k in list(manifest.get('added', ())) + list(manifest.get('deleted', ())):
            if isinstance(k, int):
                se.add('hdr:HANDSEED')
                if k in self.bheaders: se.add('obj:%x' % self.bheaders[k])   # INSERT: the block record keeps the list of its inserts
                if k in getattr(self, 'dims', ()): se |= {'obj:1'} | self.dimobjs.get(k, set())   # adding/removing a dimension adds/removes its anonymous block: BLOCK_CONTROL object list
                if self.owners.get(k) is not None: se.add('obj:%x' % self.owners[k])
        return se

    def validate(self, buf):
        import dwgmodel
        m = dwgmodel.Model(buf)
        if m.version not in DWG_WRITABLE: raise VerifyFailed('output version %s' % m.version)
        hs = m.header().get('HANDSEED')
        if isinstance(hs, int) and m.objs and hs <= max(m.objs):
            raise VerifyFailed('HANDSEED %x not above the highest handle %x' % (hs, max(m.objs)))
        # rule learned from the AutoCAD oracle (AUDIT 'color != owner's'): polyline vertices carry the owner's colour
        ents = {e['handle']: e for _, e in m.entities()}
        for h, e in ents.items():
            if str(e.get('kind', '')).startswith('VERTEX'):
                o = ents.get(e.get('owner'))
                if o is not None and o.get('color') != e.get('color'):
                    raise VerifyFailed('vertex %x colour %r differs from its polyline %x colour %r (AutoCAD AUDIT would repair)' % (h, e.get('color'), e['owner'], o.get('color')))
        return 'ok %s %d objects' % (m.version, len(m.objs))


class RvtAdapter:
    name = 'rvt'
    def __init__(self, lib=None, elements_fn=None):
        lib = lib or os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
        if lib not in sys.path: sys.path.insert(0, lib)
        self.elements_fn = elements_fn      # optional: buf -> {key: comparable} (reader element/parameter dump)

    def sniff(self, buf):
        if buf[:8] != bytes.fromhex('d0cf11e0a1b11ae1'): return None
        import cfb
        try: c = cfb.CFB(buf); s = c.streams()
        except Exception: return None
        if 'BasicFileInfo' not in s or 'Global/ElemTable' not in s and 'Global/Latest' not in s: return None
        t = s['BasicFileInfo'].data.decode('utf-16le', 'ignore')
        m = re.search(r'(20[12]\d)', t)
        v = m.group(1) if m else '?'
        if v not in RVT_WRITABLE:
            raise UnsupportedVersion('Revit %s file cannot be saved: writable years are %s. The file was not touched; open it in Revit and Save As a '
                                     'writable year, or save the edit as a new file with the writer.' % (v, ', '.join(RVT_WRITABLE)))
        return v

    def source_damage(self, buf):
        d = self._damage(buf); self._src_dmg = set(d); return d

    def overwrite_risks(self, buf):
        """c5x-rvtgap: reasons NOT to replace this file in place although the bytes are fine. A workshared model (Worksharing: Central/Local in BasicFileInfo) is tied to its
        central/local pair, workset ownership and sync history that live outside this file; rewriting it behind Revit's back can break the sync. SAVE AS stays allowed."""
        import cfb
        try: d = cfb.CFB(bytes(buf)).streams()['BasicFileInfo'].data
        except Exception: return []
        k = d.find('Worksharing:'.encode('utf-16le'))
        if k < 0: return []
        m = d[k + 24:k + 80].decode('utf-16le', 'ignore').strip().split('\r')[0].split('\n')[0].strip()
        if m and not m.lower().startswith('not enabled'): return ['workshared model (Worksharing: %s): in-place overwrite refused, use SAVE AS or save from Revit' % m]
        return []

    def _damage(self, buf):
        """problems in the SOURCE bytes the reader tolerates but the writer would carry over unchanged: bad page ECC, gzip CRC/size mismatch, bad inflate, unreadable container.
        Plain XML / raw gzip streams carry no page ECC. [] = nothing found. (c3x-rvtgap: a zeroed 64-byte run used to be saved back without any warning.)"""
        import struct, zlib, cfb, rvtw, ecc, wlpart
        errs = []
        try: S = cfb.CFB(bytes(buf)).streams()
        except Exception as ex: return ['container unreadable: %s' % ex]
        for n, e in S.items():
            if n in rvtw.PLAIN or n.startswith('\x05'): continue      # OLE property-set streams are plain
            d = e.data
            if d[:5] == b'<?xml' or d[:2] == b'\x1f\x8b': continue
            full = len(d) // rvtw.PAGE_STORED
            bad = [i for i in range(full) if not ecc.check(d[i * rvtw.PAGE_STORED:(i + 1) * rvtw.PAGE_STORED])]
            last = d[full * rvtw.PAGE_STORED:]
            if last and (ecc.params(len(last)) is None or not ecc.check(last)): bad.append(full)
            if bad: errs.append('%s: ECC bad on %d page(s), first %d' % (n, len(bad), bad[0]))
            try:
                P = rvtw.Stream(d).payload
                if n.startswith('Partitions/'):
                    if len(P) < 40: continue        # tiny partition: the parser needs a 36-byte frame
                    for k, m in enumerate(wlpart.Partition(rvtw.Stream(d)).mem):
                        raw = bytes(m['raw']); crc, isz = struct.unpack('<II', P[m['pos']:m['end']][-8:])
                        if crc != zlib.crc32(raw) & 0xffffffff or isz != len(raw): errs.append('%s member %d: crc/size mismatch' % (n, k))
                else:
                    i = P.find(rvtw.GZ)
                    if i < 0: continue
                    do = zlib.decompressobj(-15); raw = do.decompress(P[i + 10:]); crc, isz = struct.unpack('<II', do.unused_data[:8])
                    if crc != zlib.crc32(raw) & 0xffffffff or isz != len(raw) & 0xffffffff: errs.append('%s: crc/size mismatch' % n)
            except Exception as ex: errs.append('%s: %s %s' % (n, type(ex).__name__, ex))
        return errs

    def snapshot(self, buf):
        import cfb
        c = cfb.CFB(buf)
        out = {'stream:' + k: _h(e.data) for k, e in c.streams().items()}
        out['meta:streams'] = repr(sorted(c.streams()))
        out['meta:sector'] = '%d' % c.major
        if self.elements_fn:
            out.update({'el:' + str(k): v for k, v in self.elements_fn(buf).items()})
        self._keys = set(out)
        self._mem_hist = (getattr(self, '_mem_hist', [])[-1:]) + [self._member_hashes(c)]     # [source, output] of the current verify
        self._blk_hist = (getattr(self, '_blk_hist', [])[-1:]) + [self._block_hashes(c)]
        return out

    @staticmethod
    def _member_hashes(c):
        """{partition stream: [sha1 of each inflated gzip member]} or {} when the stream does not parse"""
        try:
            import rvtw, wlpart
            r = {}
            for n, e in c.streams().items():
                if not n.startswith('Partitions/'): continue
                st = rvtw.Stream(e.data)
                if len(st.payload) < 40: continue
                r[n] = [hashlib.sha1(bytes(m['raw'])).hexdigest() for m in wlpart.Partition(st).mem]
            return r
        except Exception: return {}

    BLK = 1024

    @classmethod
    def _block_hashes(cls, c):
        """{partition stream: (hashes of 1 KB blocks of the inflated members from the start, same from the end, total length)}"""
        try:
            import rvtw, wlpart
            r = {}
            for n, e in c.streams().items():
                if not n.startswith('Partitions/'): continue
                st = rvtw.Stream(e.data)
                if len(st.payload) < 40: continue
                b = b''.join(bytes(m['raw']) for m in wlpart.Partition(st).mem); B = cls.BLK
                r[n] = ([hash(b[i:i + B]) for i in range(0, len(b), B)], [hash(b[max(0, i - B):i]) for i in range(len(b), 0, -B)], len(b))
            return r
        except Exception: return {}

    SPAN_MAX = 8192        # per declared element (<= 8): the changed window of a partition (prefix/suffix diff) was <= 1066 bytes on 60 real scenes

    def span_checks(self, manifest):
        h = getattr(self, '_blk_hist', [])
        nd = sum(len(manifest.get(k, ())) for k in ('modified', 'added', 'deleted'))
        if not 1 <= nd <= 8 or len(h) < 2 or not h[0] or not h[1]: return []
        bad = []
        for n, (fa, ba, la) in h[0].items():
            if n not in h[1]: continue
            fb, bb, lb = h[1][n]
            if (fa, la) == (fb, lb): continue
            p = 0
            while p < min(len(fa), len(fb)) and fa[p] == fb[p]: p += 1
            q = 0
            while q < min(len(ba), len(bb)) and ba[q] == bb[q]: q += 1
            span = max(la, lb) - (p + q) * self.BLK
            if span > self.SPAN_MAX * nd: bad.append(('span_changed', '%s: changed window ~%d bytes for %d declared elements' % (n, span, nd)))
        return bad

    def extra_checks(self, manifest):
        """c5x-rvtgap: the element view and the record checks do not see a bit flip in a record region they do not decode (23 of 25 random single-bit flips with valid ECC/CRC
        went unnoticed), so a declared edit may change only a few neighbouring gzip members of a partition (real edits: 1-3 adjacent members); anything wider is refused"""
        h = getattr(self, '_mem_hist', [])
        if len(h) < 2 or not h[0]: return []      # c4x-rvtgap: an EMPTY output map is no reason to skip (all partitions vanished)
        bad = self.span_checks(manifest)
        nd = sum(len(manifest.get(k, ())) for k in ('modified', 'added', 'deleted')); budget = 4 * max(1, nd)
        for n, a in h[0].items():
            b = h[1].get(n)
            if b is None or abs(len(a) - len(b)) > budget:      # c4x-rvtgap ESCAPE: a declared Partitions stream emptied (valid container, nothing to check) was accepted; a partition that vanishes or whose member count changes wildly is refused
                bad.append(('members_changed', '%s: %d members in the source, %s in the output' % (n, len(a), 'none (stream empty or unparsable)' if b is None else len(b)))); continue
            if len(a) != len(b): continue
            ch = [k for k in range(len(a)) if a[k] != b[k]]
            if len(ch) > budget or (ch and ch[-1] - ch[0] + 1 > budget + 2): bad.append(('members_changed', '%s: %d members changed (%d..%d), declared %d' % (n, len(ch), ch[0], ch[-1], nd)))
        return bad

    def expand(self, manifest):
        return set(manifest.get('modified', ())), set(manifest.get('added', ())), set(manifest.get('deleted', ()))

    def side_effects(self, manifest):
        """With an element-level view, an element edit rewrites the partition / global streams that hold it; those stream keys
        are tolerated only when something is declared and the element keys (strict) cover the content. Identity stays byte-strict."""
        if not self.elements_fn or not any(manifest.get(k) for k in ('modified', 'added', 'deleted')): return set()
        return {k for k in getattr(self, '_keys', ()) if k.startswith('stream:Partitions/')}      # c5x-rvtgap: Global/* is NOT excused (the writer leaves every Global stream byte-identical on an element edit; a tampered one with valid ECC/CRC was accepted)

    def validate(self, buf):
        import cfb
        c = cfb.CFB(buf)
        s = c.streams()
        for need in ('BasicFileInfo',):
            if need not in s: raise VerifyFailed('stream %s missing in output' % need)
        if len(buf) != (c.nsectors + 1) * c.ss + (512 - c.ss if c.major == 3 else 0) and len(buf) % c.ss:
            raise VerifyFailed('container length is not sector aligned')
        dmg = [d for d in self._damage(buf) if d not in getattr(self, '_src_dmg', ())]       # c5x-rvtgap: the written bytes get the same page ECC / gzip CRC+size check as the source (a modified stream is exempt from the hash diff); damage already present in the source (SAVE AS rescue copy) is not new
        if dmg: raise VerifyFailed('output fails the integrity check: %s' % '; '.join(dmg[:3]))
        try:
            import rvtw, wlpart
            for n, e in s.items():
                if not n.startswith('Partitions/'): continue
                st = rvtw.Stream(e.data)
                if len(st.payload) < 40: continue
                pt = wlpart.Partition(st)
                import struct
                for k, m in enumerate(pt.mem):
                    L = m['end'] - m['pos']
                    if k < len(pt.gaps) and len(pt.gaps[k]) >= 32:       # c5x-rvtgap: frame after member k holds its own stored size + 8 and the next member's (0 across a section boundary); 0 violations in 35873 frames of 91 real partitions
                        own = struct.unpack_from('<I', pt.gaps[k], 2)[0]; nxt = struct.unpack_from('<I', pt.gaps[k], 16)[0]
                        Ln = pt.mem[k + 1]['end'] - pt.mem[k + 1]['pos'] if k + 1 < len(pt.mem) else None
                        if own != L + 8 or (Ln is not None and nxt not in (0, Ln + 8)): raise VerifyFailed('%s member %d: frame size fields do not match the stored member length' % (n, k))
                for k, m in enumerate(pt.mem):
                    if len(m['raw']) > 131088:       # every real 2024/2026 file tops out at exactly 131088 (12 files); Revit rejects larger members (vcheck rule)
                        raise VerifyFailed('%s member %d holds %d bytes, above the 131088 Revit limit' % (n, k, len(m['raw'])))
        except VerifyFailed: raise
        except Exception as ex: raise VerifyFailed('partition framing of the output could not be checked: %s %s' % (type(ex).__name__, ex))
        return 'ok %d streams' % len(s)


def pick_adapter(buf, adapter=None):
    if adapter is not None:
        return adapter, adapter.sniff(buf) or '?'
    for cls in (DwgAdapter, RvtAdapter):
        a = cls(); v = a.sniff(buf)
        if v: return a, v
    raise UnsupportedVersion('unknown or unsupported file format (not a writable DWG/RVT)')
