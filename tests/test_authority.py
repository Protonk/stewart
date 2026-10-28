"""Standalone authority guards with measured populations and paired controls."""
from fnmatch import fnmatchcase
from pathlib import Path
import os
import pytest
import stewart

HOME = "src/stewart/"
LITERALS = ("```audit-assignment", "```audit-report", "stewart/sessions")
# coordination/ holds captured development records whose study scripts quote custody fences as data.
EXEMPT_PREFIXES = (HOME, "tests/", "coordination/")
EXCLUDED_TOP_LEVEL = {".scratch", ".git", "dist", "build"}


pytestmark = pytest.mark.smoke


def python_names(root):
    """Every entry named ``*.py`` under root, as rglob would list it, minus excluded top-level trees.

    Excluded top-level directories are pruned before descending, so retained
    run artifacts under ``.scratch`` cost nothing. Exclusion applies only at the
    top level; symlinked directories are not entered; non-regular entries named
    ``*.py`` are listed, as rglob lists them.
    """
    names = []
    for directory, dirnames, filenames in os.walk(root):
        relative = Path(directory).relative_to(root)
        if relative == Path("."):
            dirnames[:] = [name for name in dirnames if name not in EXCLUDED_TOP_LEVEL]
        names.extend(str(relative / name) for name in (*dirnames, *filenames) if fnmatchcase(name, "*.py"))
    return sorted(names)


def source_python(root):
    names = python_names(root)
    assert len([name for name in names if name.startswith(HOME)]) >= 29, "runtime source population vanished"
    return names


def walk_entering(monkeypatch, walk, root):
    """``walk(root)``'s result and the directories it opened through ``os.scandir``, relative to root.

    os.walk and the rglob filter it replaced both look ``os.scandir`` up at call time, so the
    recorder sees either walker descend. Relative paths keep a tmp_path that sits in the running
    checkout's ``.scratch`` from reading as an entered excluded tree.
    """
    entered, real_scandir = [], os.scandir

    def recording(path="."):
        entered.append(os.path.relpath(path, root))
        return real_scandir(path)

    with monkeypatch.context() as patch:
        patch.setattr(os, "scandir", recording)
        result = walk(root)
    return result, sorted(set(entered))


def excluded_entered(entered):
    return sorted({directory for directory in entered if directory.split(os.sep)[0] in EXCLUDED_TOP_LEVEL})


