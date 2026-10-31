"""Check the relative links and anchors in the repository's Markdown files.

    python3 -I -B apparatus/check_links.py [ROOT]
    python3 -I -B apparatus/check_links.py --self-test

Reads every Markdown file that Git tracks or sees as untracked and not ignored,
except under service/vendor. Each inline link, image or reference definition
whose target has no URL scheme must name a file or directory in that same Git
listing, so a file that is ignored, deleted or differs only in letter case
counts as missing. A #fragment on a Markdown target, or alone, must match a
heading anchor of that file as GitHub derives it. Fenced code blocks and code
spans hold no links. Symbolic links are checked through the file they name.

Prints each broken link as `file:line: problem: target`, then a count, and
exits 1 if any link is broken, 2 if Git cannot list the files. ROOT is any
directory in the Git work tree to check; it defaults to the repository that
contains this script. --self-test checks the checker on a temporary repository.
Standard library only.
"""

import argparse
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse

SKIP_PREFIXES = ("service/vendor/",)

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)")
HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
INLINE_LINK = re.compile(
    r"\]\(\s*(<[^>\n]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)")
REFERENCE = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>\n]*>|\S+)")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


class GitError(Exception):
    pass


def git(root, *args):
    proc = subprocess.run(["git", "-C", root] + list(args), capture_output=True)
    if proc.returncode != 0:
        raise GitError("git %s failed in %s: %s" % (
            " ".join(args), root, proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


def work_tree(path):
    """The top of the Git work tree that contains path."""
    return git(path, "rev-parse", "--show-toplevel").decode("utf-8", "surrogateescape").strip()


def listed_files(root):
    """Paths Git tracks or sees as untracked and not ignored, present on disk."""
    out = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    names = {n.decode("utf-8", "surrogateescape") for n in out.split(b"\0") if n}
    # A tracked file deleted from the work tree is not there to link to.
    return sorted(n for n in names if os.path.lexists(os.path.join(root, n)))


def prose_lines(text):
    """(line number, line) for each line outside fenced code blocks."""
    fence = None
    for number, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                continue
            yield number, line
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                and not line.strip()[len(m.group(1)):].strip():
            fence = None


def plain(segment):
    """The text GitHub renders from Markdown outside a code span."""
    segment = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", segment)
    segment = re.sub(r"<[^>]+>", "", segment)
    # Underscores that delimit emphasis disappear; intraword ones stay.
    return re.sub(r"(?<![0-9A-Za-z])_+|_+(?![0-9A-Za-z])", "", segment)


def heading_text(raw):
    """A heading's rendered text: code spans verbatim, other markup removed."""
    out, pos = [], 0
    for m in CODE_SPAN.finditer(raw):
        out.append(plain(raw[pos:m.start()]))
        out.append(m.group(2))
        pos = m.end()
    out.append(plain(raw[pos:]))
    return "".join(out).strip()


def slug(text):
    """GitHub's anchor for a heading text (github-slugger, before deduplication)."""
    kept = (c for c in text.lower()
            if c in " -" or unicodedata.category(c)[0] in "LMN" or unicodedata.category(c) == "Pc")
    return "".join(kept).replace(" ", "-")


def anchors(text):
    """Every heading anchor of a Markdown text; repeats get -1, -2, ... as on GitHub."""
    seen = set()
    counts = {}
    for _, line in prose_lines(text):
        m = HEADING.match(line)
        if not m:
            continue
        base = slug(heading_text(m.group(1) or ""))
        result = base
        while result in seen:
            counts[base] = counts.get(base, 0) + 1
            result = "%s-%d" % (base, counts[base])
        seen.add(result)
    return seen


def link_targets(text):
    """(line number, target) for each link or reference definition outside code."""
    for number, line in prose_lines(text):
        line = CODE_SPAN.sub("", line)
        for pattern in (INLINE_LINK, REFERENCE):
            for m in pattern.finditer(line):
                target = m.group(1)
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1]
                yield number, target


def read(root, name):
    with open(os.path.join(root, name), encoding="utf-8", errors="replace") as f:
        return f.read()


def check(root):
    """Return (Markdown files read, relative links checked, broken links).

    Each broken link is (file, line, problem, target)."""
    files = listed_files(root)
    present = set(files)
    directories = {""}
    for name in files:
        parent = posixpath.dirname(name)
        while parent not in directories:
            directories.add(parent)
            parent = posixpath.dirname(parent)
    markdown = [n for n in files
                if n.lower().endswith(".md") and not n.startswith(SKIP_PREFIXES)
                and not os.path.islink(os.path.join(root, n))]
    anchor_cache = {}

    def anchors_of(name):
        if name not in anchor_cache:
            anchor_cache[name] = anchors(read(root, name))
        return anchor_cache[name]

    checked = 0
    broken = []
    for name in markdown:
        for line, target in link_targets(read(root, name)):
            if SCHEME.match(target) or target.startswith("//"):
                continue
            checked += 1
            path, has_fragment, fragment = target.partition("#")
            path = urllib.parse.unquote(path)
            if path.startswith("/"):
                resolved = posixpath.normpath(path.lstrip("/"))
            elif path:
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), path))
            else:
                resolved = name
            if resolved == ".":
                resolved = ""
            if resolved == ".." or resolved.startswith("../"):
                broken.append((name, line, "outside the repository", target))
            elif resolved not in present and resolved not in directories:
                broken.append((name, line, "missing", target))
            elif has_fragment and fragment and resolved.lower().endswith(".md") \
                    and resolved in present:
                if urllib.parse.unquote(fragment) not in anchors_of(resolved):
                    broken.append((name, line, "no such heading", target))
    return len(markdown), checked, broken


