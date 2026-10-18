"""Where an assignment lives and where its private session lives.

A workspace is a repository-relative directory holding the auditor guidance
(``AUDITOR.md``), the maintainer guidance (``MAINTAINER.md``), the single assignment
(``PROMPT.md``), retained ``reports/`` and declared ``scratch/`` areas. Every
assignment-facing path derives from it; nothing in this package names a
particular workspace.

Private sessions live outside the workspace, under the repository's Git common
directory at ``stewart/sessions/<slug>/<audit-id>/``. The slug joins the
workspace's last path component to a digest of its full relative path, so two
workspaces that share an audit ID never address each other's evidence, and a
human can still read which workspace a session belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stewart import _util as _hash
from stewart import _util as path
from stewart._bootstrap import StewartError

# Roles select policy. Harness entry filenames and launch profiles do not.
AUDITOR_GUIDANCE = "AUDITOR.md"
MAINTAINER_GUIDANCE = "MAINTAINER.md"
PROMPT = "PROMPT.md"


def relative(value: object) -> str:
    """Reject paths that could reach checkout administration or escape custody."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise StewartError("expected a nonempty repository-relative path", reason="path_escape")
    try:
        path.require_rel(value)
    except ValueError as exc:
        raise StewartError(f"path must be repo-relative: {value!r}", reason="path_escape") from exc
    parsed = Path(value)
    if parsed.as_posix() != value or any(p.lower() == ".git" for p in parsed.parts) or value == ".":
        raise StewartError(f"noncanonical or administrative path: {value!r}", reason="path_noncanonical")
    return value


def contained(root: Path, rel: str, *, leaf_link: bool = False) -> Path:
    """Resolve ``rel`` under ``root`` without following a symlink on the way.

    An auditor-created link must never redirect a read or a write into another
    checkout or a host file. ``leaf_link`` permits the final component to be a
    link so that a caller can observe it without opening its target.
    """
    relative(rel)
    parts = Path(rel).parts
    for i in range(1, len(parts) + 1):
        candidate = root.joinpath(*parts[:i])
        if candidate.is_symlink() and not (leaf_link and i == len(parts)):
            raise StewartError(f"symlink is not an input/output directory: {rel}", reason="path_symlink")
    return root / rel


@dataclass(frozen=True)
class Workspace:
    """An assignment workspace inside one maintainer checkout."""

    repo: Path
    rel: str

    @property
    def prompt(self) -> str:
        return f"{self.rel}/{PROMPT}"

    @property
    def auditor_guidance(self) -> str:
        return f"{self.rel}/{AUDITOR_GUIDANCE}"

    @property
    def maintainer_guidance(self) -> str:
        return f"{self.rel}/{MAINTAINER_GUIDANCE}"

    @property
    def reports(self) -> str:
        return f"{self.rel}/reports"

    @property
    def scratch(self) -> str:
        return f"{self.rel}/scratch"

    def report_path(self, ident: str) -> str:
        return f"{self.reports}/{ident}.md"

    def scratch_prefix(self, ident: str) -> str:
        return f"{self.scratch}/{ident}/"

    @property
    def slug(self) -> str:
        return f"{Path(self.rel).name}-{_hash.sha256_text(self.rel)[:12]}"

    def guidance_files(self) -> tuple[str, str, str]:
        """Required role policies and assignment; harness entry files are optional."""
        return (self.auditor_guidance, self.maintainer_guidance, self.prompt)

    def to_json(self) -> dict:
        return {"repo": str(self.repo), "rel": self.rel, "slug": self.slug}


def workspace(repo: Path, rel: str) -> Workspace:
    """Bind a validated workspace path to a resolved maintainer checkout.

    This validates path shape and canonicalizes the explicitly selected root.
    Manager operations check the exact Git top-level and worktree role at use
    time, including for directly constructed Workspace instances. Auditor
    helpers use the same path description with their separate checkout checks.
    """
    resolved = Path(repo).resolve()
    relative(rel)
    return Workspace(resolved, rel)