def custody_literal_violations(repo_root: Path, population: list[str]) -> list[str]:
    """Files outside the home that spell a custody literal, as ``path: literal`` strings."""
    violations = []
    for rel in population:
        if rel.startswith(EXEMPT_PREFIXES):
            continue
        try:
            text = (repo_root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        violations.extend(f"{rel}: {literal!r}" for literal in LITERALS if literal in text)
    return violations


def test_audit_custody_machinery_has_one_home(monkeypatch) -> None:
    """The ratchet's population comes from a walk that never enters the excluded top-level trees.

    The walk is recorded at this call site because an unpruned one costs time in proportion to
    the checkout's retained runs. check.py's default result and basetemp live in ``.scratch``, so
    an excluded tree is normally present to be entered; the planted-tree test below covers a
    checkout that has none.
    """
    repo_root = Path(os.environ["STEWART_TEST_PROJECT"])
    population, entered = walk_entering(monkeypatch, source_python, repo_root)
    assert custody_literal_violations(repo_root, population) == [], (
        "a second assignment parser or session layout appeared outside src/stewart; "
        "route callers to the package instead of adding a helper beside the workspace"
    )
    home = HOME.rstrip("/")
    assert home in entered, (
        f"the os.scandir recorder never saw {home} walked ({len(entered)} directories recorded); "
        "source_python must walk through os.scandir for this pruning guard to observe it")
    pruned = excluded_entered(entered)
    assert pruned == [], (
        f"source_python entered {len(pruned)} directories in excluded top-level trees, starting {pruned[:5]}; "
        "walk with python_names, which prunes them before descending")


def test_walk_prunes_excluded_top_level_trees_and_lists_what_rglob_listed(tmp_path: Path, monkeypatch) -> None:
    """Pruning is the measured property; the former rglob filter's name list is the invariant.

    The planted tree covers each semantic the old filter had: exclusion only at the top level,
    symlinked directories listed by name but never entered, and non-regular ``*.py`` entries listed.
    """
    root = tmp_path / "tree"
    for name in (".scratch/x.py", ".git/g.py", "dist/y.py", "build/w.py",
                 "a.py", "pkg/b.py", "pkg/build/z.py", "odd.py/inner.py"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("")
    (root / "linked").symlink_to("pkg", target_is_directory=True)
    (root / "alias.py").symlink_to("pkg", target_is_directory=True)
    (root / "dangling.py").symlink_to("missing")
    names, entered = walk_entering(monkeypatch, python_names, root)
    assert names == ["a.py", "alias.py", "dangling.py", "odd.py", "odd.py/inner.py", "pkg/b.py", "pkg/build/z.py"], (
        "python_names must keep rglob's population (top-level-only exclusion, symlinked directories listed "
        f"but not entered, non-regular *.py entries listed); got {names}")
    pruned = excluded_entered(entered)
    assert pruned == [], f"the walk entered excluded top-level trees {pruned}; prune them before descending"
    assert entered == [".", "odd.py", "pkg", "pkg/build"], (
        f"the walk must enter every real unexcluded directory and no symlinked one; it entered {entered}")
    old_filter = sorted(str(p.relative_to(root)) for p in root.rglob("*.py")
                        if p.relative_to(root).parts[0] not in {".scratch", ".git", "dist", "build"})
    assert names == old_filter, f"the walk's population differs from the rglob filter's: {sorted(set(names) ^ set(old_filter))}"


def test_ratchet_goes_red_on_a_planted_duplicate_and_ignores_unrelated_text(tmp_path: Path) -> None:
    """Sensitivity and the invariance it must keep: literal present versus words nearby.

    Exemptions are path prefixes from the project root, so a top-level coordination record is
    exempt while a ``coordination`` directory elsewhere is not.
    """
    (tmp_path / "dup.py").write_text('PATTERN = "^```audit-assignment"\n', encoding="utf-8")
    (tmp_path / "layout.py").write_text('SESSIONS = "stewart/sessions"\n', encoding="utf-8")
    (tmp_path / "ok.py").write_text('note = "assignments and the stewart tool are discussed"\n', encoding="utf-8")
    assert custody_literal_violations(tmp_path, ["dup.py", "layout.py", "ok.py"]) == [
        "dup.py: '```audit-assignment'", "layout.py: 'stewart/sessions'",
    ]
    home = tmp_path / "src" / "stewart"
    home.mkdir(parents=True)
    (home / "x.py").write_text('FENCE = "```audit-assignment"\n', encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    (tests / "t.py").write_text('FENCE = "```audit-assignment"\n', encoding="utf-8")
    for record in ("coordination/study/c.py", "scripts/coordination/c.py"):
        (tmp_path / record).parent.mkdir(parents=True)
        (tmp_path / record).write_text('FENCE = "```audit-report"\n', encoding="utf-8")
    assert custody_literal_violations(tmp_path, ["src/stewart/x.py", "tests/t.py", "coordination/study/c.py"]) == []
    assert custody_literal_violations(tmp_path, ["scripts/coordination/c.py"]) == [
        "scripts/coordination/c.py: '```audit-report'",
    ]


def disposition_binding_duplicates(sources: dict[str, str]) -> list[str]:
    """Find direct or locally aliased digest comparisons outside the shared validator.

    This is a narrow AST guard, not whole-program dataflow: dynamic key spelling
    and comparisons delegated through reflection are outside its coverage.
    Recording a digest in a receipt is not a second binding implementation.
    """
    import ast

    violations = []
    for filename, source in sources.items():
        for function in ast.walk(ast.parse(source)):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (filename, function.name) == ("triage.py", "_require_collection_binding"):
                continue
            aliases = set()

            def reads_digest(node):
                for item in ast.walk(node):
                    if isinstance(item, ast.Name) and item.id in aliases:
                        return True
                    if isinstance(item, ast.Subscript) and isinstance(item.slice, ast.Constant) and item.slice.value == "collection_sha256":
                        return True
                    if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr == "get":
                        if item.args and isinstance(item.args[0], ast.Constant) and item.args[0].value == "collection_sha256":
                            return True
                return False

            assignments = [node for node in ast.walk(function) if isinstance(node, ast.Assign)]
            # Resolve local aliases to a fixed point so assignment order cannot hide a duplicate.
            while True:
                before = set(aliases)
                for node in assignments:
                    if reads_digest(node.value):
                        aliases.update(target.id for target in node.targets if isinstance(target, ast.Name))
                if aliases == before:
                    break
            if any(reads_digest(node) for node in ast.walk(function) if isinstance(node, ast.Compare)):
                violations.append(f"{filename}:{function.name}")
    return sorted(violations)


def test_disposition_binding_has_one_validator():
    package = Path(stewart.__file__).parent
    assert disposition_binding_duplicates(runtime_sources(package)) == [], (
        "collection-digest binding comparisons belong in triage._require_collection_binding; "
        "submission, status, retention and resume must use the same comparison"
    )


def test_binding_ratchet_distinguishes_comparison_from_receipt_recording():
    sources = {
        "duplicate.py": 'def decide(d, actual):\n    expected = d.get("collection_sha256")\n    return actual == expected\n',
        "direct.py": 'def decide(d, actual):\n    return actual != d["collection_sha256"]\n',
        "record.py": 'def record(d):\n    return {"collection_sha256": d["collection_sha256"]}\n',
        "other.py": 'def decide(d, actual):\n    return actual == d["report_sha256"]\n',
    }
    assert disposition_binding_duplicates(sources) == ["direct.py:decide", "duplicate.py:decide"]
    assert disposition_binding_duplicates({"triage.py": 'def _require_collection_binding(d, actual):\n    return actual == d["collection_sha256"]\n'}) == []
    assert disposition_binding_duplicates({"triage.py": 'def validate_response(d, actual):\n    return actual == d["collection_sha256"]\n'}) == ['triage.py:validate_response']
    assert disposition_binding_duplicates({"triage.py": 'def bound_disposition(d, actual):\n    _require_collection_binding(d, actual)\n'}) == []


def archive_reader_duplicates(sources: dict[str, str]) -> list[str]:
    """Guard direct tar member reads/extraction outside the shared custody reader.

    This syntactic guard recognizes method calls, not reflective or delegated
    calls under arbitrary names. Tar writes and prose references are ignored.
    The collector's producer check precedes the receipt and separately verifies
    links; it is not a consumer of retained custody bytes.
    """
    import ast

    methods = {'extract', 'extractall', 'extractfile', 'getmember', 'getmembers'}
    violations = []
    for filename, source in sources.items():
        if filename == 'captured.py':
            continue
        tree = ast.parse(source)
        if filename == 'collect.py':
            tree.body = [node for node in tree.body if not (
                isinstance(node, ast.FunctionDef) and node.name == 'verify_archive')]
        if any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr in methods for node in ast.walk(tree)):
            violations.append(filename)
    return sorted(violations)


def test_archive_reads_have_one_custody_validator():
    package = Path(stewart.__file__).parent
    assert archive_reader_duplicates(runtime_sources(package)) == [], (
        'retention, handoff and status must share captured.collection_files for archive, member and payload identity checks'
    )


def test_archive_ratchet_distinguishes_member_reads_from_writes_and_prose():
    assert archive_reader_duplicates({
        'read.py': 'data = archive.extractfile(member).read()\n',
        'lookup.py': 'member = archive.getmember(name)\n',
        'write.py': 'archive.addfile(member, stream)\n',
        'prose.py': 'note = "archive.extractfile(member)"\n',
    }) == ['lookup.py', 'read.py']
    assert archive_reader_duplicates({'captured.py': 'data = archive.extractfile(member).read()\n'}) == []
    assert archive_reader_duplicates({'collect.py': 'def verify_archive():\n    bundle.getmember(name)\n'}) == []
    assert archive_reader_duplicates({'collect.py': 'def recover():\n    bundle.getmember(name)\n'}) == ['collect.py']


def declaration_parser_duplicates(sources: dict[str, str]) -> list[str]:
    """Find reserved fence literals outside the declaration authority.

    This is a syntactic guard over string/byte constants, including regexes. It
    does not detect dynamically assembled fence names or arbitrary reflection.
    Shared validator calls need no fence literal and remain admissible.
    """
    import ast

    found = []
    for filename, source in sources.items():
        if filename == "report_declaration.py":
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
                value = node.value.decode("utf-8", "replace") if isinstance(node.value, bytes) else node.value
                if "audit-report" in value:
                    found.append(filename)
                    break
    return sorted(found)


def test_declarations_have_one_parser_inside_custody_package():
    package = Path(stewart.__file__).parent
    assert declaration_parser_duplicates(runtime_sources(package)) == [], (
        "reserved report declarations belong to report_declaration.validate_report_declaration; "
        "custody consumers must call that authority rather than parsing again"
    )


def test_declaration_ratchets_detect_inner_and_outer_duplicates(tmp_path):
    planted = 'import re\ndef read(data):\n    return re.findall(rb"```audit-report\\n(.*?)```", data)\n'
    allowed = ('from stewart.report_declaration import validate_report_declaration\n'
               'def read(data, expected, sources):\n'
               '    return validate_report_declaration(data, expected=expected, sources=sources)\n')
    assert declaration_parser_duplicates({"status.py": planted}) == ["status.py"]
    assert declaration_parser_duplicates({"status.py": allowed}) == []
    assert declaration_parser_duplicates({"status.py": allowed + '\nnote = "report prose changed"\n'}) == []
    assert declaration_parser_duplicates({"report_declaration.py": planted}) == []
    (tmp_path / "duplicate.py").write_text(planted)
    assert custody_literal_violations(tmp_path, ["duplicate.py"]) == ["duplicate.py: '```audit-report'"]


def json_decoder_sites(sources: dict[str, str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Find stdlib decoder calls, including import aliases, and duplicate hooks.

    This package-local syntax guard does not resolve reflective imports or
    arbitrary interprocedural aliases. Comments and encoded payload text are
    deliberately outside its selector.
    """
    import ast

    sites, hooks = [], []
    for filename, source in sources.items():
        tree = ast.parse(source)
        modules, decoders = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.asname or a.name for a in node.names if a.name == "json")
            elif isinstance(node, ast.ImportFrom) and node.module in {"json", "json.decoder"}:
                decoders.update(a.asname or a.name for a in node.names if a.name in {"load", "loads", "JSONDecoder"})

        class Visitor(ast.NodeVisitor):
            function = "<module>"

            def visit_FunctionDef(self, node):
                previous = self.function
                self.function = node.name
                self.generic_visit(node)
                self.function = previous

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                fn = node.func
                if ((isinstance(fn, ast.Name) and fn.id in decoders)
                        or (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                            and fn.value.id in modules and fn.attr in {"load", "loads", "JSONDecoder"})):
                    sites.append((filename, self.function))
                if any(k.arg == "object_pairs_hook" for k in node.keywords):
                    hooks.append(filename)
                self.generic_visit(node)

        Visitor().visit(tree)
    return sorted(sites), sorted(hooks)


def test_control_json_has_one_decoder_and_raw_evidence_stays_separate():
    package = Path(stewart.__file__).parent
    sources = runtime_sources(package)
    assert len(sources) >= 25, "the parser guard must select the runtime package"
    sites, hooks = json_decoder_sites(sources)
    assert sites == [("_json.py", "loads_control"), ("experiment.py", "_run"), ("ledger.py", "parse_rows")], (
        "control readers must share _json.loads_control; only raw child receipt and ledger decoding stay permissive. "
        "Exact nonempty site counts also detect removal or duplication inside an allowed function."
    )
    assert hooks == ["_json.py"], "decoded-name uniqueness belongs to the control decoder alone"


def runtime_sources(package: Path) -> dict[str, str]:
    """Select runtime modules recursively, excluding the separate development trees."""
    sources = {str(p.relative_to(package)): p.read_text() for p in package.rglob("*.py")
               if p.relative_to(package).parts[0] not in {"tests", "scripts"}}
    assert sources, "the authority guard cannot measure an empty source population"
    return sources


def test_json_guard_population_keeps_nested_runtime_and_excludes_development(tmp_path):
    decoder = "import json\nvalue = json.loads(data)\n"
    for name in ("nested/consumer.py", "tests/example.py", "scripts/example.py"):
        member = tmp_path / name
        member.parent.mkdir(parents=True, exist_ok=True)
        member.write_text(decoder)
    sources = runtime_sources(tmp_path)
    assert list(sources) == ["nested/consumer.py"]
    assert json_decoder_sites(sources) == ([("nested/consumer.py", "<module>")], [])
    (tmp_path / "notes.txt").write_text(decoder)
    assert runtime_sources(tmp_path) == sources


def test_json_ratchet_detects_new_readers_but_ignores_payloads_and_shared_calls():
    allowed = "from stewart._json import loads_control\nvalue = loads_control(data)\n"
    assert json_decoder_sites({"future.py": allowed}) == ([], [])
    assert json_decoder_sites({"future.py": allowed + '# json.loads(data)\ntext = "object_pairs_hook"\n'}) == ([], [])
    for planted in (
        "import json as codec\nvalue = codec.loads(data)\n",
        "from json import loads as parse\nvalue = parse(data)\n",
        "from json.decoder import JSONDecoder as Reader\nvalue = Reader().decode(data)\n",
    ):
        assert json_decoder_sites({"new/future.py": planted}) == ([("new/future.py", "<module>")], [])
    assert json_decoder_sites({"future.py": "value = parse(data, object_pairs_hook=another_rule)\n"}) == ([], ["future.py"])
