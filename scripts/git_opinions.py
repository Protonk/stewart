"""Derive the table of Git opinions Stewart holds from its Python source.

Stewart's users keep their material in Git. GIT-ENVIRONMENT-NEEDS.md tells
them how to prepare it; its generated region lists what Stewart's code does
with Git. Rows are selected by parsing the source under src/stewart with
``ast``; nothing is imported or run. Each row's description is composed from
fixed glosses of Git's commands and options and of what the code does with a
path, so a row says what the code does in words this script supplies. A
hand-written guide cites rows by ID.

Modes. With no flag the generated Markdown is printed. --write replaces only
the bytes between the git-opinions markers in the document; --check exits 1
when they differ from what would be generated. --coverage compares the call
sites found with a raw textual scan for Git invocations and exits 1 when
anything is unaccounted for (see "Coverage" below).

Rules, by class.

  1. Configuration. Read from _git._invocation, the one function that builds
     every Git argument vector and environment, and from the process launches
     given **_invocation(...). The returned "args" list supplies the program
     and each -c setting; dict(os.environ, NAME=value) supplies inheritance and
     each variable set; env.pop(NAME), directly or over a literal tuple, each
     variable removed. The working directory row classifies the first argument
     of every call to a Git helper (the primitive, a wrapper or a function of
     _git), outside _git itself: the common directory (names or record keys
     common, common_dir, git_common), the process's current directory
     (Path.cwd(), os.getcwd()) or a checkout or repository root. A launch's
     keywords and its function's timeout default supply process handling.

  2. Invocations. Every call that reaches _git._invocation. A wrapper is any
     function that passes one of its own parameters, starred, after the
     repository argument to such a call (searched until nothing changes);
     calls to a wrapper are followed into it with their arguments bound. A
     function whose Git call takes its parameters only as values (such as
     status._git_head or _git.resolve_commit) is not a wrapper: its row is
     where that call is written, and for helpers of _git the row counts their
     callers. An option builder is a function whose every return is a tuple of
     options starting with "-" (such as _repository.checkout_git); it renders
     as the options it builds. Within a function, local assignments, list +=,
     conditional expressions and loops over literal tuples are followed. A
     run of unknown arguments before the command, or a list changed by a
     method call after its assignment, makes the call unresolved: no row is
     made and --coverage fails. One row per distinct global options, command,
     flag set and operand shape. The launch wrapper (the wrapper whose
     template is the primitive inside a process launch) decides the Reason:
     the refusal it raises when its check parameter holds.

  3. Refs. String literals and f-strings starting with refs/, outside
     docstrings, grouped by namespace (the literal text up to the last "/"
     before the first run-time value). Each use is classified where the name
     is written, following a local variable to its uses. A namespace recorded
     in a module (stored under a "ref" key, or listed by a function that
     stores "ref" records) also lists the Git operations of that module that
     take a record's "ref" field.

  4. Administration. Path expressions rooted at the common directory
     (<common>), a worktree's administration (<git-admin>: names or record keys
     git_admin, admin) or a checkout's .git (<checkout>/.git), joined with "/"
     or contained(...), through local variables and functions that return one;
     bare administration directories that are listed, created, written or
     removed; the common directory itself where it is listed in an access
     scope; the literal .git compared with a path component; gitdir: content.
     Uses are classified by the call or operation receiving the path; a path
     placed in a list or record and stored under a key is "listed under" that
     key. Stewart's storage below <common>/stewart collapses to one row per
     subdirectory.

  5. Refusals. raise StewartError(..., reason=...), directly or through a
     function that returns a StewartError, when the raise is guarded by a
     condition or loop over a Git-derived value, or handles an exception from
     work holding one. A value is Git-derived when it comes from a Git helper
     call, from a Git-administration expression in the same function (class 4,
     not Stewart's storage), or from a function whose return value derives
     from those, up to SOURCE_DEPTH levels deep. Derivation follows
     assignment, loops, with, except and container mutation (append, extend,
     insert, add, update). The common directory's path, paths into Stewart's
     storage and Stewart's own installation (__file__) are locations and carry
     nothing. A reason passed in as a parameter is taken from each caller that
     passes a literal; a re-raised exc.reason is not a new refusal.

IDs come from row content: inv.<command>[.<sorted flags>][.<literal operand
words, first three per operand>][.via-<global options>]; cfg.<kind>.<name>;
ref.<namespace>; adm.<root>.<literal segments> (a wholly run-time segment is
"entry", a glob "any", a tuple constant its name); refuse.<reason>.<module>.
<function>. They embed command, option, module, function and constant names,
so an ID is stable while the code holding the opinion is unchanged; a rename
changes it. Two rows with one ID stop generation rather than receive a suffix.

Coverage. Every raw-scan hit (calls of the Git helpers and discovered
wrappers, a literal "git", subprocess and os.exec*/spawn* launches, Git
commands quoted in text) is classified. --coverage exits 1 when a hit is
unmatched, a helper is referenced without a call, an invocation is
unresolved, a wrapper no call reaches, a refusal reason cannot be resolved, a
command appears with an option that has no gloss for that command, or a value
was cut at MAX_VARIANTS alternatives. Reviewed launches that are not Git and
re-raised reasons are listed without failing.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import io
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import tokenize
from typing import NamedTuple

BEGIN = b"<!-- git-opinions:begin -->"
END = b"<!-- git-opinions:end -->"
PACKAGE = "stewart"
#: The function that builds every Git argument vector and environment; invocations are calls that reach it.
PRIMITIVE = ("_git", "_invocation")
#: The Git module: its functions are Git helpers (class 5), and its fixed helpers are listed with their callers.
GIT_MODULE = "_git"
#: Alternatives kept per evaluated value; --coverage fails when any value had more.
MAX_VARIANTS = 24
#: Git commands whose first operand is a verb that belongs to the command name.
VERB_COMMANDS = frozenset({"worktree", "submodule", "remote", "stash", "notes", "bisect", "sparse-checkout"})
#: Names and record keys that denote the Git common directory or a worktree's own administration.
COMMON_KEYS = frozenset({"common", "common_dir", "git_common"})
ADMIN_KEYS = frozenset({"git_admin", "admin"})
#: Calls that pass a path or string through unchanged for the purposes of this table.
TRANSPARENT = frozenset({"str", "Path", "PurePosixPath", "fsdecode", "fspath", "normpath"})
#: Calls that name the process's current directory.
CURRENT_DIRECTORY = frozenset({"cwd", "getcwd"})
#: Container methods that put a value into the container they are called on (class 5 derivation, class 2
#: unresolved lists).
MUTATORS = frozenset({"append", "extend", "insert", "add", "update", "appendleft", "extendleft", "setdefault"})
#: Git commands that always write refs; `branch` and `symbolic-ref` write only in the forms ref_writes() names.
REF_WRITERS = frozenset({"update-ref", "tag", "commit", "reset", "checkout", "switch", "merge", "rebase", "fetch",
                         "pull", "push", "notes", "replace", "stash", "cherry-pick", "revert", "am"})
BRANCH_WRITING_OPTIONS = frozenset({"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-f",
                                    "--force", "--set-upstream-to", "-u", "--unset-upstream", "--edit-description"})

#: What a call does with a path passed to it, by the called name (class 4).
PATH_VERBS = {
    "read_regular": "read", "capture_receipt": "read", "read_receipt": "read", "_read": "read",
    "read_bytes": "read", "read_text": "read", "loads_control": "read",
    "write_receipt": "written as an exclusive record", "_record": "written as an exclusive record",
    "_publish": "written as an exclusive record", "write_text": "written", "write_bytes": "written",
    "listdir": "listed", "open_directory": "listed", "_names": "listed", "iterdir": "listed",
    "list_records": "listed", "scandir": "listed", "walk": "listed",
    "pinned": "opened without following links",
    "lexists": "checked", "exists": "checked", "is_dir": "checked", "is_symlink": "checked", "is_file": "checked",
    "lstat": "checked", "stat": "checked", "_regular": "checked", "isdir": "checked", "islink": "checked",
    "remove": "removed", "remove_path": "removed", "remove_empty": "removed", "rmdir": "removed",
    "unlink": "removed", "rmtree": "removed",
    "mkdir": "created", "private_directories": "created", "makedirs": "created",
    "contained": "resolved below without links",
}
#: Levels of functions whose return values count as Git-derived for refusals (class 5); see Tables._sources.
SOURCE_DEPTH = 2
#: Uses shown for Stewart's own records below <common>/stewart (other uses name internal functions).
STORAGE_VERBS = frozenset({"read", "written as an exclusive record", "written", "listed", "checked", "removed",
                           "opened without following links", "resolved below without links", "compared",
                           "named in a refusal"})
#: Uses of a bare administration directory (no literal fragment) that make it a class-4 row.
BARE_ADMIN_VERBS = frozenset({"removed", "created", "listed", "opened without following links",
                              "written as an exclusive record", "written"})

#: Glosses of Git commands. Each is true of the command in any form; what a particular use does is said by
#: the glosses of its options, which are keyed by command so that one option is never described out of context.
COMMAND_GLOSS = {
    "branch": "Lists, reads or changes branches",
    "cat-file": "Reads objects from the object database",
    "diff": "Compares commits, the index and the working tree",
    "for-each-ref": "Lists refs",
    "ls-files": "Lists paths in the index or working tree",
    "ls-tree": "Lists a committed tree",
    "merge-base": "Computes or tests merge bases",
    "rev-list": "Lists commits",
    "rev-parse": "Resolves a name or a repository location",
    "show": "Shows objects",
    "status": "Reports working-tree and index status",
    "symbolic-ref": "Reads, writes or deletes a symbolic ref",
    "update-ref": "Writes or deletes refs",
    "worktree add": "Creates a linked worktree",
    "worktree list": "Lists the worktrees Git registers",
    "worktree lock": "Locks a linked worktree with a reason",
    "worktree unlock": "Unlocks a linked worktree",
}
#: Glosses of global options (before the command) and of command options, keyed "command option". An option
#: ending in "=" glosses every value of it.
GLOBAL_GLOSS = {
    "--git-dir=": "addresses a verified administration directly, never through `.git`",
    "--work-tree=": "names the checkout explicitly",
    "--no-replace-objects": "replacement objects ignored",
}
OPTION_GLOSS = {
    "branch --show-current": "reads the checked-out branch's name, empty when detached",
    "cat-file -e": "tests that an object exists",
    "cat-file --batch": "batch reads on standard input",
    "diff --binary": "binary patches",
    "diff --cached": "against the index",
    "diff --full-index": "full object IDs",
    "diff --name-only": "names only",
    "diff --no-ext-diff": "no external diff driver",
    "diff --no-renames": "no rename detection",
    "diff --no-textconv": "no textconv filter",
    "diff -z": "NUL-delimited",
    "for-each-ref --contains": "only refs containing a commit",
    "for-each-ref --format=": "named fields only",
    "ls-files --error-unmatch": "every path must be tracked",
    "ls-files --others": "untracked paths",
    "ls-files -z": "NUL-delimited",
    "ls-tree --full-tree": "the whole tree",
    "ls-tree --name-only": "names only",
    "ls-tree -d": "directories only",
    "ls-tree -r": "recursively",
    "ls-tree -z": "NUL-delimited",
    "merge-base --is-ancestor": "tests whether one commit is an ancestor of another",
    "rev-list --parents": "with parent IDs",
    "rev-list -n": "a limited count",
    "rev-parse --absolute-git-dir": "the worktree's administration directory",
    "rev-parse --git-common-dir": "the common directory",
    "rev-parse --is-bare-repository": "whether the repository is bare",
    "rev-parse --path-format=absolute": "absolute paths",
    "rev-parse --show-toplevel": "the working tree's top level",
    "rev-parse --verify": "the name must resolve",
    "status --ignored": "ignored files included",
    "status --porcelain=v1": "porcelain v1 format",
    "status --untracked-files=all": "every untracked file",
    "status -z": "NUL-delimited",
    "symbolic-ref --quiet": "tests whether the ref is symbolic, quietly",
    "symbolic-ref -q": "tests whether the ref is symbolic, quietly",
    "update-ref --no-deref": "never through a symbolic ref",
    "update-ref --stdin": "one transaction on standard input",
    "update-ref -d": "deletes, checking the old value when one is given",
    "worktree add --detach": "detached HEAD",
    "worktree add --lock": "locked from creation",
    "worktree add --reason": "with a lock reason",
    "worktree add -b": "on a new branch",
    "worktree list --porcelain": "porcelain format",
    "worktree list -z": "NUL-delimited",
    "worktree lock --reason": "with a lock reason",
}
CONFIG_GLOSS = {
    "core.hooksPath=/dev/null": "Hooks never run: Git looks for them in `/dev/null`.",
    "core.fsmonitor=false": "No file-system monitor runs.",
}
ENVIRONMENT_GLOSS = {
    "GIT_OPTIONAL_LOCKS": "Git takes no optional locks, so read-only commands do not rewrite the index.",
    "GIT_DIR": "An inherited value cannot redirect which repository Git addresses.",
    "GIT_WORK_TREE": "An inherited value cannot redirect which working tree Git addresses.",
    "GIT_INDEX_FILE": "An inherited value cannot redirect which index Git reads or writes.",
    "GIT_COMMON_DIR": "An inherited value cannot redirect the common directory.",
}
#: Raw-scan hits reviewed by hand as launching something other than Git, keyed by
#: (module, function, matched text). --coverage prints them separately and names stale entries.
REVIEWED = {
    ("experiment", "_run", "subprocess.Popen"):
        "starts the released experiment's own argv in the auditor checkout; it is the manager-reviewed "
        "experiment, not a Git command Stewart composes",
    ("__main__", "<module>", "os.execv"): "re-executes Stewart's own bootstrap under isolated Python",
}
#: Values cut at MAX_VARIANTS alternatives since the last reset; --coverage fails when nonzero.
TRUNCATIONS = {"count": 0}


class Refusal(Exception):
    """A problem that stops the script, with the message printed as the failure."""


class Hole(NamedTuple):
    """A value the source computes at run time, shown as <text>."""
    text: str


class Spread(NamedTuple):
    """An unknown run of arguments, shown as *text."""
    text: str


class Unknown(NamedTuple):
    """A run of arguments the evaluator cannot follow (why says how); a call holding one is unresolved."""
    text: str
    why: str


class Choice(NamedTuple):
    """One of several literal values drawn from a named tuple constant."""
    values: tuple
    label: str


#: Elements of an argument vector that stand for a run of arguments rather than one scalar. Hole, Spread and
#: Unknown are tuples themselves, so every helper below tests for these before treating an element as parts.
RUNS = (Spread, Unknown)


def short(node: ast.AST, limit: int = 34) -> str:
    """Compact source text for a run-time value."""
    text = " ".join(ast.unparse(node).split())
    if len(text) <= limit:
        return text
    if isinstance(node, ast.Call):
        name = " ".join(ast.unparse(node.func).split())
        if len(name) <= limit - 3:
            return f"{name}(…)"
    return text[:limit - 1] + "…"


def merge(parts: tuple) -> tuple:
    """Join adjacent literal parts."""
    out: list = []
    for part in parts:
        if isinstance(part, str) and out and isinstance(out[-1], str):
            out[-1] += part
        elif part != "":
            out.append(part)
    return tuple(out)


def unique(variants: list) -> list:
    seen, out = set(), []
    for variant in variants:
        if variant not in seen:
            seen.add(variant)
            out.append(variant)
    if len(out) > MAX_VARIANTS:
        TRUNCATIONS["count"] += 1
    return out[:MAX_VARIANTS]


def concat(left: list, right: list) -> list:
    """Every pairing of two lists of alternatives, joined in order."""
    pairs = [a + b for a in left for b in right]
    if len(pairs) > MAX_VARIANTS * 4:
        TRUNCATIONS["count"] += 1
    return unique(pairs[:MAX_VARIANTS * 4])


def literal(element) -> str | None:
    """The text of a purely literal scalar, else None."""
    if isinstance(element, RUNS) or isinstance(element, Hole):
        return None
    if isinstance(element, tuple) and all(isinstance(part, str) for part in element):
        return "".join(element)
    return None


def leading(element) -> str:
    """The literal text a scalar starts with ('' for a hole or a run of arguments)."""
    if isinstance(element, RUNS) or isinstance(element, Hole):
        return ""
    if isinstance(element, tuple) and element and isinstance(element[0], str):
        return element[0]
    return ""


def show(element, quote: bool = True) -> str:
    """Display form: literal text, <holes>, {choices}, *runs; quoted when a literal part holds a space."""
    if isinstance(element, RUNS):
        return "*" + element.text
    text = "".join(part if isinstance(part, str) else f"<{part.text}>" if isinstance(part, Hole)
                   else "{" + ",".join(part.values) + "}" for part in element)
    spaced = any(isinstance(part, str) and " " in part for part in element)
    return f'"{text}"' if quote and (spaced or not text) else text


def norm(element) -> str:
    """Key form: holes become <>, runs *, choices {label}; names of run-time values do not matter."""
    if isinstance(element, RUNS):
        return "*"
    return "".join(part if isinstance(part, str) else "<>" if isinstance(part, Hole) else "{" + part.label + "}"
                   for part in element)


def slug(text: str) -> str:
    """Lowercase words joined by hyphens; Git format atoms keep their names."""
    text = re.sub(r"%[0-9A-Fa-f]{2}", "", text)
    text = re.sub(r"%\(([^)]*)\)", r"-\1-", text)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def literal_slug(element, words: int | None = None) -> str:
    """A slug of an element's literal parts only; holes and runs contribute nothing."""
    if isinstance(element, RUNS):
        return ""
    text = " ".join(part if isinstance(part, str) else " ".join(part.values) if isinstance(part, Choice) else " "
                    for part in element)
    value = slug(text.lstrip("-"))
    return "-".join(value.split("-")[:words]) if words and value else value