def report(files, checked, broken):
    for name, line, problem, target in broken:
        print("%s:%d: %s: %s" % (name, line, problem, target))
    print("%d Markdown files, %d relative links, %d broken" % (files, checked, len(broken)))


def self_test():
    """One good link, one missing file and one bad anchor in a new repository:
    passes only if exactly the two bad links are reported."""
    tmp = tempfile.mkdtemp(prefix="check-links-")
    try:
        git(tmp, "init", "-q")
        with open(os.path.join(tmp, "a.md"), "w", encoding="utf-8") as f:
            f.write("# Start\n\n"
                    "[good](b.md#a-good-heading)\n"
                    "[gone](missing.md)\n"
                    "[bad](b.md#no-such-heading)\n")
        with open(os.path.join(tmp, "b.md"), "w", encoding="utf-8") as f:
            f.write("# A good heading\n")
        files, checked, broken = check(work_tree(tmp))
    finally:
        shutil.rmtree(tmp)
    report(files, checked, broken)
    want = [("a.md", 4, "missing", "missing.md"),
            ("a.md", 5, "no such heading", "b.md#no-such-heading")]
    if files == 2 and checked == 3 and sorted(broken) == want:
        print("self-test: passed; the missing file and the bad anchor were reported, the good link was not")
        return 0
    print("self-test: FAILED; expected 2 files, 3 links and exactly these broken links: %r" % want)
    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Check the relative links and #anchors in a Git repository's Markdown files "
                    "(tracked, or untracked and not ignored; service/vendor is skipped). "
                    "Exit status: 0 none broken, 1 some broken, 2 Git could not list the files.")
    parser.add_argument("root", nargs="?",
                        help="a directory in the Git work tree to check "
                             "(default: the repository that contains this script)")
    parser.add_argument("--self-test", action="store_true",
                        help="check the checker on a temporary repository with one good link, "
                             "one missing file and one bad anchor")
    args = parser.parse_args()
    try:
        if args.self_test:
            return self_test()
        root = work_tree(args.root or os.path.dirname(os.path.abspath(__file__)))
        files, checked, broken = check(root)
    except GitError as exc:
        print("check_links: %s" % exc, file=sys.stderr)
        return 2
    report(files, checked, broken)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
