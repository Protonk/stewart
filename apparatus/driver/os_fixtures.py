"""Read captured local OS observations for offline controls; never probe stored IDs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent / 'testdata/os'
ORIGINS = json.loads((HERE / 'ORIGINS.json').read_bytes())


def raw(name):
    data = (HERE / name).read_bytes()
    row = ORIGINS[name]
    assert (len(data), hashlib.sha256(data).hexdigest()) == (row['bytes'], row['sha256'])
    return data


def document(name):
    return json.loads(raw(name))


def group_probe(phase):
    """Project an observed return/exception onto a synthetic target identity."""
    if phase == 'denied':
        row = document('denied-group.json')
    else:
        row = next(item for item in document('owned-group.json') if item['phase'] == phase)
    def probe(group, sig):
        assert type(group) is int and group > 0 and sig == 0
        if row['outcome'] == 'returned':
            return None
        number = row['errno']
        error = OSError(number, row['message'].removeprefix('[Errno %d] ' % number))
        assert type(error).__name__ == row['error_type'] and str(error) == row['message']
        raise error
    return probe
