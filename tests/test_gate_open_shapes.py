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