def cell(text: str) -> str:
    """Prose safe inside a Markdown table cell."""
    text = " ".join(text.split()).replace("`", "'").replace("|", "\\|")
    return text.replace("<", "&lt;").replace(">", "&gt;")


def code(text: str) -> str:
    """A code span safe inside a Markdown table cell."""
    text = text.replace("|", "\\|")
    fence = "``" if "`" in text else "`"
    pad = " " if fence == "``" else ""
    return f"{fence}{pad}{text}{pad}{fence}"


# --- source model --------------------------------------------------------------------------------------


class Function:
    """One def: its parameters, imports, nested defs and the nodes it owns directly."""

    def __init__(self, module: "Module", node: ast.FunctionDef, parent: "Function | None", qualname: str):
        self.module, self.node, self.parent, self.qualname = module, node, parent, qualname
        self.key = (module.name, qualname)
        arguments = node.args
        self.positional = [item.arg for item in arguments.posonlyargs + arguments.args]
        self.vararg = arguments.vararg.arg if arguments.vararg else None
        self.kwonly = [item.arg for item in arguments.kwonlyargs]
        self.defaults = dict(zip(self.positional[len(self.positional) - len(arguments.defaults):], arguments.defaults))
        self.defaults.update({item.arg: value for item, value in zip(arguments.kwonlyargs, arguments.kw_defaults)
                              if value is not None})
        self.params = {*self.positional, *self.kwonly}
        self.params.update(name for name in (self.vararg, arguments.kwarg.arg if arguments.kwarg else None) if name)
        self.imports: dict = {}
        self.children: dict = {}
        self.assignments: dict = defaultdict(list)
        self.nodes: list = []

    def location(self, line: int) -> str:
        return f"{self.module.name}:{self.qualname}:{line}"

    def place(self) -> str:
        return f"{self.module.name}:{self.qualname}"


class Module:
    """One parsed source file, with parent links, owners, imports and module constants."""

    def __init__(self, name: str, path: Path):
        self.name, self.path = name, path
        try:
            self.text = path.read_text(encoding="utf-8")
            self.tree = ast.parse(self.text, filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
            raise Refusal(f"cannot read the source {path}: {exc}") from exc
        self.lines = self.text.splitlines()
        self.parent = {child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)}
        self.owner: dict = {}
        self.defs: dict = {}
        self.imports: dict = {}
        self.constants: dict = {}
        self.docstrings: set = set()
        self.functions: list = []
        self._visit(self.tree, None, "")

    def location(self, fn: Function | None, line: int) -> str:
        return fn.location(line) if fn else f"{self.name}:<module>:{line}"

    def place(self, fn: Function | None) -> str:
        """Where an opinion is held, for Stewart's users: module and function, no line number."""
        return fn.place() if fn else f"{self.name}:<module>"

    def _visit(self, node: ast.AST, fn: Function | None, prefix: str) -> None:
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                self.docstrings.add(first.value)
        for child in ast.iter_child_nodes(node):
            self.owner[child] = fn
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = Function(self, child, fn, prefix + child.name)
                self.functions.append(function)
                if fn is not None:
                    fn.children[child.name] = function
                elif not prefix:
                    self.defs[child.name] = function
                self._visit(child, function, function.qualname + ".")
                continue
            if isinstance(child, ast.ClassDef):
                self._visit(child, fn, prefix + child.name + ".")
                continue
            if fn is not None:
                fn.nodes.append(child)
            self._record(child, fn)
            self._visit(child, fn, prefix)

    def _record(self, node: ast.AST, fn: Function | None) -> None:
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and \
                (node.module == PACKAGE or node.module.startswith(PACKAGE + ".")):
            base = node.module[len(PACKAGE) + 1:]
            target = fn.imports if fn else self.imports
            for alias in node.names:
                target[alias.asname or alias.name] = ("module", alias.name) if not base else ("name", base, alias.name)
        elif isinstance(node, ast.Assign):
            if fn is None:
                if self.parent.get(node) is self.tree and len(node.targets) == 1 \
                        and isinstance(node.targets[0], ast.Name):
                    self.constants[node.targets[0].id] = node.value
                return
            for target in node.targets:
                if isinstance(target, ast.Name):
                    fn.assignments[target.id].append((node.lineno, "assign", node))
                else:
                    for name in _target_names(target):
                        fn.assignments[name].append((node.lineno, "opaque", node))
        elif fn is not None and isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            fn.assignments[node.target.id].append((node.lineno, "assign", node))
        elif fn is not None and isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            fn.assignments[node.target.id].append((node.lineno, "augment", node))
        elif fn is not None and isinstance(node, (ast.For, ast.AsyncFor)):
            for name in _target_names(node.target):
                fn.assignments[name].append((node.lineno, "opaque", node))
        elif fn is not None and isinstance(node, ast.withitem) and node.optional_vars is not None:
            for name in _target_names(node.optional_vars):
                fn.assignments[name].append((getattr(node.optional_vars, "lineno", 0), "opaque", node))
        elif fn is not None and isinstance(node, ast.ExceptHandler) and node.name:
            fn.assignments[node.name].append((node.lineno, "opaque", node))


def _target_names(target: ast.AST) -> list[str]:
    return [node.id for node in ast.walk(target) if isinstance(node, ast.Name)]


class Source:
    """Every module under the package root, with name and call resolution across them."""

    def __init__(self, root: Path):
        self.root = root
        paths = sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
        if not paths:
            raise Refusal(f"no Python source under {root}")
        self.modules: dict = {}
        for path in paths:
            name = ".".join(path.relative_to(root).with_suffix("").parts)
            self.modules[name] = Module(name, path)
        self.functions = {fn.key: fn for module in self.modules.values() for fn in module.functions}

    def lookup(self, name: str, fn: Function | None, module: Module):
        """What a bare name means at a point: ('function', F), ('module', name), ('constant', module, node) or None."""
        scope = fn
        while scope is not None:
            if name in scope.children:
                return ("function", scope.children[name])
            if name in scope.imports:
                return self._imported(scope.imports[name])
            scope = scope.parent
        if name in module.defs:
            return ("function", module.defs[name])
        if name in module.constants:
            return ("constant", module, module.constants[name])
        if name in module.imports:
            return self._imported(module.imports[name])
        return None

    def _imported(self, entry: tuple, depth: int = 0):
        if entry[0] == "module":
            return ("module", entry[1]) if entry[1] in self.modules else None
        _, base, attr = entry
        if f"{base}.{attr}" in self.modules:
            return ("module", f"{base}.{attr}")
        target = self.modules.get(base)
        if target is None:
            return None
        if attr in target.defs:
            return ("function", target.defs[attr])
        if attr in target.constants:
            return ("constant", target, target.constants[attr])
        if attr in target.imports and depth < 4:
            return self._imported(target.imports[attr], depth + 1)
        return None

    def callee(self, func: ast.AST, fn: Function | None, module: Module) -> Function | None:
        """The package function a call's target names, or None."""
        found = None
        if isinstance(func, ast.Name):
            found = self.lookup(func.id, fn, module)
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            alias = self.lookup(func.value.id, fn, module)
            if alias and alias[0] == "module":
                target = self.modules[alias[1]]
                found = ("function", target.defs[func.attr]) if func.attr in target.defs else None
        return found[1] if found and found[0] == "function" else None


def called_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def is_stewart_error(func: ast.AST) -> bool:
    return called_name(func) == "StewartError"


# --- symbolic evaluation -------------------------------------------------------------------------------


class Scope(NamedTuple):
    module: Module
    fn: Function | None
    bindings: dict
    parent: "Scope | None"


class Binding(NamedTuple):
    kind: str  # "expr": one node; "varargs": the nodes passed to a *args parameter
    value: object
    scope: Scope


class Expansion(NamedTuple):
    argv: tuple
    via: tuple  # (function key, template line) for each wrapper that adds arguments
    check: object  # True when a Git failure refuses, False when tolerated, None when unknown
    stdin: bool


class Site(NamedTuple):
    module: Module
    fn: Function | None
    node: ast.Call
    expansion: Expansion


OPAQUE = object()


