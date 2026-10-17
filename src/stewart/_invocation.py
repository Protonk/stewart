"""Operation-time selection and retention of the manager's executable code.

Source operations deploy a private snapshot into a dedicated code directory.
An issued command pins that deployment, not a subsequently edited source tree.
No target repository or caller directory participates in code selection.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from stewart._bootstrap import (
    StewartError, manager_home, read_regular, runtime_digest, stage_source, verify_runtime,
)


@dataclass(frozen=True)
class Invocation:
    interpreter: str
    loaded_package: Path
    code_root: Path
    launcher: Path
    manifest: dict
    launcher_sha256: str
    source_package: Path | None

    def identity(self) -> dict:
        return {"interpreter": self.interpreter,
                "loaded_package": str(self.loaded_package),
                "code_root": str(self.code_root), "launcher": str(self.launcher),
                "runtime_sha256": runtime_digest(self.manifest),
                "launcher_sha256": self.launcher_sha256,
                "source_package": None if self.source_package is None else str(self.source_package),
                "route": "isolated-manager/1"}

    def command(self, *arguments: str) -> dict:
        """Render a plain argv; execution verifies identity before importing code."""
        verify_runtime(self.code_root, self.manifest)
        info, data = read_regular(self.launcher)
        if data is None or info.get("sha256") != self.launcher_sha256:
            raise StewartError("retained manager launcher changed or disappeared",
                               reason="launcher_mismatch", retained=[str(self.launcher)],
                               next_steps=["restore the pinned manager deployment"])
        return {"argv": [self.interpreter, "-I", "-B", str(self.launcher),
                         "manager", "--code-root", str(self.code_root),
                         "--runtime-sha256", runtime_digest(self.manifest),
                         *([] if self.source_package is None else ["--source-package", str(self.source_package)]),
                         "--", *arguments], "env": {}, "runtime": self.identity()}


_running: Invocation | None = None


def bind_verified(code_root: Path, launcher: Path, manifest: dict, *, source_package: Path | None = None) -> None:
    """Called only by the trusted launcher after its pre-import verification."""
    global _running
    package = Path(__file__).parent
    if package != code_root / "stewart":
        raise StewartError("loaded package differs from the verified runtime",
                           reason="runtime_layout")
    info, data = read_regular(launcher)
    if data is None:
        raise StewartError("manager launcher is no longer readable", reason="launcher_mismatch")
    # Do not resolve sys.executable: a venv's symlink spelling selects its site.
    _running = Invocation(sys.executable, package, code_root, launcher, manifest, info["sha256"], source_package)


def verified_invocation() -> Invocation | None:
    """The launcher-bound code selection, without deployment or filesystem work."""
    return _running


def retain_source(*, cache: Path | None = None) -> Invocation:
    """Deploy the selected source before rendering an independently pinned command."""
    source = Path(__file__).parent.resolve()
    deployed = stage_source(source, cache=cache)
    return Invocation(sys.executable, source, **deployed)


_source: dict[Path, Invocation] = {}


def current() -> Invocation:
    """Retain source once per process, only when an operation first needs it.

    In-process callers own their imports. Their first issued command selects
    the source bytes then on disk, not a reconstruction of loaded Python objects.
    Use isolated startup when executed code must match the selected inventory.
    """
    if _running is not None:
        return _running
    home = manager_home()
    if home not in _source:
        _source[home] = retain_source(cache=home)
    return _source[home]
