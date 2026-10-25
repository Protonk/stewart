"""scripts/git_opinions.py derives Git opinion rows from source text and rewrites only its marked region.

Most tests run the script against small synthetic packages, not Stewart's own
source, so they pin the script's contracts (marker and document refusals,
byte-exact rewriting, content-derived IDs, each class's selection, the
coverage detectors) without depending on the current table. The last test
checks the real project: its table is current and the hand-written guide cites
only rows and reasons that exist.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import re
import shutil

import pytest

pytestmark = pytest.mark.smoke

BEGIN, END = b"<!-- git-opinions:begin -->", b"<!-- git-opinions:end -->"

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


def synthetic_case(tmp_path):
    """The script and a synthetic package under a link-free temporary directory (the script refuses links)."""
    tmp = tmp_path.resolve()
    return tmp, load_script(tmp), package(tmp)


def package(tmp, probe=PROBE, **modules):
    """A synthetic package named stewart: a Git module, the probe module and any named extra modules."""
    root = tmp / "source/stewart"
    root.mkdir(parents=True, exist_ok=True)
    (root / "_git.py").write_text(GIT_MODULE)
    (root / "probe.py").write_text(probe)
    for name, text in modules.items():
        (root / f"{name}.py").write_text(text)
    return root


def run(script, *arguments):
    """main()'s exit status, stdout and stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = script.main([str(item) for item in arguments])
    return status, out.getvalue(), err.getvalue()


def rows(markdown):
    """Each generated row's cells, keyed by its ID."""
    found = {}
    for line in markdown.splitlines():
        if line.startswith("| `"):
            cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
            found[cells[0].strip("`")] = cells
    return found


def generate(script, source):
    status, out, err = run(script, "--source", source)
    assert status == 0, err
    return out


# --- the document ----------------------------------------------------------------------------------------


