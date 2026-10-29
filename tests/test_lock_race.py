"""Lock race (found by c8-crossplat): N processes do locked read-modify-write increments; any lost update means two holders at once."""
import os, sys, time, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _worker(path, m, out):
    from savegate.guard import Lock
    from savegate.errors import Locked
    n = 0
    for _ in range(m):
        while True:
            try:
                with Lock(path):
                    with open(path, 'rb') as f: v = int(f.read() or 0)
                    time.sleep(0.001)
                    with open(path, 'wb') as f: f.write(str(v + 1).encode())
                n += 1
                break
            except Locked:
                time.sleep(0.003)
    out.put(n)


def test_lock_mutual_exclusion_4_procs(tmp_path):
    p = str(tmp_path / 'counter.bin'); open(p, 'wb').write(b'0')
    q = mp.Queue(); ps = [mp.Process(target=_worker, args=(p, 30, q)) for _ in range(4)]
    [x.start() for x in ps]; [x.join(180) for x in ps]
    done = sum(q.get(timeout=5) for _ in ps)
    assert done == 120 and int(open(p, 'rb').read()) == 120
    assert [x for x in os.listdir(tmp_path) if x != 'counter.bin'] == []
