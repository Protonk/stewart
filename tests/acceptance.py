"""Independent installed-wheel acceptance, using only stdlib and public commands.

Run in a provisioned guest with no shared directories and networking disabled.
The destination must be new. The unavailable path must already have passed the
paired sentinel qualification under this same guest/user/interpreter setup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


class Scenario:
    def __init__(self, root: Path, unavailable: Path):
        self.root, self.unavailable = root, unavailable
        root.mkdir(parents=True, exist_ok=False)
        self.repo, self.paste = root / "ordinary project", root / "unrelated paste"
        self.repo.mkdir(); self.paste.mkdir()
        self.logs = root / "commands"; self.logs.mkdir()
        self.ws = "audits/parser-review"
        self.env = dict(os.environ, PYTHONPATH=str(self.paste),
                        STEWART_MANAGER_HOME=str(root / "manager storage"))
        self.number = 0
        self.checks = []
        self.cli = [sys.executable, "-I", "-B", "-m", "stewart"]

    def check(self, label, value):
        assert value, label
        self.checks.append(label)

    def run(self, argv, *, cwd=None, allowed=(0,), env=None):
        self.number += 1
        prefix = self.logs / f"{self.number:04d}"
        result = subprocess.run([str(arg) for arg in argv], cwd=cwd or self.paste,
                                env=env or self.env, text=True, capture_output=True, timeout=90)
        prefix.with_suffix(".json").write_text(json.dumps({"argv": [str(arg) for arg in argv],
            "cwd": str(cwd or self.paste), "returncode": result.returncode}, indent=2) + "\n")
        prefix.with_suffix(".stdout").write_text(result.stdout)
        prefix.with_suffix(".stderr").write_text(result.stderr)
        assert result.returncode in allowed, f"command {self.number} failed: {result.stderr} {result.stdout}"
        return result

    def git(self, *argv):
        return self.run(["/usr/bin/git", *argv], cwd=self.repo).stdout.strip()

    def action(self, command, *arguments, allowed=(0,)):
        result = self.run([*self.cli, "--repo", self.repo, "--workspace", self.ws, "--json", command, *arguments],
                          allowed=allowed)
        data = json.loads(result.stdout)
        assert data["exit_code"] == result.returncode
        return data["result"] if data["ok"] else data

    def setup(self):
        self.check("PAWL path absent before acceptance", not self.unavailable.exists())
        self.run([*self.cli, "--help"])
        missing = self.run([*self.cli, "--workspace", self.ws, "--json", "status", "--audit-id", "missing"], allowed=(2,))
        self.check("missing explicit repository refuses", "--repo" in missing.stdout + missing.stderr)
        probe = self.run([sys.executable, "-I", "-B", "-c",
            "import json,sys,stewart,stewart.api; print(json.dumps({'file':stewart.__file__,"
            "'loaded':sorted(k for k in sys.modules if k.startswith('stewart'))}))"])
        self.installation = json.loads(probe.stdout)
        self.check("API import is lazy", self.installation["loaded"] == ["stewart", "stewart.api"])
        self.check("wheel imports from selected environment", Path(self.installation["file"]).is_relative_to(Path(sys.prefix)))
        self.git("init", "-q", "-b", "review-work")
        self.git("config", "user.name", "Stewart acceptance")
        self.git("config", "user.email", "acceptance@example.invalid")
        (self.repo / ".git/info/exclude").write_text("/.scratch/stewart/\n/.scratch/stewart-runtimes/\n")
        (self.repo / "input.txt").write_text("a known committed value\n")
        directory = self.repo / self.ws; directory.mkdir(parents=True)
        (directory / "AUDITOR.md").write_text("Read the bounded prompt. Use only its granted operations.\n")
        (directory / "MAINTAINER.md").write_text("Preserve raw evidence and review each custody gap.\n")
        (directory / "PROMPT.md").write_text("**UNASSIGNED**\n")
        self.git("add", "."); self.git("commit", "-qm", "Ordinary project inputs")
        self.check("ordinary project has no tool or required venv", all(not (self.repo / name).exists() for name in ("tools", "stewart", ".venv")))
        self.check("project branch is not main", self.git("branch", "--show-current") == "review-work")
        self.check("ordinary project read succeeds", (self.repo / "input.txt").read_text() == "a known committed value\n")

    def prepare(self, ident, *, paused=False, extra=(), experiment=None):
        initialized = self.action("init", "--audit-id", ident, "--input", "input.txt", *extra)
        metadata = initialized["assignment"]
        if experiment:
            metadata.update(experiment=experiment, scratch_paths=[f"{self.ws}/scratch/{ident}/artifacts", experiment["output_area"]])
            metadata["input_files"].append(experiment["protected_manifest"])
        sections = {"Question": "Does this synthetic custody flow preserve the selected value?",
                    "Decision": "Whether this installed distribution can manage an ordinary project.",
                    "Scope and exclusions": "Synthetic files only; no external observations.",
                    "Evidence": "The committed input and independently retained observations.",
                    "Stop condition": "Stop and preserve evidence on the first failed comparison."}
        if experiment:
            sections["Experiment authorization"] = (
                "Permission: one released synthetic Python script invocation.\n"
                "Target and variation: ordinary value equality and a planted disagreement.\n"
                "Protected state: input.txt byte-identical at both endpoints.\n"
                "Construction area: the declared artifacts directory.\n"
                "Execution allowance: the grant's one command template.\n"
                "Action bounds and stops: one invocation; stop on failure.\n"
                "Preservation evidence: the protected manifest and captured output.")
        text = "# Assigned synthetic question\n\n```audit-assignment\n" + json.dumps(metadata, indent=2) + "\n```\n\n"
        text += "".join(f"## {title}\n{body}\n\n" for title, body in sections.items())
        (self.repo / self.ws / "PROMPT.md").write_text(text)
        self.git("add", "--", f"{self.ws}/PROMPT.md"); self.git("commit", "-qm", f"Assign {ident}")
        flags = ("--mode", "paused", "--writers-paused", "--pause-note", "The only fixture writer is this driver and is paused.") if paused else ()
        return self.action("prepare", *flags), metadata

    def helpers(self, prepared):
        commands = re.findall(r"```sh\n(.*?)\n```", Path(prepared["launch"]).read_text(), re.S)
        self.check("handoff supplies four fixed helper operations", len(commands) == 4)
        for command in commands:
            argv = shlex.split(command)
            self.check("helper uses the issued worktree", argv[:3] == ["cd", prepared["worktree"], "&&"])
            self.run(argv[3:], cwd=Path(prepared["worktree"]))

    def disposition(self, ident, collection):
        draft = self.action("triage-draft", "--audit-id", ident, "--collection", collection)
        response = draft["response"]
        response["decision"] = "Retain this synthetic observation; it establishes no project semantics."
        response["custody_gaps"] = {key: "Recorded and reviewed as a synthetic limitation." for key in response["custody_gaps"]}
        if "follow_up" in response:
            response["follow_up"].update(disposition="decline", reason="No further synthetic scope is granted.")
        location = self.root / f"response-{ident}.json"; location.write_text(json.dumps(response))
        return self.action("triage", "--audit-id", ident, "--collection", collection,
                           "--response", str(location), "--actor", "acceptance driver")

    def lifecycle(self):
        prepared, meta = self.prepare("snapshot")
        self.helpers(prepared)
        view = self.action("status", "--audit-id", "snapshot")
        command = next(item for item in view["next_actions"] if item["action"] == "collect")
        # Execute the printed manager argv from the unrelated paste directory.
        argv = list(command["argv"])
        argv[argv.index("--auditor-stopped") + 1] = "finished"
        argv.insert(argv.index("collect"), "--json")
        captured = json.loads(self.run(argv).stdout)["result"]
        self.check("printed manager command kept its installation", "runtime" in command and command["env"] == {})
        disposition = self.disposition("snapshot", captured["collection"])
        self.action("retain", "--audit-id", "snapshot", "--triage", disposition["triage"], "--report")
        self.check("retained report equals raw capture", (self.repo / meta["report_path"]).read_bytes() == (Path(captured["path"]) / "REPORT.md").read_bytes())
        package = self.action("export", "--audit-id", "snapshot", "--collection", captured["collection"],
                              "--select", "REPORT.md", "--select", "runtime-assets", "--select", "runtime-observation:collection",
                              "--output", ".scratch/transferred-evidence", "--actor", "acceptance driver")
        shutil.rmtree(prepared["runtime"]["root"])
        recovered = self.action("recover-runtime", "--audit-id", "snapshot", "--actor", "acceptance driver")
        self.check("recovery uses a fresh runtime path", recovered["runtime"]["root"] != prepared["runtime"]["root"])
        reused, reused_meta = self.prepare("reuse", extra=("--evidence-package", package["package"]))
        self.check("export is reusable without source runtime", len(reused_meta["supplemental_inputs"]) == 9)
        self.helpers(reused)
        paused, _ = self.prepare("paused", paused=True)
        self.helpers(paused)
        collected = self.action("collect", "--audit-id", "paused", "--auditor-stopped", "finished")
        triaged = self.disposition("paused", collected["collection"])
        resumed = self.action("resume", "--audit-id", "paused", "--triage", triaged["triage"], "--reason", "The synthetic hold is released.")
        self.check("paused session has a recorded resume", Path(resumed["path"]).is_file())

    def experiment(self):
        digest = hashlib.sha256((self.repo / "input.txt").read_bytes()).hexdigest()
        manifest = self.repo / "protected.json"
        manifest.write_text(json.dumps({"schema": 1, "files": {"input.txt": digest}}))
        self.git("add", "--", "protected.json"); self.git("commit", "-qm", "Protect synthetic input")
        base = f"{self.ws}/scratch/measurement"
        grant = {"schema": "stewart.experiment-grant/2", "permission": "construction+execution",
                 "script": f"{base}/artifacts/experiment.py", "freeze": [f"{base}/artifacts/prediction.md"],
                 "output_area": f"{base}/run", "protected_manifest": "protected.json",
                 "interpreter": "tool-interpreter", "environment": "minimal", "cwd": "worktree",
                 "argv_template": ["{interpreter}", "{script}", "{output}"], "invocations": 1}
        prepared, _ = self.prepare("measurement", experiment=grant)
        worktree = Path(prepared["worktree"])
        script = worktree / grant["script"]; script.parent.mkdir(parents=True)
        cases = [
            {"id": "ordinary", "population": "ordinary", "role": "value varies", "expected_admission": True, "prediction": "agree", "measurements": ["value"]},
            {"id": "metadata", "population": "ordinary", "role": "ignored prose varies", "expected_admission": True, "prediction": "agree", "measurements": ["value"]},
            {"id": "control", "population": "control", "role": "planted disagreement", "expected_admission": True, "prediction": "mismatch", "measurements": ["value"]},
            {"id": "refusal", "population": "ordinary", "role": "inadmissible by construction", "expected_admission": False, "prediction": "refused", "measurements": []}]
        script.write_text(
            "import json,sys\nfrom pathlib import Path\nfrom _stewart_ledger_v1 import Ledger\n"
            "output=Path(sys.argv[1]); ledger=Ledger(output/'ledger.jsonl')\n"
            f"cases={cases!r}\n"
            "for item in cases:\n"
            "    item=dict(item); ident=item.pop('id'); ledger.declare(ident, **item)\n"
            "    ledger.reach(ident); ledger.admit(ident, item['expected_admission'], reason='synthetic membership')\n"
            "ledger.compare('ordinary','value',1,1)\n"
            "ledger.compare('metadata','value',1,1,note='unrelated metadata changed')\n"
            "control=ledger.compare('control','value',1,2)\n"
            "(output/'receipt.json').write_text(json.dumps({'control':control,'ledger':sys.modules['_stewart_ledger_v1'].__file__}))\n"
            "print('synthetic child complete')\n")
        (worktree / grant["freeze"][0]).write_text("Ordinary values agree, the planted control disagrees, and refusal is not a measurement.\n")
        review = {"cases": cases, "admissibility_reasoning": "The driver constructs all selected cases.",
                  "static_review": ["The script writes only granted output using the pinned ledger."],
                  "limits": ["Synthetic instrumentation only; no project semantics measured."]}
        review_path = self.root / "experiment-review.json"; review_path.write_text(json.dumps(review))
        released = self.action("release", "--audit-id", "measurement", "--review", str(review_path), "--actor", "acceptance driver")
        attempted = self.action("run", "--audit-id", "measurement", "--release", released["release"])
        record = attempted["record"]
        self.check("control instrument actually fires", record["ledger"]["summary"]["control"]["mismatches"] == 1)
        self.check("ordinary comparisons remain distinct", record["ledger"]["summary"]["ordinary"]["mismatches"] == 0)
        self.check("protected input remains unchanged", hashlib.sha256((worktree / "input.txt").read_bytes()).hexdigest() == digest)
        self.check("child output is retained", "synthetic child complete" in (Path(released["record"]["attempt"]) / "stdout.txt").read_text())
        repeated = self.action("run", "--audit-id", "measurement", "--release", released["release"], allowed=(2,))
        self.check("released invocation cannot run twice", repeated["error"]["reason"] == "release_consumed")

    def failures(self):
        prepared, metadata = self.prepare("damaged")
        worktree, session = Path(prepared["worktree"]), Path(prepared["session"])
        report = worktree / metadata["report_path"]
        report.write_text("Malformed declaration retained before runtime validation.\n```audit-report\n{\n")
        expected = report.read_bytes()
        runtime = Path(prepared["runtime"]["root"])
        ledger = next(item["path"] for item in prepared["runtime"]["manifest"]["entries"] if item["path"].endswith("/ledger.py"))
        (runtime / ledger).write_text("raise RuntimeError('changed supplied code')\n")
        captured = self.action("collect", "--audit-id", "damaged", "--auditor-stopped", "interrupted", allowed=(1,))
        self.check("runtime damage preserves malformed raw report", (Path(captured["path"]) / "REPORT.md").read_bytes() == expected)
        self.check("manager independently detects changed supplied code", any("runtime" in error for error in captured["receipt"]["errors"]))
        partial = session / "collections/20990101T000000-01234567"; partial.mkdir()
        (partial / "STARTED.json").write_text("{}\n")
        view = self.action("status", "--audit-id", "damaged")
        self.check("partial collection remains visible", any(item["name"] == partial.name and any(problem["reason"] == "collection_incomplete" for problem in item["problems"]) for item in view["collections"]))
        historical = session.parent / "unsupported"; historical.mkdir()
        unsupported = json.loads((session / "session.json").read_text()); unsupported["schema_version"] = -1
        old_bytes = json.dumps(unsupported).encode(); (historical / "session.json").write_bytes(old_bytes)
        view = self.action("status", "--audit-id", "unsupported")
        self.check("unsupported history stays visible as a problem", any(problem["reason"] == "session_schema_unsupported" for problem in view["session"]["problems"]))
        refused = self.action("collect", "--audit-id", "unsupported", "--auditor-stopped", "finished", allowed=(2,))
        self.check("unsupported history refuses mutation without rewriting", refused["error"]["reason"] == "session_schema_unsupported" and (historical / "session.json").read_bytes() == old_bytes)

    def decoys(self):
        marker = self.paste / "startup-hook-fired"
        (self.paste / "sitecustomize.py").write_text(f"open({str(marker)!r},'w').write('control')\n")
        (self.paste / "stewart.py").write_text("raise RuntimeError('paste-directory decoy')\n")
        poisoned = dict(self.env, PYTHONHOME="/nonexistent-python-home")
        self.run([str(Path(sys.executable).parent / "stewart"), "--help"], env=poisoned)
        self.run([*self.cli, "--help"], env=poisoned)
        self.check("installed startup ignores caller settings and decoys", not marker.exists())
        self.run([sys.executable, "-B", "-c", "pass"])
        self.check("unisolated hook control fires", marker.read_text() == "control")
        marker.unlink()

    def finish(self):
        self.check("PAWL path absent after acceptance", not self.unavailable.exists())
        result = {"python": sys.version, "executable": sys.executable, "installation": self.installation,
                  "git": self.run(["/usr/bin/git", "--version"]).stdout.strip(), "commands": self.number,
                  "checks": self.checks, "selected": len(self.checks), "passed": len(self.checks),
                  "unavailable": str(self.unavailable), "root": str(self.root)}
        (self.root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--unavailable", type=Path, required=True)
    args = parser.parse_args()
    scenario = Scenario(args.root.resolve(), args.unavailable)
    scenario.setup()
    scenario.lifecycle()
    scenario.experiment()
    scenario.failures()
    scenario.decoys()
    scenario.finish()


if __name__ == "__main__":
    main()
