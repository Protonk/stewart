"""Capture a stopped auditor's report/notes through no-follow descriptors.

The witness lives outside the audit lifetime and is not ordinary product retrieval.
Run only after the harness has returned and the auditor has acknowledged stopping.
"""

import datetime
import hashlib
import json
import os
import pathlib
import stat

root = pathlib.Path(__file__).resolve().parents[2]
run = root / '.scratch/opus-preparation-audit-01/run-001'
prepared = json.loads((run / 'prepare.stdout').read_text())['result']
stop = json.loads((run / 'AUDITOR-STOP.json').read_text())
assert stop['stopped'] is True
destination = run / 'precollection-witness'
destination.mkdir()
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def open_directory(base, parts):
    fd = os.dup(base)
    try:
        for part in parts:
            if part in ('', '.', '..') or '/' in part:
                raise ValueError('Invalid path component')
            child = os.open(part, directory_flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def snapshot(parent, name, relative):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('Witness member is not a regular file')
        blocks = []
        while chunk := os.read(fd, 65536):
            blocks.append(chunk)
        after = os.fstat(fd)
        keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(before, key) != getattr(after, key) for key in keys):
            raise ValueError('Witness member changed during observation')
        data = b''.join(blocks)
    finally:
        os.close(fd)
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(data)
    members.append({'path': relative, 'size': len(data),
                    'sha256': hashlib.sha256(data).hexdigest()})


def visit(fd, relative):
    for name in sorted(os.listdir(fd)):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        path = relative + '/' + name
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, directory_flags, dir_fd=fd)
            try:
                visit(child, path)
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode):
            snapshot(fd, name, path)
        else:
            raise ValueError('Unexpected non-regular witness member: ' + path)


members = []
anchor = os.open('/', directory_flags)
try:
    worktree = open_directory(anchor, pathlib.Path(prepared['worktree']).parts[1:])
finally:
    os.close(anchor)
try:
    report = 'audits/opus-preparation/reports/opus-commission-boundary-01.md'
    parent = open_directory(worktree, pathlib.PurePosixPath(report).parts[:-1])
    try:
        snapshot(parent, pathlib.PurePosixPath(report).name, report)
    finally:
        os.close(parent)
    notes = 'audits/opus-preparation/scratch/opus-commission-boundary-01/notes'
    parent = open_directory(worktree, pathlib.PurePosixPath(notes).parts)
    try:
        visit(parent, notes)
    finally:
        os.close(parent)
finally:
    os.close(worktree)

record = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'observer': 'root coordinator after harness return and stop acknowledgment',
          'source_worktree': prepared['worktree'], 'members': members,
          'meaning': 'Independent precollection byte witness; not product retrieval.'}
with (run / 'PRECOLLECTION-WITNESS.json').open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps({'members': len(members), 'record': str(run / 'PRECOLLECTION-WITNESS.json')}))
