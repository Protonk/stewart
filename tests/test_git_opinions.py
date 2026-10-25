"""scripts/git_opinions.py derives Git opinion rows from source text and rewrites only its marked region.

The script runs here against a small synthetic package, not Stewart's own
source, so these tests pin the script's contracts (marker refusal, the stale
check, content-derived IDs, wrapper discovery and the coverage self-check)
without coupling the suite to the current table.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil

import pytest

pytestmark = pytest.mark.smoke

BEGIN, END = "<!-- git-opinions:begin -->", "<!-- git-opinions:end -->"

GIT_MODULE = '''\
import os
import subprocess


class StewartError(Exception):
    def __init__(self, message, *, reason):
        super().__init__(message)
        self.reason = reason


def _invocation(repo, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE"):
        env.pop(key, None)
    return {"args": ["git", "-c", "core.hooksPath=/dev/null", *args], "cwd": repo, "env": env}


def git(repo, *args, check=True, timeout=120):
    result = subprocess.run(**_invocation(repo, *args), capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise StewartError("git failed", reason="git_failed")
    return result


def git_text(repo, *args):
    return git(repo, *args).stdout.decode().strip()
'''

PROBE = '''\
from stewart._git import StewartError, git, git_text


def _ask(repo, *args):
    return git(repo, "--no-replace-objects", *args, check=False)


def head(repo):
    if git_text(repo, "rev-parse", "--is-bare-repository") != "false":
        raise StewartError("the repository is bare", reason="repository_bare")
    return git_text(repo, "rev-parse", "--verify", "HEAD")


def listing(repo):
    return _ask(repo, "ls-tree", "-r", "-z", "HEAD")
'''


def load_script(tmp_path):
    """Load a copy of scripts/git_opinions.py; it imports no subprocess module, so it starts no process."""
    script = tmp_path / "copy/scripts/git_opinions.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(Path(os.environ["STEWART_TEST_PROJECT"]) / "scripts/git_opinions.py", script)
    spec = importlib.util.spec_from_file_location("git_opinions_under_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "subprocess" not in vars(module), "the script must parse source, never run it"
    return module


def package(tmp_path, probe=PROBE):
    """A synthetic package named stewart: a Git module and one caller."""
    root = tmp_path / "source/stewart"
    root.mkdir(parents=True, exist_ok=True)
    (root / "_git.py").write_text(GIT_MODULE)
    (root / "probe.py").write_text(probe)
    return root


def run(script, *arguments):
    """main()'s exit status, stdout and stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = script.main([str(item) for item in arguments])
    return status, out.getvalue(), err.getvalue()


def ids(markdown):
    return {line.split("`")[1] for line in markdown.splitlines() if line.startswith("| `")}


def test_region_markers_must_appear_once_in_order_and_a_refused_document_is_not_written(tmp_path):
    script, source = load_script(tmp_path), package(tmp_path)
    cases = {
        "missing": "# Guide\n\nno region here\n",
        "repeated": f"{BEGIN}\n{END}\n{BEGIN}\n{END}\n",
        "reversed": f"before\n{END}\nmiddle\n{BEGIN}\nafter\n",
    }
    for name, text in cases.items():
        document = tmp_path / f"{name}.md"
        document.write_text(text)
        for mode in ("--write", "--check"):
            status, out, err = run(script, "--source", source, "--document", document, mode)
            assert status == 2, (name, mode, out, err)
            assert "refused" in err and "nothing was written" in err, err
            assert document.read_text() == text, f"{name}: a refused {mode} changed the document"
    real = tmp_path / "real.md"
    real.write_text(f"{BEGIN}\n{END}\n")
    link = tmp_path / "link.md"
    link.symlink_to(real)
    status, _, err = run(script, "--source", source, "--document", link, "--write")
    assert status == 2 and "is a link" in err, err
    assert real.read_text() == f"{BEGIN}\n{END}\n" and link.is_symlink()


