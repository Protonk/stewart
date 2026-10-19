"""Removal through pinned directory descriptors: links are removed, never followed.

A pathname check followed by a pathname removal lets a substituted ancestor
redirect the removal into unrelated storage. Here every ancestor is opened with
no-follow directory descriptors from the filesystem root, and the target is
removed relative to its pinned parent, so a link anywhere on the way fails the
open instead of being traversed. A link at the target itself is unlinked. A
directory is removed child by child through descriptors whose identity matches
the entry that was inspected. Removal never resolves a recorded path twice.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import stat

from stewart._bootstrap import open_directory

_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


class Substituted(Exception):
    """An ancestor of a recorded path is a link or not a directory; nothing below it was traversed."""

    def __init__(self, location: Path, detail: str):
        super().__init__(f"{location}: {detail}")
        self.location = location
        self.detail = detail


class Replaced(Exception):
    """The entry changed identity between inspection and removal; it was left in place."""


@contextmanager
def pinned(directory: Path):
    """Open ``directory`` through no-follow descriptors for every component.

    ``FileNotFoundError`` propagates for an absent component. A component that
    is a link or not a directory raises ``Substituted`` naming the requested
    location; the caller keeps it and reports the substitution.
    """
    try:
        with open_directory(Path(directory)) as descriptor:
            yield descriptor
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR, errno.EMLINK):
            raise Substituted(Path(directory), "a link or non-directory stands in for a recorded directory or one of "
                                              "its ancestors; nothing below it was traversed") from exc
        raise


def entry(parent: int, name: str) -> os.stat_result | None:
    """The entry's own status relative to a pinned parent, without following it."""
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _open_child(parent: int, name: str, expected: os.stat_result) -> int:
    try:
        descriptor = os.open(name, _DIRECTORY, dir_fd=parent)
    except PermissionError:
        # A read-only tree (an auditor may have changed modes) still belongs to
        # the recorded inventory. Restore owner access without following links.
        try:
            os.chmod(name, stat.S_IRWXU, dir_fd=parent, follow_symlinks=False)
        except (NotImplementedError, OSError):
            os.chmod(name, stat.S_IRWXU, dir_fd=parent)
        descriptor = os.open(name, _DIRECTORY, dir_fd=parent)
    opened = os.fstat(descriptor)
    if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
        os.close(descriptor)
        raise Replaced(f"{name} changed identity before it was opened")
    return descriptor


def _remove_directory(parent: int, name: str, expected: os.stat_result) -> None:
    descriptor = _open_child(parent, name, expected)
    try:
        try:
            os.fchmod(descriptor, stat.S_IRWXU)
        except OSError:
            pass
        for child in os.listdir(descriptor):
            found = os.stat(child, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(found.st_mode):
                _remove_directory(descriptor, child, found)
            else:
                os.unlink(child, dir_fd=descriptor)
    finally:
        os.close(descriptor)
    os.rmdir(name, dir_fd=parent)


def remove(parent: int, name: str) -> str:
    """Remove one entry below a pinned parent; return what was done.

    ``absent`` when nothing is there, ``removed link`` for a link (its target is
    untouched), ``removed`` for a file or a directory tree.
    """
    found = entry(parent, name)
    if found is None:
        return "absent"
    if stat.S_ISLNK(found.st_mode):
        os.unlink(name, dir_fd=parent)
        return "removed link"
    if stat.S_ISDIR(found.st_mode):
        _remove_directory(parent, name, found)
        return "removed"
    os.unlink(name, dir_fd=parent)
    return "removed"


def remove_path(location: Path) -> str:
    """Remove ``location`` relative to its pinned parent; an absent parent means an absent entry."""
    location = Path(location)
    try:
        with pinned(location.parent) as parent:
            return remove(parent, location.name)
    except FileNotFoundError:
        return "absent"


def remove_empty(location: Path) -> str:
    """Remove a recorded directory only when it is a real, empty directory."""
    location = Path(location)
    try:
        with pinned(location.parent) as parent:
            found = entry(parent, location.name)
            if found is None:
                return "absent"
            if not stat.S_ISDIR(found.st_mode):
                raise Substituted(location, "a link or non-directory stands where a directory was recorded")
            descriptor = _open_child(parent, location.name, found)
            try:
                if os.listdir(descriptor):
                    return "kept: not empty"
            finally:
                os.close(descriptor)
            os.rmdir(location.name, dir_fd=parent)
            return "removed"
    except FileNotFoundError:
        return "absent"