class Analysis:
    """Everything the five classes need, computed once from a Source."""

    def __init__(self, source: Source):
        self.source = source
        if PRIMITIVE not in source.functions:
            raise Refusal(f"{source.root} defines no {PRIMITIVE[0]}.{PRIMITIVE[1]}; every rule starts there")
        TRUNCATIONS["count"] = 0
        self.option_builders: dict = {}
        self.string_helpers: dict = {}
        self.wrappers: dict = {}
        self._discover_string_helpers()
        self._discover_option_builders()
        self._discover_wrappers()
        self.template_ids = {id(node) for templates in self.wrappers.values() for node in templates}
        self.launch_wrappers = self._discover_launch_wrappers()
        self.sites = self._find_sites()
        self.calls_to = defaultdict(list)  # function key -> [(module, fn, call)]
        for module in source.modules.values():
            for node in ast.walk(module.tree):
                if isinstance(node, ast.Call):
                    fn = module.owner.get(node)
                    target = source.callee(node.func, fn, module)
                    if target is not None:
                        self.calls_to[target.key].append((module, fn, node))

    # evaluation --------------------------------------------------------------------------------------

    def scope_for(self, fn: Function | None, module: Module, bindings: dict | None = None) -> Scope:
        parent = self.scope_for(fn.parent, module) if fn is not None and fn.parent is not None else None
        return Scope(module, fn, bindings or {}, parent)

    def scalar(self, node: ast.AST, scope: Scope, depth: int = 0) -> list:
        if depth > 40:
            return [(Hole(short(node)),)]
        deeper = depth + 1
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bytes):
                value = value.decode("utf-8", "replace")
            return [(str(value),)] if isinstance(value, (str, int, float)) else [(Hole(repr(value)),)]
        if isinstance(node, ast.JoinedStr):
            variants: list = [()]
            for value in node.values:
                part = [(value.value,)] if isinstance(value, ast.Constant) else self.scalar(value.value, scope, deeper)
                variants = concat(variants, part)
            return unique([merge(variant) for variant in variants])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return unique([merge(variant) for variant in
                           concat(self.scalar(node.left, scope, deeper), self.scalar(node.right, scope, deeper))])
        if isinstance(node, ast.IfExp):
            return unique(self.scalar(node.body, scope, deeper) + self.scalar(node.orelse, scope, deeper))
        if isinstance(node, ast.Name):
            return self.name(node, scope, "scalar", deeper)
        if isinstance(node, ast.Call):
            if called_name(node.func) in TRANSPARENT and len(node.args) == 1 and not node.keywords:
                return self.scalar(node.args[0], scope, deeper)
            target = self.source.callee(node.func, scope.fn, scope.module)
            if target is not None and target.key in self.string_helpers:
                return self.string_helpers[target.key]
        return [(Hole(short(node)),)]

    def seq(self, node: ast.AST, scope: Scope, depth: int = 0) -> list:
        if depth > 40:
            return [(Spread(short(node)),)]
        deeper = depth + 1
        if isinstance(node, (ast.List, ast.Tuple)):
            return self.arguments(node.elts, scope, deeper)
        if isinstance(node, ast.Starred):
            return self.seq(node.value, scope, deeper)
        if isinstance(node, ast.Name):
            return self.name(node, scope, "seq", deeper)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return concat(self.seq(node.left, scope, deeper), self.seq(node.right, scope, deeper))
        if isinstance(node, ast.IfExp):
            return unique(self.seq(node.body, scope, deeper) + self.seq(node.orelse, scope, deeper))
        if isinstance(node, ast.Call):
            target = self.source.callee(node.func, scope.fn, scope.module)
            if target is not None and target.key in self.option_builders:
                return self.option_builders[target.key]
            if isinstance(node.func, ast.Name) and node.func.id in ("list", "tuple", "sorted") \
                    and len(node.args) == 1 and not node.keywords:
                inner = self.seq(node.args[0], scope, deeper)
                if all(len(variant) == 1 and isinstance(variant[0], Spread) for variant in inner):
                    return [(Spread(short(node)),)]
                return inner
        return [(Spread(short(node)),)]

    def arguments(self, nodes: list, scope: Scope, depth: int = 0) -> list:
        variants: list = [()]
        for node in nodes:
            part = self.seq(node.value, scope, depth) if isinstance(node, ast.Starred) \
                else [(value,) for value in self.scalar(node, scope, depth)]
            variants = concat(variants, part)
        return variants

    def name(self, node: ast.Name, scope: Scope, want: str, depth: int) -> list:
        ident = node.id
        unknown = [(Spread(ident),)] if want == "seq" else [(Hole(ident),)]
        current = scope
        while current is not None:
            if ident in current.bindings:
                return self.bound(current.bindings[ident], want, depth)
            fn = current.fn
            if fn is not None:
                elements = self.loop_elements(node, ident, fn)
                if elements is OPAQUE:
                    return unknown
                if elements is not None:
                    out: list = []
                    for element in elements:
                        out += self.seq(element, current, depth) if want == "seq" else self.scalar(element, current, depth)
                    return unique(out)
                assigned = self.assigned(fn, ident, node.lineno, current, want, depth)
                if assigned is not None:
                    return assigned
                if ident in fn.params:
                    return unknown
            current = current.parent
        found = self.source.lookup(ident, scope.fn, scope.module)
        if found and found[0] == "constant":
            constant = Scope(found[1], None, {}, None)
            return self.seq(found[2], constant, depth) if want == "seq" else self.scalar(found[2], constant, depth)
        return unknown

    def bound(self, binding: Binding, want: str, depth: int) -> list:
        if binding.kind == "varargs":
            if want == "scalar":
                return [(Hole("…"),)]
            return self.arguments(binding.value, binding.scope, depth)
        if want == "seq":
            return self.seq(binding.value, binding.scope, depth)
        return self.scalar(binding.value, binding.scope, depth)

    def loop_elements(self, node: ast.AST, ident: str, fn: Function):
        """The literal elements a for loop or comprehension binds ident to around node; OPAQUE when not literal."""
        module = fn.module
        child, current = node, module.parent.get(node)
        while current is not None and current is not fn.node:
            generators = []
            if isinstance(current, (ast.For, ast.AsyncFor)) and child is not current.iter:
                generators = [(current.target, current.iter)]
            elif isinstance(current, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                generators = [(item.target, item.iter) for item in current.generators if item.iter is not child]
            for target, iterable in generators:
                if isinstance(target, ast.Name) and target.id == ident:
                    return self.literal_elements(iterable, fn)
                if ident in _target_names(target):
                    return OPAQUE
            child, current = current, module.parent.get(current)
        return None

    def literal_elements(self, iterable: ast.AST, fn: Function):
        if isinstance(iterable, (ast.Tuple, ast.List)):
            return list(iterable.elts)
        if isinstance(iterable, ast.Name):
            found = self.source.lookup(iterable.id, fn, fn.module)
            if found and found[0] == "constant" and isinstance(found[2], (ast.Tuple, ast.List)):
                return list(found[2].elts)
        return OPAQUE

    def assigned(self, fn: Function, ident: str, line: int, scope: Scope, want: str, depth: int):
        """The value of the last assignment to ident before line, with later += applied; None when unassigned."""
        every = fn.assignments.get(ident, [])
        entries = [entry for entry in every if entry[0] < line]
        bases = [index for index, entry in enumerate(entries) if entry[1] in ("assign", "opaque")]
        if not bases:
            return None if not every else ([(Spread(ident),)] if want == "seq" else [(Hole(ident),)])
        base_line, kind, statement = entries[bases[-1]]
        if kind == "opaque":
            return [(Spread(ident),)] if want == "seq" else [(Hole(ident),)]
        if want == "seq" and self.mutated(fn, ident, base_line, line):
            return [(Unknown(ident, "a list changed by a method call after its assignment"),)]
        evaluate = self.seq if want == "seq" else self.scalar
        value = evaluate(statement.value, scope, depth)
        if all(len(variant) == 1 and isinstance(variant[0], (Hole, Spread)) for variant in value):
            # Computed at run time: the variable's own name says more than the expression it came from.
            value = [(Spread(ident),)] if want == "seq" else [(Hole(ident),)]
        for _, kind, statement in entries[bases[-1] + 1:]:
            if kind == "augment" and isinstance(statement.op, ast.Add):
                value = concat(value, evaluate(statement.value, scope, depth))
                if want == "scalar":
                    value = [merge(variant) for variant in value]
        return unique(value)

    def mutated(self, fn: Function, ident: str, after: int, before: int) -> bool:
        """Whether a mutating method is called on ident between an assignment and a use."""
        return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in MUTATORS and isinstance(node.func.value, ast.Name)
                   and node.func.value.id == ident and after <= node.lineno <= before for node in fn.nodes)

    # discovery ---------------------------------------------------------------------------------------

    def _returns(self, fn: Function) -> list[ast.Return]:
        return [node for node in fn.nodes if isinstance(node, ast.Return) and node.value is not None]

    def _discover_string_helpers(self) -> None:
        """Functions whose body is one return of a string built from literals and parameters."""
        for fn in self.source.functions.values():
            body = [statement for statement in fn.node.body
                    if not (isinstance(statement, ast.Expr) and statement.value in fn.module.docstrings)]
            if len(body) != 1 or not isinstance(body[0], ast.Return) \
                    or not isinstance(body[0].value, (ast.JoinedStr, ast.BinOp)):
                continue
            value = self.scalar(body[0].value, self.scope_for(fn, fn.module))
            if all(any(isinstance(part, str) and part.strip() for part in variant) for variant in value):
                self.string_helpers[fn.key] = value

    def _discover_option_builders(self) -> None:
        """Functions whose every return is Git global options: literals or templates starting with '-'."""
        changed = True
        while changed:
            changed = False
            for fn in self.source.functions.values():
                if fn.key in self.option_builders:
                    continue
                returns = self._returns(fn)
                if not returns:
                    continue
                values: list = []
                for statement in returns:
                    if isinstance(statement.value, ast.Call):
                        target = self.source.callee(statement.value.func, fn, fn.module)
                        if target is None or target.key not in self.option_builders:
                            break
                        values += self.option_builders[target.key]
                    elif isinstance(statement.value, (ast.Tuple, ast.List)) and statement.value.elts:
                        found = self.seq(statement.value, self.scope_for(fn, fn.module))
                        if not all(variant and all(not isinstance(element, Spread) and leading(element).startswith("-")
                                                   for element in variant) for variant in found):
                            break
                        values += found
                    else:
                        break
                else:
                    self.option_builders[fn.key] = unique(values)
                    changed = True

    def _discover_wrappers(self) -> None:
        """Functions that pass one of their own parameters, starred, into a call that reaches the primitive."""
        while True:
            found: dict = {}
            helpers = {PRIMITIVE, *self.wrappers}
            for fn in self.source.functions.values():
                if fn.key == PRIMITIVE:
                    continue
                templates = []
                for node in fn.nodes:
                    if not isinstance(node, ast.Call):
                        continue
                    target = self.source.callee(node.func, fn, fn.module)
                    if target is None or target.key not in helpers:
                        continue
                    if any(isinstance(item, ast.Starred) and isinstance(item.value, ast.Name)
                           and item.value.id in fn.params for item in node.args[1:]):
                        templates.append(node)
                if templates:
                    found[fn.key] = templates
            if found.keys() == self.wrappers.keys() and all(
                    [id(node) for node in found[key]] == [id(node) for node in self.wrappers[key]] for key in found):
                return
            self.wrappers = found

    def launches(self) -> list[tuple]:
        """Process launches fed by **_invocation(...): (owning function, the launching call)."""
        found = []
        for fn in self.source.functions.values():
            for node in fn.nodes:
                if isinstance(node, ast.Call) and any(
                        keyword.arg is None and isinstance(keyword.value, ast.Call)
                        and (target := self.source.callee(keyword.value.func, fn, fn.module)) is not None
                        and target.key == PRIMITIVE for keyword in node.keywords):
                    found.append((fn, node))
        return found

    def _discover_launch_wrappers(self) -> dict:
        """Wrappers whose template is the primitive inside a process launch, with the reason they refuse with.

        The reason is the literal one of the StewartError the wrapper raises under a condition naming its
        ``check`` parameter; such a wrapper decides whether a nonzero exit refuses.
        """
        found = {}
        for fn, launch in self.launches():
            if fn.key not in self.wrappers or "check" not in fn.params:
                continue
            reasons = set()
            for node in fn.nodes:
                if isinstance(node, ast.If) and any(isinstance(item, ast.Name) and item.id == "check"
                                                    for item in ast.walk(node.test)):
                    for raised in ast.walk(node):
                        if isinstance(raised, ast.Raise) and isinstance(raised.exc, ast.Call) \
                                and is_stewart_error(raised.exc.func):
                            reasons |= {keyword.value.value for keyword in raised.exc.keywords
                                        if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant)}
            found[fn.key] = ", ".join(sorted(reasons))
        return found

    def bind(self, target: Function, call: ast.Call, scope: Scope) -> dict:
        bindings: dict = {}
        rest: list = []
        index = 0
        for item in call.args:
            if rest or isinstance(item, ast.Starred) or index >= len(target.positional):
                rest.append(item)
            else:
                bindings[target.positional[index]] = Binding("expr", item, scope)
                index += 1
        if target.vararg:
            bindings[target.vararg] = Binding("varargs", rest, scope)
        for keyword in call.keywords:
            if keyword.arg:
                bindings[keyword.arg] = Binding("expr", keyword.value, scope)
        for name, default in target.defaults.items():
            bindings.setdefault(name, Binding("expr", default, Scope(target.module, None, {}, None)))
        return bindings

    def trivial(self, target: Function, template: ast.Call) -> bool:
        """A template that forwards exactly the wrapper's *args adds nothing worth naming."""
        rest = template.args[1:]
        return bool(target.vararg) and len(rest) == 1 and isinstance(rest[0], ast.Starred) \
            and isinstance(rest[0].value, ast.Name) and rest[0].value.id == target.vararg

    def truth(self, binding: Binding | None):
        if binding is None:
            return True
        values = {literal(variant) for variant in self.scalar(binding.value, binding.scope)}
        return True if values == {"True"} else False if values == {"False"} else None

    def expand(self, call: ast.Call, scope: Scope, depth: int = 0) -> list[Expansion]:
        """Every argument vector a call that reaches the primitive can produce, through each wrapper."""
        target = self.source.callee(call.func, scope.fn, scope.module)
        if target is None or depth > 12:
            return []
        if target.key == PRIMITIVE:
            return [Expansion(argv, (), None, False) for argv in self.arguments(call.args[1:], scope)]
        templates = self.wrappers.get(target.key)
        if not templates:
            return []
        bindings = self.bind(target, call, scope)
        inner = Scope(target.module, target, bindings, self.scope_for(target.parent, target.module)
                      if target.parent else None)
        check, stdin = None, False
        if target.key in self.launch_wrappers:
            truth = self.truth(bindings.get("check"))
            check = self.launch_wrappers[target.key] if truth is True else "" if truth is False else None
            given = bindings.get("input")
            stdin = given is not None and not (isinstance(given.value, ast.Constant) and given.value.value is None)
        out = []
        for template in templates:
            note = () if self.trivial(target, template) else ((target.key, template.lineno),)
            for expansion in self.expand(template, inner, depth + 1):
                out.append(Expansion(expansion.argv, note + expansion.via,
                                     check if check is not None else expansion.check, stdin or expansion.stdin))
        return out

    def _find_sites(self) -> list[Site]:
        sites = []
        helpers = {PRIMITIVE, *self.wrappers}
        for module in self.source.modules.values():
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.Call) or id(node) in self.template_ids:
                    continue
                fn = module.owner.get(node)
                target = self.source.callee(node.func, fn, module)
                if target is None or target.key not in helpers:
                    continue
                for expansion in self.expand(node, self.scope_for(fn, module)):
                    sites.append(Site(module, fn, node, expansion))
        return sites