def test_write_replaces_only_the_region_and_check_follows_the_source(tmp_path):
    script, source = load_script(tmp_path), package(tmp_path)
    before, after = "# Preparing material\n\nHand-written lead.\n\n", "\n\n## Reading the table\n\nHand-written.\n"
    document = tmp_path / "GUIDE.md"
    document.write_text(f"{before}{BEGIN}\nstale rows\n{END}{after}")
    status, generated, _ = run(script, "--source", source)
    assert status == 0 and generated.count("\n### ") == 5, generated
    status, _, err = run(script, "--source", source, "--document", document, "--check")
    assert status == 1 and "stale" in err, "the check must fire on a region that differs"
    status, out, _ = run(script, "--source", source, "--document", document, "--write")
    assert status == 0 and "wrote" in out
    assert document.read_text() == f"{before}{BEGIN}\n{generated}{END}{after}", "bytes outside the region changed"
    assert run(script, "--source", source, "--document", document, "--check")[0] == 0
    status, out, _ = run(script, "--source", source, "--document", document, "--write")
    assert status == 0 and "unchanged" in out
    package(tmp_path, PROBE.replace('"-r", "-z"', '"-d", "-z"'))
    status, _, err = run(script, "--source", source, "--document", document, "--check")
    assert status == 1 and "stale" in err, "a changed flag in the source must make the region stale"


def test_ids_follow_content_not_line_numbers_and_wrappers_are_followed(tmp_path):
    script, source = load_script(tmp_path), package(tmp_path)
    status, first, _ = run(script, "--source", source)
    assert status == 0
    expected = {"cfg.program", "cfg.c.core-hookspath", "cfg.env.set.git-optional-locks", "cfg.env.removed.git-dir",
                "cfg.env.removed.git-work-tree", "inv.rev-parse.verify.head", "inv.rev-parse.is-bare-repository",
                "inv.ls-tree.r-z.head.via-no-replace-objects", "refuse.git_failed._git.git",
                "refuse.repository_bare.probe.head"}
    assert expected <= ids(first), sorted(ids(first))
    assert "probe:listing:15 via probe:_ask:5" in first, "the wrapper's call must be located at its caller"
    # Invariance: shifting every line leaves each ID as it was, while the locations move.
    package(tmp_path, "\n\n\n" + PROBE)
    status, shifted, _ = run(script, "--source", source)
    assert status == 0 and ids(shifted) == ids(first) and shifted != first
    assert "probe:listing:18 via probe:_ask:8" in shifted
    # Differing: a changed flag changes exactly that row's ID.
    package(tmp_path, PROBE.replace('"-r", "-z"', '"-d", "-z"'))
    status, changed, _ = run(script, "--source", source)
    assert status == 0
    assert ids(first) - ids(changed) == {"inv.ls-tree.r-z.head.via-no-replace-objects"}
    assert ids(changed) - ids(first) == {"inv.ls-tree.d-z.head.via-no-replace-objects"}


def test_coverage_lists_a_git_call_that_bypasses_the_helpers(tmp_path):
    script, source = load_script(tmp_path), package(tmp_path)
    status, report, _ = run(script, "--source", source, "--coverage")
    assert status == 0 and "unmatched (0)" in report, report
    assert "probe:listing:15 [_ask] site: inv.ls-tree.r-z.head.via-no-replace-objects" in report, report
    bypass = PROBE.replace("from stewart._git", "import subprocess\nfrom stewart._git") + (
        '\n\ndef raw(repo):\n    return subprocess.run(["git", "status"], cwd=repo)\n')
    package(tmp_path, bypass)
    status, report, _ = run(script, "--source", source, "--coverage")
    assert status == 1, report
    unmatched = report.split("unmatched (", 1)[1]
    assert "probe:raw:20 [subprocess.run] unmatched: a process launch that does not go through _invocation" \
        in unmatched, report
    assert "probe:raw:20 [\"git\"] unmatched: a literal 'git' outside the invocation builder" in unmatched, report