def test_region_markers_must_appear_once_in_order_and_a_refused_document_is_not_written(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    cases = {
        "missing": b"# Guide\n\nno region here\n",
        "repeated": BEGIN + b"\n" + END + b"\n" + BEGIN + b"\n" + END + b"\n",
        "reversed": b"before\n" + END + b"\nmiddle\n" + BEGIN + b"\nafter\n",
    }
    for name, data in cases.items():
        document = tmp / f"{name}.md"
        document.write_bytes(data)
        for mode in ("--write", "--check"):
            status, out, err = run(script, "--source", source, "--document", document, mode)
            assert status == 2, (name, mode, out, err)
            assert "refused" in err and "nothing was written" in err, err
            assert document.read_bytes() == data, f"{name}: a refused {mode} changed the document"


def test_write_replaces_only_the_region_and_check_follows_the_source(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    before, after = b"# Preparing material\n\nHand-written lead.\n\n", b"\n\n## Reading the table\n\nHand-written.\n"
    document = tmp / "GUIDE.md"
    document.write_bytes(before + BEGIN + b"\nstale rows\n" + END + after)
    generated = generate(script, source)
    assert generated.count("\n### ") == 5, generated
    status, _, err = run(script, "--source", source, "--document", document, "--check")
    assert status == 1 and "stale" in err, "the check must fire on a region that differs"
    status, out, _ = run(script, "--source", source, "--document", document, "--write")
    assert status == 0 and "wrote" in out
    assert document.read_bytes() == before + BEGIN + b"\n" + generated.encode() + END + after
    assert run(script, "--source", source, "--document", document, "--check")[0] == 0
    status, out, _ = run(script, "--source", source, "--document", document, "--write")
    assert status == 0 and "unchanged" in out
    package(tmp, PROBE.replace('"-r", "-z"', '"-d", "-z"'))
    status, _, err = run(script, "--source", source, "--document", document, "--check")
    assert status == 1 and "stale" in err, "a changed flag in the source must make the region stale"


def test_bytes_outside_the_region_are_kept_exactly_including_crlf(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    before = b"# Title\r\n\r\nA lead with a lone\rcarriage return and caf\xe9 in Latin-1.\r\n\r\n"
    after = b"\r\n\r\n## After\r\nend\r\n"
    document = tmp / "CRLF.md"
    document.write_bytes(before + BEGIN + b"\r\nstale\r\n" + END + after)
    generated = generate(script, source).encode()
    status, _, err = run(script, "--source", source, "--document", document, "--write")
    assert status == 0, err
    assert document.read_bytes() == before + BEGIN + b"\n" + generated + END + after, "bytes outside changed"
    assert run(script, "--source", source, "--document", document, "--check")[0] == 0


def test_unsafe_documents_are_refused_and_left_unchanged(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    text = BEGIN + b"\n" + END + b"\n"

    def refused(document, mode, expected):
        status, _, err = run(script, "--source", source, "--document", document, mode)
        assert status == 2 and expected in err, (document, mode, err)

    directory = tmp / "directory.md"
    directory.mkdir()
    refused(directory, "--check", "not a regular file")
    fifo = tmp / "fifo.md"
    os.mkfifo(fifo)
    refused(fifo, "--check", "not a regular file")  # refused before opening, so the check cannot hang
    real = tmp / "real.md"
    real.write_bytes(text)
    link = tmp / "link.md"
    link.symlink_to(real)
    refused(link, "--write", "is a link")
    linked_parent = tmp / "linked-directory"
    linked_parent.symlink_to(tmp)
    refused(linked_parent / "real.md", "--write", "reached through the link")
    os.link(real, tmp / "second-name.md")
    refused(real, "--write", "hard links")
    (tmp / "second-name.md").unlink()
    real.chmod(0o444)
    try:
        refused(real, "--write", "read-only")
        assert run(script, "--source", source, "--document", real, "--check")[0] == 1, "a read-only check reads"
    finally:
        real.chmod(0o644)
    assert real.read_bytes() == text and link.is_symlink()
    assert not list(tmp.glob(".real.md.*")), "a refusal before staging leaves no staging file"


def test_a_failed_replacement_keeps_the_staged_bytes(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    document = tmp / "GUIDE.md"
    document.write_bytes(BEGIN + b"\n" + END + b"\n")
    generated = generate(script, source).encode()

    def refuse_replace(*arguments):
        raise OSError("replacement refused by the test")

    original = script.os.replace
    script.os.replace = refuse_replace
    try:
        status, _, err = run(script, "--source", source, "--document", document, "--write")
    finally:
        script.os.replace = original
    assert status == 2 and "replacement refused by the test" in err, err
    staged = re.search(r"staged bytes are kept at (\S+)", err)
    assert staged, err
    assert Path(staged.group(1)).read_bytes() == BEGIN + b"\n" + generated + END + b"\n"
    assert document.read_bytes() == BEGIN + b"\n" + END + b"\n", "the document must stay as it was"


# --- IDs and rendering ------------------------------------------------------------------------------------


def test_ids_follow_content_not_line_numbers_and_wrappers_are_followed(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    first = generate(script, source)
    expected = {"cfg.program", "cfg.c.core-hookspath", "cfg.env.set.git-optional-locks", "cfg.env.removed.git-dir",
                "cfg.env.removed.git-work-tree", "inv.rev-parse.verify.head", "inv.rev-parse.is-bare-repository",
                "inv.ls-tree.r-z.head.via-no-replace-objects", "refuse.git_failed._git.git",
                "refuse.repository_bare.probe.head"}
    assert expected <= set(rows(first)), sorted(rows(first))
    assert rows(first)["inv.ls-tree.r-z.head.via-no-replace-objects"][3] == "probe:listing via probe:_ask", \
        "the wrapper's call is held at its caller, named without a line number"
    # Invariance: shifting every line changes nothing in the table.
    package(tmp, "\n\n\n" + PROBE)
    assert generate(script, source) == first
    # Differing: a changed flag changes exactly that row's ID.
    package(tmp, PROBE.replace('"-r", "-z"', '"-d", "-z"'))
    changed = set(rows(generate(script, source)))
    assert set(rows(first)) - changed == {"inv.ls-tree.r-z.head.via-no-replace-objects"}
    assert changed - set(rows(first)) == {"inv.ls-tree.d-z.head.via-no-replace-objects"}


def test_duplicate_ids_stop_generation(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    assert run(script, "--source", source)[0] == 0
    package(tmp, PROBE + '\n\ndef blob(repo, rev, path):\n    return git(repo, "show", f"{rev}:{path}")\n'
                         '\n\ndef commit(repo, rev):\n    return git(repo, "show", rev)\n')
    status, out, err = run(script, "--source", source)
    assert status == 2 and "two rows would share the ID inv.show" in err and not out, err


def test_generated_text_holding_a_marker_is_refused(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, PROBE + '\n\ndef odd(repo):\n    return git(repo, "show", "<!-- git-opinions:end -->")\n')
    status, out, err = run(script, "--source", source)
    assert status == 2 and "contains a region marker" in err and not out, err


def test_git_failed_reason_follows_the_check_argument(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    table = rows(generate(script, source))
    assert table["inv.rev-parse.verify.head"][4] == "`git_failed`", "git_text keeps git's default check"
    assert table["inv.ls-tree.r-z.head.via-no-replace-objects"][4] == "", "check=False reads the exit status"
    package(tmp, PROBE.replace('return git_text(repo, "rev-parse", "--verify", "HEAD")',
                               'return git(repo, "rev-parse", "--verify", "HEAD", check=False)'))
    assert rows(generate(script, source))["inv.rev-parse.verify.head"][4] == ""


# --- the classes ------------------------------------------------------------------------------------------


REFS = '''\
from stewart._git import git


def branch_tip(repo, name):
    ref = f"refs/heads/{name}"
    return git(repo, "for-each-ref", "--format=%(objectname)", ref, check=False)
'''


def test_refs_are_listed_by_namespace_with_their_git_uses(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    assert not [row for row in rows(generate(script, source)) if row.startswith("ref.")]
    package(tmp, refs=REFS)
    first = rows(generate(script, source))
    assert first["ref.refs-heads"][1] == ("`refs/heads/<name>`: passed to Git: "
                                         "`inv.for-each-ref.format-objectname.refs-heads`."), first["ref.refs-heads"]
    package(tmp, refs=REFS.replace("ref = ", "target = ").replace("ref, check", "target, check"))
    assert rows(generate(script, source))["ref.refs-heads"] == first["ref.refs-heads"], "a local's name is not content"
    package(tmp, refs=REFS.replace("refs/heads/", "refs/tags/"))
    renamed = rows(generate(script, source))
    assert "ref.refs-tags" in renamed and "ref.refs-heads" not in renamed


ADMIN = '''\
import os
from pathlib import Path


def registered(common):
    return os.listdir(Path(common) / "worktrees")


def lock_reason(git_admin):
    return (Path(git_admin) / "locked").read_bytes()
'''


def test_administration_paths_are_listed_with_what_the_code_does(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    assert not [row for row in rows(generate(script, source)) if row.startswith("adm.")]
    package(tmp, admin=ADMIN)
    first = rows(generate(script, source))
    assert first["adm.common.worktrees"][1:4] == ["`<common>/worktrees`: listed.", "administration",
                                                  "admin:registered"], first["adm.common.worktrees"]
    assert first["adm.git-admin.locked"][1] == "`<git-admin>/locked`: read."
    package(tmp, admin=ADMIN.replace("def registered", "def listed").replace("def lock_reason", "def reason"))
    renamed = rows(generate(script, source))
    assert [renamed[key][1] for key in ("adm.common.worktrees", "adm.git-admin.locked")] == \
        [first[key][1] for key in ("adm.common.worktrees", "adm.git-admin.locked")]
    assert renamed["adm.common.worktrees"][3] == "admin:listed"
    package(tmp, admin=ADMIN.replace('"locked"', '"gitdir"'))
    changed = rows(generate(script, source))
    assert "adm.git-admin.gitdir" in changed and "adm.git-admin.locked" not in changed


MUTATION = '''\
from stewart._git import StewartError, git_text


def roots(repo):
    found = []
    for line in git_text(repo, "worktree", "list", "--porcelain").splitlines():
        found.append(line)
    return found


def require_registered(repo, path):
    if path not in roots(repo):
        raise StewartError("the path is not registered", reason="not_registered")
'''


def test_refusal_derivation_follows_container_mutation(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, mutation=MUTATION)
    row = rows(generate(script, source)).get("refuse.not_registered.mutation.require_registered")
    assert row and row[1] == "“the path is not registered”", "a list built by append from Git output is derived"
    comprehension = MUTATION.replace(
        '    found = []\n    for line in git_text(repo, "worktree", "list", "--porcelain").splitlines():\n'
        '        found.append(line)\n    return found\n',
        '    return [line for line in git_text(repo, "worktree", "list", "--porcelain").splitlines()]\n')
    package(tmp, mutation=comprehension)
    assert rows(generate(script, source)).get("refuse.not_registered.mutation.require_registered") == row
    package(tmp, mutation=MUTATION.replace(
        'for line in git_text(repo, "worktree", "list", "--porcelain").splitlines():', "for line in [repo]:"))
    assert "refuse.not_registered.mutation.require_registered" not in rows(generate(script, source)), \
        "appending a value Git did not report derives nothing"


DEPTH = '''\
from stewart._git import StewartError, git_text


def level1(repo):
    return git_text(repo, "rev-parse", "--show-toplevel")


def level2(repo):
    return level1(repo)


def level3(repo):
    return level2(repo)


def guarded_two(repo):
    if level2(repo) != "/":
        raise StewartError("two levels", reason="depth_two")


def guarded_three(repo):
    if level3(repo) != "/":
        raise StewartError("three levels", reason="depth_three")
'''


def test_refusal_derivation_stops_at_the_source_depth(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, depth=DEPTH)
    table = rows(generate(script, source))
    assert script.SOURCE_DEPTH == 2
    assert "refuse.depth_two.depth.guarded_two" in table, "a value two calls from Git is derived"
    assert "refuse.depth_three.depth.guarded_three" not in table, "three calls from Git is beyond the depth"


# --- coverage ---------------------------------------------------------------------------------------------


def coverage(script, source):
    status, report, _ = run(script, "--source", source, "--coverage")
    return status, report


def section(report, title):
    """The entries listed under one coverage heading."""
    lines = report.split(f"[git-opinions] {title} (", 1)[1].splitlines()[1:]
    return [line.strip() for line in lines[:next((i for i, line in enumerate(lines) if line.startswith("[")),
                                                 len(lines))] if line.strip() != "none"]


def test_coverage_passes_a_package_whose_git_goes_through_the_helpers(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    status, report = coverage(script, source)
    assert status == 0 and "passed: 0 problems" in report, report
    assert "probe:listing:15 [_ask] site: inv.ls-tree.r-z.head.via-no-replace-objects" in report, report


def test_coverage_flags_a_literal_git_outside_the_invocation_builder(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, PROBE + '\n\ndef argv():\n    return ["git", "status"]\n')
    status, report = coverage(script, source)
    assert status == 1
    assert section(report, "raw-scan hits nothing accounts for") == [
        "probe:argv:19 [\"git\"] unmatched: a literal 'git' outside the invocation builder"], report


def test_coverage_flags_a_process_launch_outside_the_invocation_builder(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, "import subprocess\n" + PROBE + "\n\ndef launch(command):\n    return subprocess.run(command)\n")
    status, report = coverage(script, source)
    assert status == 1
    assert section(report, "raw-scan hits nothing accounts for") == [
        "probe:launch:20 [subprocess.run] unmatched: a process launch that does not go through _invocation"], report


def test_coverage_flags_a_git_helper_referenced_without_a_call(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, PROBE + "\n\nRUNNER = git\n")
    status, report = coverage(script, source)
    assert status == 1
    assert section(report, "raw-scan hits nothing accounts for") == [
        "probe:<module>:18 [git] unmatched: Git helper referenced without a call"], report


def test_coverage_reports_unresolved_invocations_instead_of_rows(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, PROBE + '\n\ndef collect(repo, record):\n    return git(repo, *record["options"], "gc")\n'
                         '\n\ndef history(repo):\n    args = ["log"]\n    args.append("--all")\n'
                         '    return git(repo, *args)\n')
    status, report = coverage(script, source)
    assert status == 1
    unresolved = section(report, "unresolved invocations (no row is made)")
    assert len(unresolved) == 2, report
    assert unresolved[0].startswith("probe:collect:19:") and "stands where the command could be" in unresolved[0]
    assert unresolved[1].startswith("probe:history:25:") and "changed by a method call" in unresolved[1]
    assert section(report, "raw-scan hits nothing accounts for") == []
    assert not [row for row in rows(generate(script, source)) if ".gc" in row or row.startswith("inv.log")], \
        "an unresolved call makes no row"


def test_coverage_fails_on_an_option_without_a_gloss_for_its_command(tmp_path):
    tmp, script, source = synthetic_case(tmp_path)
    package(tmp, PROBE + '\n\ndef drop(repo, name):\n    return git(repo, "branch", "-D", name)\n')
    status, report = coverage(script, source)
    assert status == 1
    assert section(report, "commands or options without a gloss for their command") == ["option '-D' of 'branch'"]
    generated = generate(script, source)
    assert rows(generated)["inv.branch.d"][1].startswith("Lists, reads or changes branches."), \
        "a use without a gloss is described only by what is true of every use"
    assert "`inv.branch.d`" in generated.split("Invocation rows whose command writes refs:", 1)[1]


# --- the project ------------------------------------------------------------------------------------------

#: Reason identifiers the guide names as outside the table's classes (it says so where it names them): their
#: refusals are not guarded by anything Git reports, so no row carries them.
OUTSIDE_THE_TABLE = {"checkout_home", "scope_uncovered", "path_symlink", "session_owner_missing",
                     "session_other_maintainer"}


def test_the_project_table_is_current_and_the_guide_cites_existing_rows(tmp_path):
    project = Path(os.environ["STEWART_TEST_PROJECT"]).resolve()
    script, source, document = load_script(tmp_path.resolve()), project / "src/stewart", \
        project / "GIT-ENVIRONMENT-NEEDS.md"
    status, out, err = run(script, "--source", source, "--document", document, "--check")
    assert status == 0, f"regenerate the table with scripts/git_opinions.py --write: {out}{err}"
    table = rows(generate(script, source))
    reasons = {reason for cells in table.values() for reason in re.findall(r"`([a-z_]+)`", cells[4])}
    data = document.read_bytes()
    handwritten = (data[:data.index(BEGIN)] + data[data.index(END):]).decode("utf-8")
    tokens = set(re.findall(r"`([^`\n]+)`", handwritten))
    citations = {token for token in tokens if token.startswith(("cfg.", "inv.", "ref.", "adm.", "refuse."))}
    missing = sorted(token for token in citations if not (
        any(row.startswith(token.rstrip("*")) for row in table) if token.endswith("*") else token in table))
    assert not missing, f"the guide cites rows the table does not hold: {missing}"
    modules = {path.stem for path in source.glob("*.py")}  # module names, such as `verify_inputs`, are not reasons
    named = {token for token in tokens if re.fullmatch(r"[a-z]+(_[a-z]+)+(_\*)?", token)} - modules
    absent = sorted(token for token in named - OUTSIDE_THE_TABLE if not (
        any(reason.startswith(token[:-1]) for reason in reasons) if token.endswith("*") else token in reasons))
    assert not absent, f"the guide names reasons no row carries: {absent}"
