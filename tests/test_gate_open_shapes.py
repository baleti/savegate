import json, pytest
import savegate as sg
from savegate.core import gate_open

@pytest.mark.parametrize('content', ['', '{{{', '[]', 'null', '"open"', '1', '{"rvt":"open"}', '{"rvt":["open"]}', '{"rvt":null}',
                                     '{"rvt":{"2024":true}}', '{"rvt":{"2024":"Open"}}', '{"rvt":{"2024":["open"]}}', '{"rvt":{"2024":{"a":1}}}'])
def test_malformed_gate_is_closed(tmp_path, content):
    p = tmp_path / 'g.json'; p.write_text(content)
    assert gate_open('rvt', '2024', sg.Config(gate_file=str(p))) is False

def test_open_cases(tmp_path):
    p = tmp_path / 'g.json'; p.write_text('{"rvt":{"2024":"open"}}')
    c = sg.Config(gate_file=str(p))
    assert gate_open('rvt', '2024', c) and not gate_open('rvt', '2025', c) and not gate_open('dwg', '2024', c)

def test_missing_gate_file_is_closed(tmp_path):
    assert gate_open('rvt', '2024', sg.Config(gate_file=str(tmp_path / 'nope.json'))) is False

def test_fifo_directory_huge_deep_are_closed(tmp_path):
    import os, threading
    res = {}
    def run(path):
        res[path] = gate_open('rvt', '2024', sg.Config(gate_file=path))
    fifo = str(tmp_path / 'f'); os.mkfifo(fifo)
    big = tmp_path / 'big.json'; big.write_text('{"x":"' + 'a' * (2 << 20) + '","rvt":{"2024":"open"}}')
    deep = tmp_path / 'deep.json'; deep.write_text('[' * 100000)
    for pth in (fifo, str(tmp_path), str(big), str(deep)):
        th = threading.Thread(target=run, args=(pth,), daemon=True); th.start(); th.join(5)
        assert not th.is_alive(), 'hung on %s' % pth
        assert res[pth] is False
