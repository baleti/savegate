import sys, os, time, resource, hashlib
sys.path.insert(0, os.path.expanduser('~/src/savegate'))
import savegate as sg
from savegate.adapters import RawAdapter
mb = int(sys.argv[1]); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
os.environ['SAVEGATE_JOURNAL'] = out + '/j'
p = out + '/big.bin'; blk = os.urandom(1 << 20)
with open(p, 'wb') as f:
    for i in range(mb): f.write(blk)
cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2)
t = time.time()
with sg.open_doc(p, RawAdapter(), cfg) as doc:
    print('open', round(time.time() - t, 1), 's', flush=True)
    new = bytearray(doc.buf); new[100] ^= 1; new = bytes(new)
    for i in range(3):
        t = time.time(); r = sg.save(doc, new if i % 2 == 0 else bytes(doc.buf), {'modified': ['file']}, verify=None)
        print('save', i, round(time.time() - t, 1), 's', r.size >> 20, 'MB', flush=True)
print('files', sorted(os.listdir(out)))
print('peak RSS MB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >> 10)