# --- class 2: invocations ------------------------------------------------------------------------------


class Parsed(NamedTuple):
    globals: tuple
    sub: str
    flags: tuple
    operands: tuple


def parse_argv(argv: tuple) -> tuple[Parsed | None, str]:
    """Split an argument vector into global options, the command, its flags and its operands.

    Returns the parse, or None and why the vector is unresolved: it holds a run the evaluator could not
    follow, a run of unknown arguments stands where the command could be, or no literal command appears.
    """
    unknown = [element for element in argv if isinstance(element, Unknown)]
    if unknown:
        return None, f"*{unknown[0].text} is {unknown[0].why}"
    index = 0
    while index < len(argv):
        element = argv[index]
        if isinstance(element, Spread):
            return None, f"*{element.text}, a run of unknown arguments, stands where the command could be"
        text = literal(element)
        if text is not None and not text.startswith("-"):
            break
        if not leading(element).startswith("-"):
            return None, f"{show(element)} stands where the command should be"
        index += 1
    if index == len(argv):
        return None, "no literal command"
    globals_, words = argv[:index], [literal(argv[index])]
    index += 1
    if words[0] in VERB_COMMANDS and index < len(argv):
        verb = literal(argv[index])
        if verb is not None and not verb.startswith("-"):
            words.append(verb)
            index += 1
    flags, operands = [], []
    for element in argv[index:]:
        (flags if not isinstance(element, RUNS) and leading(element).startswith("-") else operands).append(element)
    return Parsed(globals_, " ".join(words), tuple(flags), tuple(operands)), ""


def invocation_key(parsed: Parsed) -> tuple:
    return (tuple(norm(item) for item in parsed.globals), parsed.sub,
            tuple(sorted({norm(item) for item in parsed.flags})), tuple(norm(item) for item in parsed.operands))


def invocation_id(parsed: Parsed) -> str:
    parts = ["inv", slug(parsed.sub)]
    flags = sorted({value for value in (literal_slug(item) for item in parsed.flags) if value})
    if flags:
        parts.append("-".join(flags))
    operands = [value for value in (literal_slug(item, words=3) for item in parsed.operands) if value]
    if operands:
        parts.append("-".join(operands))
    options = sorted({value for value in (literal_slug(item) if not isinstance(item, Spread) else slug(item.text)
                                          for item in parsed.globals) if value})
    if options:
        parts.append("via-" + "-".join(options))
    return ".".join(parts)


def option_gloss(element, sub: str) -> str | None:
    """The gloss of an option as used with a command (sub is "" for a global option), or None."""
    text = literal(element)
    text = leading(element) if text is None else text
    table, prefix = (GLOBAL_GLOSS, "") if not sub else (OPTION_GLOSS, sub + " ")
    if prefix + text in table:
        return table[prefix + text]
    if "=" in text and prefix + text.split("=", 1)[0] + "=" in table:
        return table[prefix + text.split("=", 1)[0] + "="]
    return None


def ref_writes(parsed: Parsed) -> bool:
    """Whether an invocation's command writes refs."""
    flags = {literal(item) or leading(item).split("=", 1)[0] for item in parsed.flags}
    if parsed.sub in REF_WRITERS:
        return True
    if parsed.sub == "worktree add":
        return bool(flags & {"-b", "-B"})
    if parsed.sub == "branch":
        return bool(flags & BRANCH_WRITING_OPTIONS) or (bool(parsed.operands) and not flags & {
            "--show-current", "--list", "-l", "--contains", "--merged", "--no-merged", "--points-at"})
    if parsed.sub == "symbolic-ref":
        return bool(flags & {"-d", "--delete"}) or len(parsed.operands) >= 2
    return False


# --- the five classes ----------------------------------------------------------------------------------


class Row(NamedTuple):
    id: str
    cls: str
    group: str
    opinion: str  # Markdown
    where: tuple
    reason: str


def location_order(text: str):
    """Sort key for module:function[:line] strings, module first, then line when present."""
    module, _, rest = text.partition(":")
    function, _, tail = rest.partition(" ")
    number = re.search(r":(\d+)$", function)
    return (module, int(number.group(1)) if number else 0, function, text)


