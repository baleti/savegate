"""Edit journal: JSON lines, fsynced per entry, so a viewer crash can be recovered."""
import os, json, time, uuid
from .atomic import full_fsync


def journal_dir():
    return os.environ.get('SAVEGATE_JOURNAL') or os.path.join(
        os.environ.get('LOCALAPPDATA', os.path.expanduser('~')) if os.name == 'nt' else os.environ.get('XDG_STATE_HOME', os.path.expanduser('~/.local/state')), 'savegate', 'journal')


class Journal:
    def __init__(self, source_path, directory=None):
        self.dir = directory or journal_dir()
        try: os.makedirs(self.dir, exist_ok=True)
        except OSError: import tempfile; self.dir = tempfile.gettempdir()
        self.id = time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
        self.path = os.path.join(self.dir, self.id + '.jsonl')
        self.f = open(self.path, 'a', encoding='utf-8')
        self.log('open', source=os.path.abspath(source_path))

    def log(self, kind, **kw):
        try:   # a full disk or unwritable state dir must never break a save
            self.f.write(json.dumps(dict(t=time.time(), kind=kind, **kw), ensure_ascii=False) + '\n')
            self.f.flush(); full_fsync(self.f.fileno())
        except (OSError, ValueError):
            pass

    def close(self, done=True):
        if done: self.log('closed')
        self.f.close()
        if done:
            try: os.remove(self.path)
            except OSError: pass


def unfinished(directory=None):
    """sessions that did not end with 'closed': [(path, entries)]"""
    d = directory or journal_dir(); out = []
    try: names = sorted(os.listdir(d))
    except OSError: return out
    for n in names:
        if not n.endswith('.jsonl'): continue
        p = os.path.join(d, n)
        try:
            ents = []
            for line in open(p, encoding='utf-8'):
                try: ents.append(json.loads(line))
                except ValueError: break   # torn last line from a crash
        except OSError: continue
        if ents and ents[-1].get('kind') != 'closed': out.append((p, ents))
    return out
