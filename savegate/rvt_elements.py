"""Element-level snapshot for RvtAdapter(elements_fn=...): decodes the output with the pure-Python reader and
returns {element_id: comparable} (class + geometry bbox/confidence + solids hash). Heavy for big files: run the
save verification for RVT on a worker host; for the small writer scenes it takes seconds."""
import os, sys, tempfile, hashlib, json


def elements(buf, reader_dir=None, with_geometry=True):
    reader_dir = reader_dir or os.environ.get('SAVEGATE_RVT_READER') or os.path.expanduser('~/rvt-research')
    if reader_dir not in sys.path: sys.path.insert(0, reader_dir)
    import rvt_geometry as G
    fd, p = tempfile.mkstemp(suffix='.rvt'); os.close(fd)
    try:
        with open(p, 'wb') as f: f.write(buf)
        idx = G.file_geometry_index(p)
        out = {}
        for eid, cls in idx.items():
            v = str(cls)
            if with_geometry:
                try:
                    r = G.element_geometry(p, eid)
                    v += '|' + json.dumps([r.get('class'), r.get('confidence'), r.get('bbox'), r.get('transform')], default=repr, sort_keys=True)
                    v += '|' + hashlib.sha1(json.dumps(r.get('solids'), default=repr, sort_keys=True).encode()).hexdigest()
                except Exception as e:
                    v += '|ERR ' + type(e).__name__
            out[eid] = v
        return out
    finally:
        os.remove(p)