class Tables:
    """Rows of every class, and what --coverage reports about how they were found."""

    def __init__(self, source: Source):
        self.source = source
        self.analysis = Analysis(source)
        self.site_rows: dict = defaultdict(set)  # id(call node) -> row IDs
        self.fn_rows: dict = defaultdict(set)  # function key -> row IDs of the sites it holds
        self.parsed_rows: dict = {}  # invocation row ID -> its parsed argument vector
        self.unresolved: list = []  # (site, why)
        self.gloss_gaps: set = set()
        self._location_cache: dict = {}
        self.invocations = self._invocations()
        self.configuration = self._configuration()
        self.administration, self.local_nodes, self.path_nodes = self._administration()
        self.refs, self.ref_writers = self._refs()
        self.refusals, self.unresolved_reasons, self.reraised = self._refusals()
        rows = [*self.configuration, *self.invocations, *self.refs, *self.administration, *self.refusals]
        seen: dict = {}
        for row in rows:
            if row.id in seen:
                raise Refusal(f"two rows would share the ID {row.id} ({seen[row.id]} and {', '.join(row.where)}); "
                              "refine the ID rule in scripts/git_opinions.py so content distinguishes them")
            seen[row.id] = ", ".join(row.where)

    # class 1 -----------------------------------------------------------------------------------------

    def _configuration(self) -> list[Row]:
        analysis = self.analysis
        fn = self.source.functions[PRIMITIVE]
        where = (fn.place(),)
        scope = analysis.scope_for(fn, fn.module)
        rows: list[Row] = []
        group = "Configuration"
        returned = [node.value for node in fn.nodes if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)]
        if len(returned) != 1:
            raise Refusal(f"{fn.location(fn.node.lineno)} no longer returns one dict; the configuration rule "
                          "reads its 'args', 'cwd' and 'env' keys")
        fields = {key.value: value for key, value in zip(returned[0].keys, returned[0].values)
                  if isinstance(key, ast.Constant)}
        if "args" not in fields or not isinstance(fields["args"], (ast.List, ast.Tuple)):
            raise Refusal(f"{fn.location(fn.node.lineno)} returns no literal 'args' list")
        elements = fields["args"].elts
        program = literal(analysis.scalar(elements[0], scope)[0]) if elements else None
        if program is None:
            raise Refusal(f"{fn.location(fn.node.lineno)}: the program name is not a literal")
        resolution = "resolved through the inherited `PATH`; no absolute Git path is configured" \
            if "/" not in program else "named by absolute path"
        rows.append(Row("cfg.program", "configuration", group, f"Runs the program {code(program)}, {resolution}.",
                        where, ""))
        for index, element in enumerate(elements[:-1]):
            if isinstance(element, ast.Constant) and element.value == "-c":
                setting = show(analysis.scalar(elements[index + 1], scope)[0], quote=False)
                gloss = CONFIG_GLOSS.get(setting, "")
                rows.append(Row("cfg.c." + slug(setting.split("=", 1)[0]), "configuration", group,
                                f"Every Git command gets {code('-c ' + setting)}. {gloss}".strip(), where, ""))
        if "cwd" in fields:
            rows.append(self._working_directory_row(fields["cwd"], where, group))
        environment = fields.get("env")
        assigned = None
        if isinstance(environment, ast.Name):
            entries = fn.assignments.get(environment.id, [])
            assigned = entries[0][2].value if entries and entries[0][1] == "assign" else None
        if isinstance(assigned, ast.Call) and called_name(assigned.func) == "dict":
            if assigned.args and ast.unparse(assigned.args[0]) == "os.environ":
                rows.append(Row("cfg.env.inherited", "configuration", group,
                                "Git inherits Stewart's whole environment, apart from the variables below.",
                                where, ""))
            for keyword in assigned.keywords:
                value = show(analysis.scalar(keyword.value, scope)[0], quote=False)
                rows.append(Row("cfg.env.set." + slug(keyword.arg), "configuration", group,
                                f"Sets {code(f'{keyword.arg}={value}')}. {ENVIRONMENT_GLOSS.get(keyword.arg, '')}"
                                .strip(), where, ""))
        for node in fn.nodes:
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "pop" \
                    and isinstance(environment, ast.Name) and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == environment.id and node.args:
                for variant in analysis.scalar(node.args[0], scope):
                    name = literal(variant)
                    if name is None:
                        continue
                    rows.append(Row("cfg.env.removed." + slug(name), "configuration", group,
                                    f"Removes {code(name)} from the environment. {ENVIRONMENT_GLOSS.get(name, '')}"
                                    .strip(), where, ""))
        # The process launches that consume the invocation: how output, input and time limits are handled.
        for owner, call in sorted(analysis.launches(), key=lambda item: item[0].key):
            words = []
            keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
            if "capture_output" in keywords or "stdout" in keywords:
                words.append("captures Git's output")
            if "stdin" not in keywords:
                words.append("Git's standard input is Stewart's own unless the caller passes `input`"
                             if "input" in keywords else "Git's standard input is Stewart's own")
            else:
                words.append(f"standard input is {code(short(keywords['stdin']))}")
            timeout = owner.defaults.get("timeout")
            if timeout is not None and isinstance(timeout, ast.Constant):
                words.append(f"stops Git after {timeout.value} seconds unless the caller passes `timeout`")
            rows.append(Row(f"cfg.process.{slug(owner.qualname)}", "configuration", group,
                            f"{code(owner.qualname)} {'; '.join(words)}.", (owner.place(),), ""))
        return rows

    def _working_directory_row(self, cwd: ast.AST, where: tuple, group: str) -> Row:
        """Where Git runs: the first argument of each call to a Git helper outside the Git module, by kind."""
        helpers = {PRIMITIVE, *self.analysis.wrappers} | {key for key in self.source.functions if key[0] == GIT_MODULE}
        kinds: dict = defaultdict(set)
        for key in helpers:
            for module, caller, call in self.analysis.calls_to.get(key, []):
                if module.name == GIT_MODULE or not call.args or isinstance(call.args[0], ast.Starred):
                    continue
                kinds[self._directory_kind(call.args[0])].add(module.place(caller))
        statement = f"Git runs in the directory each caller passes ({code('cwd=' + short(cwd))}): a checkout or " \
                    "repository root"
        named = {"common": "the Git common directory", "current": "the process's current directory"}
        exceptions = [f"{named[kind]} in " + ", ".join(f"`{place}`" for place in sorted(kinds[kind]))
                      for kind in ("common", "current") if kinds.get(kind)]
        if exceptions:
            statement += ", except " + "; and ".join(exceptions)
        statement += ". Without `--git-dir`, Git discovers the repository from there."
        return Row("cfg.cwd", "configuration", group, statement, where, "")

    @staticmethod
    def _directory_kind(node: ast.AST) -> str:
        while isinstance(node, ast.Call) and called_name(node.func) in TRANSPARENT and len(node.args) == 1:
            node = node.args[0]
        if isinstance(node, ast.Call) and called_name(node.func) in CURRENT_DIRECTORY:
            return "current"
        key = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else \
            node.slice.value if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) else None
        return "common" if key in COMMON_KEYS else "root"

    # class 2 -----------------------------------------------------------------------------------------

    def _invocations(self) -> list[Row]:
        analysis = self.analysis
        groups: dict = defaultdict(list)
        for site in analysis.sites:
            parsed, why = parse_argv(site.expansion.argv)
            if parsed is None:
                self.unresolved.append((site, why))
                continue
            groups[invocation_key(parsed)].append((site, parsed))
        rows = []
        for members in groups.values():
            parsed = min((item[1] for item in members), key=lambda item: " ".join(show(e) for e in item.globals + item.flags))
            row_id = invocation_id(parsed)
            self.parsed_rows[row_id] = parsed
            forms = sorted({"git " + " ".join(show(element) for element in site.expansion.argv) for site, _ in members})
            where, refusals, stdin = set(), set(), False
            for site, _ in members:
                self.site_rows[id(site.node)].add(row_id)
                if site.fn is not None:
                    self.fn_rows[site.fn.key].add(row_id)
                via = "".join(f" via {key[0]}:{key[1]}" for key, _ in site.expansion.via)
                where.add(site.module.place(site.fn) + via)
                refusals.add(site.expansion.check or "")
                stdin = stdin or site.expansion.stdin
            where_list = sorted(where, key=location_order)
            used_by = self._used_by({site.fn.key for site, _ in members if site.fn is not None
                                     and site.fn.module.name == GIT_MODULE and site.fn.key not in analysis.wrappers})
            if used_by:
                where_list.append(used_by)
            gloss = COMMAND_GLOSS.get(parsed.sub)
            if gloss is None:
                self.gloss_gaps.add(f"command {parsed.sub!r}")
                gloss = f"Runs {code('git ' + parsed.sub)}"
            notes = []
            for sub, elements in (("", parsed.globals), (parsed.sub, parsed.flags)):
                for element in elements:
                    if literal(element) == "--":
                        continue
                    note = option_gloss(element, sub)
                    if note is None:
                        option = show(element, quote=False)
                        self.gloss_gaps.add(f"option {option!r} of {sub!r}" if sub else f"global option {option!r}")
                    elif note not in notes:
                        notes.append(note)
            if stdin:
                notes.append("input on standard input")
            statement = gloss + ("; " + "; ".join(notes) if notes else "") + "."
            extra = len(forms) - 3
            shown = forms[:3] + ([f"… {extra} more form{'s' if extra > 1 else ''}"] if extra > 0 else [])
            opinion = statement + "<br>" + "<br>".join(code(form) if not form.startswith("…") else form
                                                       for form in shown)
            named = sorted(value for value in refusals if value)
            if named and "" not in refusals:
                reason = ", ".join(f"`{value}`" for value in named)
            elif named:
                reason = ", ".join(f"`{value}`" for value in named) + " at some sites; others read the exit status"
            else:
                reason = ""
            rows.append(Row(row_id, "invocation", "git " + parsed.sub, opinion, tuple(where_list), reason))
        return sorted(rows, key=lambda row: (row.group, row.id))

    def _used_by(self, keys: set) -> str:
        """Callers of fixed helpers in the Git module, counted by module."""
        counts: dict = defaultdict(int)
        names = []
        for key in sorted(keys):
            names.append(key[1])
            for module, _, _ in self.analysis.calls_to.get(key, []):
                counts[module.name] += 1
        if not counts:
            return ""
        return "used through " + ", ".join(f"`{name}`" for name in names) + " by " + ", ".join(
            f"{module} ({count})" for module, count in sorted(counts.items()))

    # class 3 -----------------------------------------------------------------------------------------

    def _refs(self) -> tuple[list[Row], list[str]]:
        analysis = self.analysis
        namespaces: dict = defaultdict(lambda: {"forms": set(), "uses": defaultdict(set), "modules": set()})
        for module in self.source.modules.values():
            for node in ast.walk(module.tree):
                if node in module.docstrings or isinstance(module.parent.get(node), ast.JoinedStr):
                    continue
                if not ((isinstance(node, ast.Constant) and isinstance(node.value, str)
                         and node.value.startswith("refs/"))
                        or (isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[0], ast.Constant)
                            and str(node.values[0].value).startswith("refs/"))):
                    continue
                fn = module.owner.get(node)
                for variant in analysis.scalar(node, analysis.scope_for(fn, module)):
                    prefix = leading(variant)
                    if len(variant) > 1 or not literal(variant):
                        prefix = prefix[:prefix.rfind("/") + 1] if "/" in prefix else prefix
                    entry = namespaces[prefix]
                    entry["forms"].add(show(variant, quote=False))
                    for use in self._ref_uses(node, fn, module):
                        entry["uses"][use].add(module.place(fn))
                    if self._recorded_ref(node, fn, module):
                        entry["modules"].add(module.name)
        # A recorded namespace also lists the module's Git operations on a record's "ref" field.
        field_operations = self._ref_field_operations()
        for entry in namespaces.values():
            for module_name in entry["modules"]:
                for place, rows in field_operations.get(module_name, []):
                    for row in rows:
                        entry["uses"][f"recorded refs {self._ref_verb(row)} by `{row}`"].add(place)
        rows = []
        for prefix, entry in namespaces.items():
            forms = ", ".join(code(form) for form in sorted(entry["forms"]))
            uses = self._annotated(entry["uses"])
            where = sorted({item for places in entry["uses"].values() for item in places}, key=location_order)
            rows.append(Row("ref." + slug(prefix.rstrip("/") or prefix), "ref", "Refs", f"{forms}: {uses}.",
                            tuple(where), ""))
        writers = sorted(row_id for row_id, parsed in self.parsed_rows.items() if ref_writes(parsed))
        return sorted(rows, key=lambda row: row.id), writers

    @staticmethod
    def _ref_field(node: ast.AST) -> bool:
        """Whether an expression reads a record's "ref" field: x["ref"] or x.get("ref")."""
        return any((isinstance(item, ast.Subscript) and isinstance(item.slice, ast.Constant) and item.slice.value == "ref")
                   or (isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr == "get"
                       and item.args and isinstance(item.args[0], ast.Constant) and item.args[0].value == "ref")
                   for item in ast.walk(node))

    def _recorded_ref(self, node: ast.AST, fn: Function | None, module: Module) -> bool:
        """A ref name stored under a "ref" key, or written in a function that stores "ref" records."""
        parent = module.parent.get(node)
        if isinstance(parent, ast.Dict) and node in parent.values:
            key = parent.keys[parent.values.index(node)]
            if isinstance(key, ast.Constant) and key.value == "ref":
                return True
        return fn is not None and any(isinstance(item, ast.Dict) and any(
            isinstance(key, ast.Constant) and key.value == "ref" for key in item.keys) for item in fn.nodes)

    def _ref_field_operations(self) -> dict:
        """Per module, the Git operations (sites, or calls of functions holding sites) given a record's ref field."""
        found: dict = defaultdict(list)
        for module in self.source.modules.values():
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = module.owner.get(node)
                rows = set(self.site_rows.get(id(node), ()))
                if not rows:
                    target = self.source.callee(node.func, fn, module)
                    rows = set(self.fn_rows.get(target.key, ())) if target is not None else set()
                if rows and any(self._ref_field(argument) for argument in
                                [*node.args, *(keyword.value for keyword in node.keywords)]):
                    found[module.name].append((module.place(fn), rows))
        return found

    def _ref_verb(self, row_id: str) -> str:
        parsed = self.parsed_rows.get(row_id)
        flags = {literal(item) for item in parsed.flags} if parsed else set()
        if parsed and parsed.sub == "update-ref":
            return "deleted" if "-d" in flags else "created" if "--stdin" in flags else "written"
        return "written" if parsed and ref_writes(parsed) else "read"

    @staticmethod
    def _annotated(uses: dict) -> str:
        """Uses joined; a use that holds at only one or two of a row's places names them."""
        every = {place for places in uses.values() for place in places}
        out = []
        for use, places in sorted(uses.items()):
            if len(places) <= 2 and places != every and len(every) > 1:
                use += " (in " + ", ".join(f"`{place}`" for place in sorted(places)) + ")"
            out.append(use)
        return "; ".join(out)

    def _ref_uses(self, node: ast.AST, fn: Function | None, module: Module, depth: int = 0) -> set[str]:
        """How a ref name is used where it is written: passed to Git, tested, recorded or refused."""
        child, current = node, module.parent.get(node)
        while current is not None and depth < 6:
            if isinstance(current, ast.Call):
                if id(current) in self.site_rows:
                    return {"passed to Git: " + ", ".join(f"`{row}`" for row in sorted(self.site_rows[id(current)]))}
                if isinstance(current.func, ast.Attribute) and current.func.attr == "startswith" \
                        and child is not current.func:
                    return {"prefix test"}
                if is_stewart_error(current.func):
                    return {"named in a refusal"}
                target = self.source.callee(current.func, fn, module)
                if target is not None and target.key in self.fn_rows:
                    return {f"passed to `{target.qualname}`: " + ", ".join(f"`{row}`"
                                                                         for row in sorted(self.fn_rows[target.key]))}
                if called_name(current.func) in TRANSPARENT:
                    child, current = current, module.parent.get(current)
                    continue
                return {"recorded"}
            if isinstance(current, ast.keyword):
                if current.arg == "retained":
                    return {"named in a refusal"}
            elif isinstance(current, ast.Assign) and len(current.targets) == 1 \
                    and isinstance(current.targets[0], ast.Name) and fn is not None:
                uses = set()
                for later in fn.nodes:
                    if isinstance(later, ast.Name) and later.id == current.targets[0].id \
                            and isinstance(later.ctx, ast.Load) and later.lineno >= current.lineno:
                        uses |= self._ref_uses(later, fn, module, depth + 1)
                return uses or {"assigned"}
            elif isinstance(current, ast.Compare):
                return {"compared"}
            elif isinstance(current, ast.Return):
                return {f"returned by `{fn.qualname if fn else '<module>'}`"}
            elif isinstance(current, ast.stmt):
                return {"recorded"}
            child, current = current, module.parent.get(current)
        return {"recorded"}

    # class 4 -----------------------------------------------------------------------------------------

    def path_shape(self, node: ast.AST, fn: Function | None, module: Module, depth: int = 0):
        """The administration path an expression names, as (root, *segments), or None."""
        if depth > 12:
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = self.path_shape(node.left, fn, module, depth + 1)
            right = self.segments(node.right, fn, module)
            if left is None:
                if right == ((".git",),):
                    return ("<checkout>",) + right
                return None
            return left + right
        if isinstance(node, ast.Name):
            if node.id in COMMON_KEYS:
                return ("<common>",)
            if node.id in ADMIN_KEYS:
                return ("<git-admin>",)
            if fn is not None:
                entries = [entry for entry in fn.assignments.get(node.id, []) if entry[0] < node.lineno]
                if entries and entries[-1][1] == "assign":
                    return self.path_shape(entries[-1][2].value, fn, module, depth + 1)
            return None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            key = node.slice.value
            return ("<common>",) if key in COMMON_KEYS else ("<git-admin>",) if key in ADMIN_KEYS else None
        if isinstance(node, ast.Attribute):
            return ("<common>",) if node.attr in COMMON_KEYS else ("<git-admin>",) if node.attr in ADMIN_KEYS \
                else None
        if isinstance(node, ast.Call):
            name = called_name(node.func)
            if name in TRANSPARENT and len(node.args) == 1:
                return self.path_shape(node.args[0], fn, module, depth + 1)
            if name == "contained" and len(node.args) == 2:
                base = self.path_shape(node.args[0], fn, module, depth + 1)
                return base + self.segments(node.args[1], fn, module) if base else None
            target = self.source.callee(node.func, fn, module)
            if target is not None:
                shapes = {self.path_shape(statement.value, target, target.module, depth + 1)
                          for statement in self.analysis._returns(target)}
                shapes.discard(None)
                if len(shapes) == 1:
                    return shapes.pop()
        return None

    def segments(self, node: ast.AST, fn: Function | None, module: Module) -> tuple:
        """Path segments a joined expression adds: literal text split on '/', run-time values as holes."""
        if isinstance(node, ast.Name) and fn is not None:
            elements = self.analysis.loop_elements(node, node.id, fn)
            if isinstance(elements, list) and all(isinstance(item, ast.Constant) for item in elements):
                return ((Choice(tuple(str(item.value) for item in elements), self._loop_label(node, fn)),),)
        scope = self.analysis.scope_for(fn, module)
        variant = self.analysis.scalar(node, scope)[0]
        out, current = [], []
        for part in variant:
            if isinstance(part, str):
                pieces = part.split("/")
                current.append(pieces[0])
                for piece in pieces[1:]:
                    out.append(tuple(current))
                    current = [piece]
            else:
                current.append(part)
        out.append(tuple(current))
        return tuple(merge(segment) for segment in out if merge(segment))

    def _loop_label(self, node: ast.Name, fn: Function) -> str:
        child, current = node, fn.module.parent.get(node)
        while current is not None and current is not fn.node:
            for target, iterable in ([(current.target, current.iter)] if isinstance(current, ast.For) else
                                     [(item.target, item.iter) for item in getattr(current, "generators", [])]):
                if isinstance(target, ast.Name) and target.id == node.id:
                    return iterable.id if isinstance(iterable, ast.Name) else node.id
            child, current = current, fn.module.parent.get(current)
        return node.id

    def _administration(self) -> tuple[list[Row], set, set]:
        """Class 4 rows, the ids of Git-administration nodes, and the ids of path nodes among them (for class 5)."""
        found: dict = defaultdict(lambda: {"displays": set(), "paths": set(), "uses": defaultdict(set)})
        local_nodes: set = set()  # every Git-administration expression, Stewart's storage excluded
        path_nodes: set = set()  # those that are paths (not a compared name or file content)
        for module in self.source.modules.values():
            for node in ast.walk(module.tree):
                if node in module.docstrings:
                    continue
                fn = module.owner.get(node)
                kind = "path"
                if isinstance(node, ast.Constant) and node.value == ".git" \
                        and isinstance(module.parent.get(node), ast.Compare):
                    shape, display, kind = ("name", ".git"), "a path component named `.git`", "name"
                    uses = {"compared case-insensitively" if self._case_folded(module.parent[node]) else "compared"}
                elif (isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))
                      and node.value[:8] in ("gitdir: ", b"gitdir: ")) or \
                        (isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[0], ast.Constant)
                         and str(node.values[0].value).startswith("gitdir: ")):
                    if isinstance(module.parent.get(node), ast.JoinedStr):
                        continue
                    shape, display, kind = ("content", "gitdir"), "a `.git` file holding one `gitdir: <path>` line", \
                        "content"
                    uses = self._path_uses(node, fn, module)
                elif isinstance(node, (ast.BinOp, ast.Call, ast.Name, ast.Subscript)):
                    if not self._maximal(node, module):
                        continue
                    shape = self.path_shape(node, fn, module)
                    if shape is None:
                        continue
                    if len(shape) > 1 and isinstance(node, (ast.Name, ast.Subscript)):
                        continue  # a local holding a longer path: its uses are followed from its assignment
                    display = shape[0] + "".join("/" + show(segment, quote=False) for segment in shape[1:])
                    uses = self._path_uses(node, fn, module)
                    if len(shape) == 1:
                        # A bare administration directory counts where it is handled; the common directory
                        # itself only where an access scope lists it.
                        uses = {use for use in uses if use in BARE_ADMIN_VERBS} if shape[0] == "<git-admin>" else \
                            {use for use in uses if use.startswith("listed under")}
                        if not uses:
                            continue
                else:
                    continue
                key = tuple(norm(segment) if isinstance(segment, tuple) else segment for segment in shape)
                storage = key[0] == "<common>" and len(key) > 1 and key[1] == "stewart"
                if storage:
                    # Stewart's own records: one row per directory below <common>/stewart, verbs only.
                    uses = {use for use in uses if use in STORAGE_VERBS or use.startswith(("created", "listed under"))}
                    key = key[:3]
                    display = "<common>/stewart" + (f"/{key[2]}/…" if len(key) > 2 else "")
                else:
                    local_nodes.add(id(node))
                    if kind == "path":
                        path_nodes.add(id(node))
                entry = found[key]
                entry["displays"].add(display)
                entry["paths"].add(shape)
                entry["storage"] = storage
                for use in uses or {"named"}:
                    entry["uses"][use].add(module.place(fn))
        rows = []
        for key, entry in found.items():
            parts = [slug(key[0].strip("<>"))]
            for segment in key[1:]:
                # A segment that is wholly a run-time value is "entry", a glob "any"; names of values never count.
                text = " entry " if segment == "<>" else segment.replace("<>", " ").replace("*", " any ")
                text = re.sub(r"\{([^}]*)\}", lambda match: " " + match.group(1).lstrip("_") + " ", text)
                value = slug(("dot " + text[1:]) if text.startswith(".") else text)
                if value:
                    parts.append(value)
            display = sorted(entry["displays"])[0]
            shown = display if display.startswith("a ") else code(display)
            if entry["storage"] and len(entry["paths"]) > 1:
                shown += f" ({len(entry['paths'])} paths)"
            where = sorted({item for places in entry["uses"].values() for item in places}, key=location_order)
            group = "Stewart's storage in the common directory" if entry["storage"] else "Git's administration"
            rows.append(Row("adm." + ".".join(parts), "administration", group,
                            f"{shown}: {self._annotated(entry['uses'])}.", tuple(where), ""))
        return sorted(rows, key=lambda row: (row.group, row.id)), local_nodes, path_nodes

    @staticmethod
    def _case_folded(compare: ast.Compare) -> bool:
        """Whether a comparison folds case first (an operand is x.lower() or x.casefold())."""
        return any(isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
                   and item.func.attr in ("lower", "casefold") for item in [compare.left, *compare.comparators])

    def _maximal(self, node: ast.AST, module: Module) -> bool:
        """Whether a path expression is not merely part of a longer one (joined further, wrapped or contained)."""
        parent = module.parent.get(node)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div) and parent.left is node:
            return False
        if isinstance(parent, ast.Call) and called_name(parent.func) in TRANSPARENT and len(parent.args) == 1:
            return False
        if isinstance(parent, ast.Call) and called_name(parent.func) == "contained" and parent.args \
                and parent.args[0] is node:
            return False
        return not (isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load))

    def _held(self, node: ast.AST, fn: Function | None, module: Module, depth: int) -> set[str]:
        """What happens to a container holding a path: listed under a record key, named in a refusal, recorded."""
        above = node
        while True:
            parent = module.parent.get(above)
            if isinstance(parent, (ast.List, ast.Tuple, ast.Set, ast.Starred)):
                above = parent
            elif isinstance(parent, ast.Call) and called_name(parent.func) in ("list", "tuple", "sorted", "set",
                                                                               "frozenset", "fromkeys") \
                    and above in parent.args:
                above = parent
            else:
                break
        if isinstance(parent, ast.Dict) and above in parent.values:
            key = parent.keys[parent.values.index(above)]
            return {f"listed under `{key.value}`"} if isinstance(key, ast.Constant) else {"recorded"}
        if isinstance(parent, ast.keyword) and parent.arg == "retained":
            return {"named in a refusal"}
        if isinstance(parent, ast.Call) and is_stewart_error(parent.func):
            return {"named in a refusal"}
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name) \
                and fn is not None and depth < 6:
            uses: set = set()
            for later in fn.nodes:
                if isinstance(later, ast.Name) and later.id == parent.targets[0].id \
                        and isinstance(later.ctx, ast.Load) and later.lineno >= parent.lineno:
                    uses |= self._held(later, fn, module, depth + 1)
            return uses or {"recorded"}
        return {"recorded"}

    def _path_uses(self, node: ast.AST, fn: Function | None, module: Module, depth: int = 0) -> set[str]:
        """What the code does with a path where it is written, following a local variable to its uses."""
        child, current = node, module.parent.get(node)
        while current is not None and depth < 6:
            if isinstance(current, ast.Call):
                name = called_name(current.func)
                if child is current.func:
                    return {"used"}
                if is_stewart_error(current.func):
                    return {"named in a refusal"}
                if name in TRANSPARENT:
                    child, current = current, module.parent.get(current)
                    continue
                if name in PATH_VERBS:
                    return {PATH_VERBS[name]}
                if name in ("list", "tuple", "sorted", "set", "frozenset", "fromkeys"):
                    return self._held(child, fn, module, depth)
                target = self.source.callee(current.func, fn, module)
                return {f"passed to `{target.qualname}`"} if target is not None else {"recorded"}
            if isinstance(current, ast.keyword):
                if current.arg == "retained":
                    return {"named in a refusal"}
            elif isinstance(current, ast.Dict):
                return {"recorded"}  # a record's field; a list of paths under a key is "listed under" it
            elif isinstance(current, (ast.List, ast.Tuple, ast.Set, ast.Starred)):
                return self._held(child, fn, module, depth)
            elif isinstance(current, ast.Attribute) and current.value is child:
                call = module.parent.get(current)
                if isinstance(call, ast.Call) and call.func is current and current.attr in PATH_VERBS:
                    verb = PATH_VERBS[current.attr]
                    mode = next((keyword.value for keyword in call.keywords if keyword.arg == "mode"), None)
                    if mode is not None and isinstance(mode, ast.Constant) and isinstance(mode.value, int):
                        verb += f" (mode {mode.value:#o})".replace("0o", "0")
                    return {verb}
                if current.attr in ("encode", "decode", "strip", "lower"):
                    nxt = call if isinstance(call, ast.Call) and call.func is current else current
                    child, current = nxt, module.parent.get(nxt)
                    continue
                if current.attr not in ("parent", "name"):
                    return {"used"}
            elif isinstance(current, ast.Compare):
                return {"compared"}
            elif isinstance(current, ast.Return):
                return {"returned"}
            elif isinstance(current, (ast.FormattedValue, ast.JoinedStr)):
                return {"named in a message"}
            elif isinstance(current, ast.Assign) and len(current.targets) == 1 \
                    and isinstance(current.targets[0], ast.Name) and fn is not None:
                uses: set = set()
                for later in fn.nodes:
                    if isinstance(later, ast.Name) and later.id == current.targets[0].id \
                            and isinstance(later.ctx, ast.Load) and later.lineno >= current.lineno:
                        if not self._maximal(later, module):
                            continue  # extended or contained: recorded as its own, longer path
                        uses |= self._path_uses(later, fn, module, depth + 1)
                return uses or {"assigned"}
            elif isinstance(current, ast.stmt):
                return {"used"}
            child, current = current, module.parent.get(current)
        return {"used"}

    # class 5 -----------------------------------------------------------------------------------------

    def _sources(self) -> set:
        """Functions whose calls yield Git-derived values, to SOURCE_DEPTH levels.

        Level 0 is the Git helpers: the primitive, the wrappers and every function in the Git module. Level n
        adds each function whose return value derives from a call at a lower level or from a Git-administration
        path in its own body. Deeper levels are orchestration (records stamped with Stewart's own provenance,
        command dispatch) whose results are not observations of the material's repository. A compared `.git`
        name or `gitdir:` content taints conditions in its own function but never a return value, and the
        common directory's path and Stewart's storage paths never carry taint (``_location_value``).
        """
        sources = {PRIMITIVE, *self.analysis.wrappers} | {key for key in self.source.functions if key[0] == GIT_MODULE}
        for _ in range(SOURCE_DEPTH):
            cache: dict = {}
            added = set()
            for fn in self.source.functions.values():
                if fn.key in sources:
                    continue
                names = self._taint_chain(fn, sources, cache, self.path_nodes)
                if any(self._tainted(statement.value, names, sources, fn, self.path_nodes)
                       for statement in self.analysis._returns(fn)):
                    added.add(fn.key)
            if not added:
                break
            sources |= added
        return sources

    def _taint_chain(self, fn: Function, sources: set, cache: dict, nodes: set) -> set:
        if fn.key not in cache:
            inherited = self._taint_chain(fn.parent, sources, cache, nodes) if fn.parent else set()
            cache[fn.key] = self._taint(fn, sources, inherited, nodes)
        return cache[fn.key]

    def _tainted(self, node: ast.AST, names: set, sources: set, fn: Function, nodes: set) -> bool:
        """Whether an expression holds a Git-derived value; location values are skipped whole."""
        pending = [node]
        while pending:
            item = pending.pop()
            if id(item) in nodes:
                return True
            if isinstance(item, ast.expr) and self._location_value(item, fn):
                continue
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id in names:
                return True
            if isinstance(item, ast.Call):
                target = self.source.callee(item.func, fn, fn.module)
                if target is not None and target.key in sources:
                    return True
            pending.extend(ast.iter_child_nodes(item))
        return False

    def _location_value(self, node: ast.AST, fn: Function) -> bool:
        """A location, not an observation: the common directory's path, a path into Stewart's storage, or a call
        given Stewart's own installation (``__file__``), such as the package identity stamped on records."""
        if isinstance(node, ast.Call) and any(isinstance(item, ast.Name) and item.id == "__file__"
                                              for argument in [*node.args, *(k.value for k in node.keywords)]
                                              for item in ast.walk(argument)):
            return True
        if isinstance(node, (ast.Subscript, ast.Attribute)):
            key = node.slice.value if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                else getattr(node, "attr", None)
            if key in COMMON_KEYS:
                return True
        if not isinstance(node, (ast.BinOp, ast.Call)):
            return False
        if id(node) not in self._location_cache:
            shape = self.path_shape(node, fn, fn.module)
            self._location_cache[id(node)] = shape is not None and len(shape) > 1 and shape[0] == "<common>" \
                and shape[1] == ("stewart",)
        return self._location_cache[id(node)]

    def _taint(self, fn: Function, sources: set, inherited: set, nodes: set) -> set:
        """Names in fn that hold values derived from Git or its administration.

        Derivation follows assignment (including to a subscript or attribute of a name), augmented assignment,
        loop and comprehension targets, with targets, except names of a try over derived work, and container
        mutation: a derived value appended, inserted or merged into a container derives the container.
        """
        names = set(inherited)
        while True:
            before = len(names)
            for node in fn.nodes:
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None \
                        and not self._location_value(node.value, fn) \
                        and self._tainted(node.value, names, sources, fn, nodes):
                    for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                        names.update(_target_names(target))
                elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)) \
                        and self._tainted(node.iter, names, sources, fn, nodes):
                    names.update(_target_names(node.target))
                elif isinstance(node, ast.withitem) and node.optional_vars is not None \
                        and self._tainted(node.context_expr, names, sources, fn, nodes):
                    names.update(_target_names(node.optional_vars))
                elif isinstance(node, ast.Try) and any(self._tainted(item, names, sources, fn, nodes)
                                                       for item in node.body):
                    names.update(handler.name for handler in node.handlers if handler.name)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr in MUTATORS and isinstance(node.func.value, ast.Name) \
                        and any(self._tainted(argument, names, sources, fn, nodes)
                                for argument in [*node.args, *(keyword.value for keyword in node.keywords)]):
                    names.add(node.func.value.id)
            if len(names) == before:
                return names

    def _dependent(self, raise_node: ast.Raise, fn: Function, names: set, sources: set) -> bool:
        """Whether a raise is guarded by a Git-derived condition or handles a failure of Git-derived work."""
        module = fn.module
        child, current = raise_node, module.parent.get(raise_node)
        while current is not None and current is not fn.node:
            if isinstance(current, (ast.If, ast.While)) and child is not current.test \
                    and self._tainted(current.test, names, sources, fn, self.local_nodes):
                return True
            if isinstance(current, (ast.For, ast.AsyncFor)) and child is not current.iter \
                    and self._tainted(current.iter, names, sources, fn, self.local_nodes):
                return True
            if isinstance(current, ast.ExceptHandler):
                trying = module.parent.get(current)
                if any(self._tainted(item, names, sources, fn, self.local_nodes) for item in trying.body):
                    return True
            child, current = current, module.parent.get(current)
        return False

    def _factories(self) -> dict:
        """Functions that return a StewartError: key -> (the StewartError call, the factory)."""
        found = {}
        for fn in self.source.functions.values():
            for statement in self.analysis._returns(fn):
                if isinstance(statement.value, ast.Call) and is_stewart_error(statement.value.func):
                    found[fn.key] = (statement.value, fn)
                    break
        return found

    def message(self, node: ast.AST | None, substitutions: dict, limit: int = 110) -> str:
        """A refusal message's literal text with run-time values shown as {expression}."""
        def render(item, conversion=-1, substitute=True) -> str:
            if substitute and isinstance(item, ast.Name) and item.id in substitutions:
                # The caller's argument, rendered in the caller's terms (its names are not the factory's).
                return render(substitutions[item.id], conversion, substitute=False)
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                return repr(item.value) if conversion == ord("r") else item.value
            if isinstance(item, ast.JoinedStr):
                return "".join(value.value if isinstance(value, ast.Constant) else render(value.value, value.conversion)
                               for value in item.values)
            if isinstance(item, ast.BinOp) and isinstance(item.op, ast.Add):
                return render(item.left) + render(item.right)
            return "{" + short(item, 28) + "}"
        text = " ".join(render(node).split()) if node is not None else ""
        return text if len(text) <= limit else text[:limit - 1] + "…"

    def _refusals(self) -> tuple[list[Row], list[str], list[str]]:
        analysis = self.analysis
        sources = self._sources()
        factories = self._factories()
        grouped: dict = defaultdict(list)
        unresolved: list = []
        reraised: list = []
        taints: dict = {}

        def taint(fn: Function) -> set:
            return self._taint_chain(fn, sources, taints, self.local_nodes)

        def touches(fn: Function) -> bool:
            return any(self._tainted(node, set(), sources, fn, self.local_nodes) for node in fn.nodes
                       if isinstance(node, (ast.Call, ast.BinOp, ast.Constant, ast.Subscript, ast.Name, ast.JoinedStr)))

        for fn in self.source.functions.values():
            if not touches(fn) and not (fn.parent and touches(fn.parent)):
                continue
            names = taint(fn)
            for node in fn.nodes:
                if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                    continue
                call = node.exc
                if is_stewart_error(call.func):
                    reason_node = next((keyword.value for keyword in call.keywords if keyword.arg == "reason"), None)
                    text = self.message(call.args[0] if call.args else None, {})
                else:
                    target = self.source.callee(call.func, fn, fn.module)
                    if target is None or target.key not in factories:
                        continue
                    made, factory = factories[target.key]
                    substitutions = dict(zip(factory.positional, call.args))
                    substitutions.update({keyword.arg: keyword.value for keyword in call.keywords if keyword.arg})
                    reason_node = next((keyword.value for keyword in made.keywords if keyword.arg == "reason"), None)
                    if isinstance(reason_node, ast.Name) and reason_node.id in substitutions:
                        reason_node = substitutions[reason_node.id]
                    text = self.message(made.args[0] if made.args else None, substitutions)
                if not self._dependent(node, fn, names, sources):
                    continue
                if isinstance(reason_node, ast.Constant) and isinstance(reason_node.value, str):
                    grouped[(reason_node.value, fn.key)].append((fn.place(), text))
                elif isinstance(reason_node, ast.Attribute) and reason_node.attr == "reason":
                    reraised.append(f"{fn.location(node.lineno)}: re-raises {short(reason_node)}, the reason of a "
                                    "refusal raised elsewhere")
                elif isinstance(reason_node, ast.Name) and reason_node.id in fn.params:
                    resolved = False
                    for module, caller, site in analysis.calls_to.get(fn.key, []):
                        value = next((keyword.value for keyword in site.keywords if keyword.arg == reason_node.id), None)
                        if value is None and reason_node.id in fn.positional:
                            index = fn.positional.index(reason_node.id)
                            value = site.args[index] if index < len(site.args) else None
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            key = caller.key if caller else (module.name, "<module>")
                            grouped[(value.value, key)].append(
                                (module.place(caller) + f" (raised in {fn.place()})", text))
                            resolved = True
                    if not resolved:
                        unresolved.append(f"{fn.location(node.lineno)}: reason is parameter "
                                          f"{reason_node.id!r} and no caller passes a literal")
                else:
                    unresolved.append(f"{fn.location(node.lineno)}: reason "
                                      f"{short(reason_node) if reason_node is not None else 'missing'}")
        rows = []
        for (reason, key), members in grouped.items():
            members = sorted(set(members), key=lambda item: (location_order(item[0]), item[1]))
            opinion = "<br>".join(f"“{cell(text)}”" for _, text in members)
            where = tuple(dict.fromkeys(where for where, _ in members))
            rows.append(Row(f"refuse.{reason}.{key[0]}.{key[1]}", "refusal", "Refusals", opinion, where,
                            f"`{reason}`"))
        return sorted(rows, key=lambda row: row.id), unresolved, reraised


