"""Standalone authority guards with measured populations and paired controls."""
from pathlib import Path
import os
import pytest
import stewart

HOME = "src/stewart/"
LITERALS = ("```audit-assignment", "```audit-report", ".scratch/stewart")
EXEMPT_PREFIXES = (HOME, "tests/")


pytestmark = pytest.mark.smoke


def source_python(root):
    names = sorted(str(p.relative_to(root)) for p in root.rglob("*.py")
                   if p.relative_to(root).parts[0] not in {".scratch", ".git", "dist", "build"})
    assert len([name for name in names if name.startswith(HOME)]) >= 29, "runtime source population vanished"
    return names


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


def test_audit_custody_machinery_has_one_home() -> None:
    repo_root = Path(os.environ["STEWART_TEST_PROJECT"])
    assert custody_literal_violations(repo_root, source_python(repo_root)) == [], (
        "a second assignment parser or session layout appeared outside src/stewart; "
        "route callers to the package instead of adding a helper beside the workspace"
    )


def test_ratchet_goes_red_on_a_planted_duplicate_and_ignores_unrelated_text(tmp_path: Path) -> None:
    """Sensitivity and the invariance it must keep: literal present versus words nearby."""
    (tmp_path / "dup.py").write_text('PATTERN = "^```audit-assignment"\n', encoding="utf-8")
    (tmp_path / "layout.py").write_text('SESSIONS = ".scratch/stewart"\n', encoding="utf-8")
    (tmp_path / "ok.py").write_text('note = "assignments and the stewart tool are discussed"\n', encoding="utf-8")
    assert custody_literal_violations(tmp_path, ["dup.py", "layout.py", "ok.py"]) == [
        "dup.py: '```audit-assignment'", "layout.py: '.scratch/stewart'",
    ]
    home = tmp_path / "src" / "stewart"
    home.mkdir(parents=True)
    (home / "x.py").write_text('FENCE = "```audit-assignment"\n', encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    (tests / "t.py").write_text('FENCE = "```audit-assignment"\n', encoding="utf-8")
    assert custody_literal_violations(tmp_path, ["src/stewart/x.py", "tests/t.py"]) == []


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
    assert sites == [("_json.py", "loads_control"), ("experiment.py", "run"), ("ledger.py", "parse_rows")], (
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
