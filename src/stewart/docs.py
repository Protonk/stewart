"""Operation-time access to bundled guidance; importing this module reads nothing."""
from pathlib import Path

from stewart._bootstrap import StewartError, read_regular

DOCUMENTS = {"manual": "README.md", "questions": "QUESTION-TYPE.md", "protocols": "AUDIT-PROTOCOLS.md",
             "auditor": "AUDITOR.md", "maintainer": "MAINTAINER.md", "agents": "AGENTS.md", "claude": "CLAUDE.md"}


def document(name: str) -> dict:
    """Read a fixed packaged resource, never a source-tree-relative lookup."""
    if name not in DOCUMENTS:
        raise StewartError("select a bundled document", reason="documentation")
    path = Path(__file__).parent / "resources" / DOCUMENTS[name]
    info, data = read_regular(path)
    if data is None:
        raise StewartError("bundled guidance is unavailable", reason="documentation", retained=[str(path)])
    return {"name": name, "path": str(path), "sha256": info["sha256"], "text": data.decode("utf-8")}