# --- rendering -----------------------------------------------------------------------------------------

TITLES = {
    "configuration": "Configuration common to every Git call",
    "invocation": "Git invocations",
    "ref": "Refs Stewart names, creates or deletes",
    "administration": "Git administration paths",
    "refusal": "Refusals that depend on what Git reports",
}
#: One plain sentence per class for Stewart's users: what the class lists and what it leaves out. The rules
#: that select each class are in this script's docstring and --help.
SUMMARIES = {
    "configuration": (
        "The settings, environment and working directory Stewart gives every Git command it runs. Your own Git "
        "configuration and the rest of your environment still apply and are not listed."),
    "invocation": (
        "Each distinct Git command Stewart's own code runs, where it runs it, and whether a failure stops the "
        "operation. Git run by the auditor or by an experiment, and Git commands Stewart only prints as advice, "
        "are not listed."),
    "ref": (
        "The ref names Stewart's code writes, and what it does with refs in each namespace. Refs it only learns "
        "from Git's output are not listed by name."),
    "administration": (
        "The files and directories in Git's administration that Stewart reads, writes or checks, and where its "
        "own records live inside your repository's Git directory. Your working files and Stewart's checkout "
        "home are not listed."),
    "refusal": (
        "The refusals Stewart raises because of something Git reported or something in Git's administration, "
        "with their reason identifiers. Refusals that depend only on your arguments, on Stewart's own records "
        "or on values passed between Stewart's functions, and problems that `status` reports without refusing, "
        "are not listed."),
}


def table(rows: list[Row]) -> list[str]:
    lines = ["| ID | Opinion | Class | Where | Reason |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append(f"| `{row.id}` | {row.opinion} | {row.cls} | {', '.join(row.where)} | {row.reason} |")
    return lines


def render(tables: Tables) -> str:
    out = [
        "<!-- Generated by scripts/git_opinions.py from the Python source under src/stewart; edit the script, "
        "not this region, and regenerate with --write. -->",
        "",
        "Rows are selected by parsing Stewart's source: each is something its code does with Git. Each row's "
        "description is composed from fixed glosses of Git's commands and options, and of what the code does "
        "with a path. A row's ID is formed from that content and from the names of the code that holds it, "
        "never from a line number; it stays the same while the code holding the opinion is unchanged. "
        "**Where** names the `module:function` of Stewart's source that holds the opinion; **Reason** is the "
        "refusal identifier that code raises, when there is one. A refusal raised while preparing an audit is "
        "reported as `prepare_failed`, with this reason in the preparation's failure record.",
    ]
    classes = [("configuration", tables.configuration), ("invocation", tables.invocations), ("ref", tables.refs),
               ("administration", tables.administration), ("refusal", tables.refusals)]
    for number, (name, rows) in enumerate(classes, 1):
        out += ["", f"### {number}. {TITLES[name]} ({len(rows)} rows)", "", SUMMARIES[name]]
        groups: dict = {}
        for row in rows:
            groups.setdefault(row.group, []).append(row)
        if len(groups) <= 1:
            out += ["", *table(rows)]
        else:
            for group in sorted(groups):
                heading = code(group) if name == "invocation" else group
                out += ["", f"#### {heading}", "", *table(groups[group])]
        if name == "ref":
            out += ["", "Invocation rows whose command writes refs: "
                    + (", ".join(f"`{row}`" for row in tables.ref_writers) or "none") + "."]
    text = "\n".join(out) + "\n"
    if BEGIN.decode() in text or END.decode() in text:
        raise Refusal("the generated text contains a region marker")
    return text


# --- the document region -------------------------------------------------------------------------------


def read_document(document: Path, *, for_write: bool) -> tuple[bytes, os.stat_result, Path]:
    """The document's exact bytes, its identity and its absolute path; refuses anything unsafe to rewrite.

    Every directory on the way must be a real directory, not a link, and the document a regular file with
    no other hard link (replacing it would break them). It is opened without following a link and without
    blocking, and must still be the file inspected. For --write it must also be writable by its owner.
    """
    path = Path(os.path.abspath(document))
    for ancestor in reversed(path.parents):
        try:
            observed = os.lstat(ancestor)
        except OSError as exc:
            raise Refusal(f"cannot inspect {ancestor}: {exc}") from exc
        if stat.S_ISLNK(observed.st_mode):
            raise Refusal(f"{path} is reached through the link {ancestor}; name it by a path without links "
                          "(nothing was written)")
    try:
        observed = os.lstat(path)
    except OSError as exc:
        raise Refusal(f"cannot inspect {path}: {exc}") from exc
    if stat.S_ISLNK(observed.st_mode):
        raise Refusal(f"{path} is a link; name the document itself (nothing was written)")
    if not stat.S_ISREG(observed.st_mode):
        raise Refusal(f"{path} is not a regular file (nothing was written)")
    if observed.st_nlink != 1:
        raise Refusal(f"{path} has {observed.st_nlink} hard links; replacing it would break them "
                      "(nothing was written)")
    if for_write and not observed.st_mode & stat.S_IWUSR:
        raise Refusal(f"{path} is read-only; make it writable first if it should change (nothing was written)")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except OSError as exc:
        raise Refusal(f"cannot open {path}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino):
            raise Refusal(f"{path} changed while it was opened (nothing was written)")
        chunks = []
        while chunk := os.read(descriptor, 1 << 16):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    return b"".join(chunks), opened, path


def region(data: bytes, document: Path) -> tuple[int, int]:
    """The byte span strictly between the markers; refuses missing, repeated or reversed markers."""
    begins, ends = data.count(BEGIN), data.count(END)
    if begins != 1 or ends != 1:
        raise Refusal(f"{document} must hold {BEGIN.decode()} and {END.decode()} exactly once each (found "
                      f"{begins} and {ends}); nothing was written")
    start, stop = data.index(BEGIN) + len(BEGIN), data.index(END)
    if stop < start:
        raise Refusal(f"{document} has {END.decode()} before {BEGIN.decode()}; nothing was written")
    return start, stop


def write_region(document: Path, generated: bytes) -> bool:
    """Replace the region's bytes, every other byte kept exactly; returns whether anything changed.

    The new document is staged beside the old one and replaces it only while the old one is unchanged. A
    staging file that could not be put in place is kept, and the refusal names it.
    """
    data, observed, path = read_document(document, for_write=True)
    start, stop = region(data, path)
    updated = data[:start] + b"\n" + generated + data[stop:]
    if updated == data:
        return False
    descriptor, staging = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".git-opinions-staged", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(staging, stat.S_IMODE(observed.st_mode))
        current, now, _ = read_document(path, for_write=True)
        if current != data or (now.st_dev, now.st_ino) != (observed.st_dev, observed.st_ino):
            raise Refusal(f"{path} changed while the region was generated")
        os.replace(staging, path)
    except (Refusal, OSError) as exc:
        raise Refusal(f"{exc}; {path} was not replaced, and the staged bytes are kept at {staging}") from exc
    return True


def check_region(document: Path, generated: bytes) -> bool:
    data, _, path = read_document(document, for_write=False)
    start, stop = region(data, path)
    return data[start:stop] == b"\n" + generated


# --- coverage -------------------------------------------------------------------------------------------

RAW_PATTERNS = [
    r"\bgit\(", r"\bgit_text\(", r"\btree_entries\(", r"\bgitlinks\(", r"\bcreate_refs\(", r"\bresolve_commit\(",
    r"\b_invocation\(", r"\b_git_common\(", r"\b_git_head\(", r"[\"']git[\"']",
    r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\b", r"\bos\.(?:system|popen|exec\w*|spawn\w*|posix_spawn\w*)\(",
    # A Git command quoted in text: advice Stewart prints for its user, which no invocation row covers.
    r"`git [a-z][a-z-]*",
]


def prose_spans(module: Module) -> dict:
    """Per line, the character spans of comments and string text, with each token's type and text."""
    spans: dict = defaultdict(list)
    kinds = {tokenize.COMMENT, tokenize.STRING} | {getattr(tokenize, name) for name in
                                                   ("FSTRING_MIDDLE", "TSTRING_MIDDLE") if hasattr(tokenize, name)}
    for token in tokenize.generate_tokens(io.StringIO(module.text).readline):
        if token.type not in kinds:
            continue
        (start_row, start_col), (end_row, end_col) = token.start, token.end
        for row in range(start_row, end_row + 1):
            first = start_col if row == start_row else 0
            last = end_col if row == end_row else 10 ** 6
            spans[row].append((first, last, token.type, token.string))
    return spans


def coverage(tables: Tables) -> tuple[list[str], int]:
    """Every raw-scan hit with what accounts for it, the checks that fail, and how many failed."""
    analysis, source = tables.analysis, tables.source
    names = {key[1].rsplit(".", 1)[-1] for key in [*analysis.wrappers, *analysis.option_builders]}
    patterns = RAW_PATTERNS + [rf"\b{re.escape(name)}\(" for name in sorted(names)
                               if not any(name in pattern for pattern in RAW_PATTERNS)]
    git_running = {site.fn.key for site in analysis.sites if site.fn is not None}
    consumed = {id(node) for site in analysis.sites for node in ast.walk(site.node) if isinstance(node, ast.Call)}
    reviewed_used: set = set()
    lines, dispositions, unmatched = [], defaultdict(int), []
    for module in source.modules.values():
        spans = prose_spans(module)
        by_end: dict = {}
        constants: dict = {}
        defs = {(fn.node.lineno, fn.node.name) for fn in module.functions}
        documented = {line for node in module.docstrings for line in range(node.lineno, node.end_lineno + 1)}
        for node in ast.walk(module.tree):
            if isinstance(node, (ast.Name, ast.Attribute)) and hasattr(node, "end_lineno"):
                by_end[(node.end_lineno, node.end_col_offset)] = node
            if isinstance(node, ast.Constant) and node.value == "git":
                constants[(node.lineno, node.col_offset)] = node
        for number, line in enumerate(module.lines, 1):
            for pattern in patterns:
                for match in re.finditer(pattern, line):
                    text = match.group().rstrip("(")
                    column = len(line[:match.start()].encode("utf-8"))
                    end = len(line[:match.start() + len(text)].encode("utf-8"))
                    inside = [span for span in spans.get(number, []) if span[0] <= match.start() < span[1]]
                    literal_git = inside and inside[0][2] == tokenize.STRING and inside[0][3] in ('"git"', "'git'")
                    if inside and not literal_git:
                        fn = function_at(module, number)
                        quiet = inside[0][2] == tokenize.COMMENT or number in documented
                        if text.startswith("`git"):
                            disposition = ("advice: a Git command in a comment or docstring, not an invocation" if quiet
                                           else "advice: a Git command Stewart prints for its user, not an invocation")
                        else:
                            disposition = "prose: comment or string text"
                    else:
                        node = constants.get((number, column)) if literal_git else by_end.get((number, end))
                        parent = module.parent.get(node) if node is not None else None
                        fn = module.owner.get(node) if node is not None else function_at(module, number)
                        disposition = classify(tables, module, fn, node, parent, text, number, defs, git_running,
                                               consumed, reviewed_used)
                    kind = disposition.split(":", 1)[0]
                    dispositions[kind] += 1
                    entry = f"{module.location(fn, number)} [{text}] {disposition}"
                    lines.append(entry)
                    if kind == "unmatched":
                        unmatched.append(entry)
    # Helper references that are not calls (aliasing would hide invocations from the raw scan).
    helper_keys = {PRIMITIVE, *analysis.wrappers, *analysis.option_builders, *git_running}
    for module in source.modules.values():
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
                continue
            parent = module.parent.get(node)
            if isinstance(parent, ast.Call) and parent.func is node:
                continue
            fn = module.owner.get(node)
            found = source.lookup(node.id, fn, module)
            if found and found[0] == "function" and found[1].key in helper_keys:
                entry = f"{module.location(fn, node.lineno)} [{node.id}] unmatched: Git helper referenced without a call"
                lines.append(entry)
                unmatched.append(entry)
                dispositions["unmatched"] += 1
    checks = [
        ("raw-scan hits nothing accounts for", unmatched),
        ("unresolved invocations (no row is made)",
         [f"{site.module.location(site.fn, site.node.lineno)}: "
          + " ".join(show(element) for element in site.expansion.argv) + f" ({why})" for site, why in tables.unresolved]),
        ("wrappers no call reaches", [f"{key[0]}:{key[1]}" for key in sorted(analysis.wrappers)
                                      if not analysis.calls_to.get(key)]),
        ("refusals whose reason could not be resolved", tables.unresolved_reasons),
        ("commands or options without a gloss for their command", sorted(tables.gloss_gaps)),
        (f"values cut at MAX_VARIANTS ({MAX_VARIANTS}) alternatives",
         [f"{TRUNCATIONS['count']} values"] if TRUNCATIONS["count"] else []),
    ]
    notes = [
        ("re-raised reasons (not new refusals)", tables.reraised),
        ("reviewed entries no hit matches", [f"{key}: {why}" for key, why in sorted(REVIEWED.items())
                                             if key not in reviewed_used]),
    ]
    report = [f"[git-opinions] raw scan: {sum(dispositions.values())} hits in {len(source.modules)} modules; "
              + ", ".join(f"{count} {kind}" for kind, count in sorted(dispositions.items())),
              *sorted(lines, key=location_order), ""]
    failed = 0
    for title, entries in checks:
        failed += len(entries)
        report.append(f"[git-opinions] {title} ({len(entries)}):")
        report += [f"  {entry}" for entry in entries] or ["  none"]
    for title, entries in notes:
        report.append(f"[git-opinions] {title} ({len(entries)}, informational):")
        report += [f"  {entry}" for entry in entries] or ["  none"]
    report.append("[git-opinions] wrappers: " + ", ".join(f"{key[0]}:{key[1]}" for key in sorted(analysis.wrappers)))
    report.append("[git-opinions] launch wrappers: " + ", ".join(
        f"{key[0]}:{key[1]} ({reason or 'no reason'})" for key, reason in sorted(analysis.launch_wrappers.items())))
    report.append("[git-opinions] option builders: " + ", ".join(f"{key[0]}:{key[1]}"
                                                               for key in sorted(analysis.option_builders)))
    report.append(f"[git-opinions] invocation sites: {len(analysis.sites)} expansions at "
                  f"{len({id(site.node) for site in analysis.sites})} calls")
    report.append(f"[git-opinions] {'FAILED' if failed else 'passed'}: {failed} problems in the checks above")
    return report, failed


def function_at(module: Module, line: int) -> Function | None:
    """The innermost def whose body spans a line."""
    spanning = [fn for fn in module.functions if fn.node.lineno <= line <= fn.node.end_lineno]
    return max(spanning, key=lambda fn: fn.node.lineno, default=None)


def classify(tables, module, fn, node, parent, text, number, defs, git_running, consumed, reviewed_used) -> str:
    """What accounts for one raw-scan hit in code."""
    analysis, source = tables.analysis, tables.source
    function = fn.qualname if fn else "<module>"
    if node is None:
        name = text.split(".")[-1]
        if (number, name) in defs:
            return "definition: the helper's own def"
        return "unmatched: no expression found at this position"
    if isinstance(node, ast.Constant):
        if fn is not None and fn.key == PRIMITIVE:
            return "configuration: the program name (class 1)"
        return "unmatched: a literal 'git' outside the invocation builder"
    if text.startswith(("subprocess.", "os.")):
        if not (isinstance(parent, ast.Call) and parent.func is node):
            return "reference: named, not called"
        if any(keyword.arg is None and isinstance(keyword.value, ast.Call)
               and called_name(keyword.value.func) == PRIMITIVE[1] for keyword in parent.keywords):
            return "launch: the Git process, configured by class 1"
        key = (module.name, function, text)
        if key in REVIEWED:
            reviewed_used.add(key)
            return f"reviewed: {REVIEWED[key]}"
        return "unmatched: a process launch that does not go through _invocation"
    if not (isinstance(parent, ast.Call) and parent.func is node):
        return "unmatched: not a call"
    rows = tables.site_rows.get(id(parent))
    if rows:
        return "site: " + ", ".join(sorted(rows))
    if id(parent) in analysis.template_ids:
        count = len(analysis.calls_to.get(fn.key, []))
        return f"template: expanded at the {count} calls of {fn.key[0]}:{fn.key[1]}"
    if any(site.node is parent for site, _ in tables.unresolved):
        return "unresolved: listed below; no row is made"
    target = source.callee(parent.func, fn, module)
    if target is None:
        return "unmatched: the call names no package function"
    if target.key in analysis.option_builders:
        if id(parent) in consumed:
            return f"option builder: {target.qualname} inside a site's arguments"
        assigned = module.parent.get(parent)
        if isinstance(assigned, ast.Assign) and isinstance(assigned.targets[0], ast.Name) and fn is not None:
            name = assigned.targets[0].id
            users = sorted({site.node.lineno for site in analysis.sites if site.fn is not None and
                            (site.fn is fn or site.fn.parent is fn) and any(
                                isinstance(item, ast.Name) and item.id == name for item in ast.walk(site.node))}
                           | {template.lineno for key, templates in analysis.wrappers.items()
                              if source.functions[key].parent is fn for template in templates
                              if any(isinstance(item, ast.Name) and item.id == name for item in ast.walk(template))})
            calls = sorted({site.lineno for _, owner, site in
                            (item for key in analysis.wrappers for item in analysis.calls_to.get(key, []))
                            if owner is fn and any(isinstance(item, ast.Name) and item.id == name
                                                   for item in ast.walk(site))})
            if users or calls:
                return f"option builder: {target.qualname} result used by the calls at lines " \
                       + ", ".join(map(str, sorted(set(users) | set(calls))))
        if isinstance(assigned, ast.Return) and fn is not None and fn.key in analysis.option_builders:
            return f"option builder: returned by the option builder {fn.qualname}"
        return f"unmatched: {target.qualname} called but its options reach no site"
    if target.key in git_running:
        rows = sorted(tables.fn_rows.get(target.key, ()))
        return f"helper call: {target.qualname} runs " + ", ".join(rows)
    if target.key in analysis.wrappers:
        return "unmatched: a wrapper call that produced no command"
    return f"unrelated: calls {target.module.name}:{target.qualname}, which runs no Git"


# --- command line ---------------------------------------------------------------------------------------

EXIT_OK, EXIT_FAILED, EXIT_REFUSED, EXIT_INTERNAL = 0, 1, 2, 3


def main(argv: list[str] | None = None) -> int:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=(
        "Run it with an explicit interpreter and isolated startup, for example\n"
        "  python3.14 -I -B scripts/git_opinions.py --check\n\n"
        "Exit status: 0 on success; 1 when --check finds the region stale or --coverage finds a\n"
        "problem; 2 when the run is refused (the source cannot be read, two rows would share an ID,\n"
        "or the document is unsafe to read or rewrite: a link, under a linked directory, not a\n"
        "regular file, hard-linked, read-only for --write, or with missing, repeated or reversed\n"
        "markers); 3 on an internal error, with its traceback."))
    parser.add_argument("--source", type=Path, default=project / "src" / PACKAGE,
                        help="the package directory to read (default <project>/src/stewart)")
    parser.add_argument("--document", type=Path, default=project / "GIT-ENVIRONMENT-NEEDS.md",
                        help="the document holding the generated region (default <project>/GIT-ENVIRONMENT-NEEDS.md)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true",
                      help="replace only the bytes between the git-opinions markers in the document")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 when the document's region differs from what would be generated; writes nothing")
    mode.add_argument("--coverage", action="store_true",
                      help="list every raw-scan hit for Git invocations with what accounts for it; exit 1 when "
                           "any check fails")
    args = parser.parse_args(argv)
    try:
        source_root = args.source.resolve()
        if not source_root.is_dir():
            raise Refusal(f"no source directory at {source_root}")
        tables = Tables(Source(source_root))
        if args.coverage:
            report, failed = coverage(tables)
            print("\n".join(report))
            return EXIT_FAILED if failed else EXIT_OK
        generated = render(tables).encode("utf-8")
        if args.write:
            changed = write_region(args.document, generated)
            print(f"[git-opinions] {'wrote' if changed else 'unchanged'}: the region of {args.document}")
            return EXIT_OK
        if args.check:
            if check_region(args.document, generated):
                print(f"[git-opinions] current: the region of {args.document} matches the source")
                return EXIT_OK
            print(f"[git-opinions] stale: the region of {args.document} differs from what the source generates; "
                  "run scripts/git_opinions.py --write", file=sys.stderr)
            return EXIT_FAILED
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.flush()
            sys.stdout.buffer.write(generated)
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(generated.decode("utf-8"))
        return EXIT_OK
    except Refusal as exc:
        print(f"[git-opinions] refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception:
        import traceback
        traceback.print_exc()
        print("[git-opinions] internal error: a defect in this script, named by the traceback above; the document "
              "is replaced only by a completed --write", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
