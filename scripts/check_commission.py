"""Exercise an installed commission binary with retained independent witnesses.

Use an explicit isolated Python interpreter. Each evidence directory is new;
commands, stdout/stderr, inputs and changed specimens remain for review. This
does not exercise audit results, qualify another host, or delete artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.absolute()
    evidence.mkdir(parents=True, exist_ok=False)
    installed = evidence / "installed"
    installed.mkdir()
    binary = installed / "stewart-commission"
    shutil.copyfile(args.binary, binary)
    binary.chmod(0o700)
    work = Path(tempfile.mkdtemp(prefix="stewart-commission-check-", dir="/private/tmp"))
    witness = evidence / "witness"
    witness.mkdir()
    write_json(evidence / "START.json", {
        "binary_source": str(args.binary.absolute()), "installed_binary": str(binary),
        "binary_sha256": digest(binary.read_bytes()), "cwd": str(work),
        "observer": "independent external CLI driver", "working_state_retained": str(work),
    })
    checks = []
    calls = []

    def check(label, condition, detail=None):
        checks.append({"check": label, "passed": bool(condition), "detail": detail})

    def run(*arguments, expected=0):
        index = len(calls) + 1
        stem = f"command-{index:03d}"
        argv = [str(binary), *map(str, arguments)]
        write_json(evidence / f"{stem}.start.json", {"argv": argv, "cwd": str(work)})
        try:
            result = subprocess.run(argv, cwd=work, capture_output=True, timeout=20)
        except subprocess.TimeoutExpired as exc:
            result = subprocess.CompletedProcess(argv, 124, exc.stdout or b"", exc.stderr or b"")
        for stream in ("stdout", "stderr"):
            with (evidence / f"{stem}.{stream}").open("xb") as output:
                output.write(getattr(result, stream))
        calls.append({"command": stem, "argv": argv, "exit": result.returncode})
        if expected is not None:
            check(f"{stem} expected exit", result.returncode == expected,
                  {"expected": expected, "actual": result.returncode})
        return result

    def specimen(name, large=False):
        base = work / name
        base.mkdir()
        sources = base / "sources"
        sources.mkdir()
        question = b"Does the recorded undertaking preserve the selected bytes?\n"
        material = bytes(range(256)) + b"\x00selected original specimen\xff\n"
        payloads = {"question": question, "material": material,
                    "guidance": b"Keep observations distinct from attributed claims.\n"}
        if large:
            payloads.update({f"large{i}": bytes([70+i]) * (16 * 1024 * 1024) for i in range(6)})
        members = []
        for ident, raw in payloads.items():
            source = sources / ident
            source.write_bytes(raw)
            members.append({"id": ident, "role": "question" if ident == "question" else
                            "guidance" if ident == "guidance" else "material",
                            "source": str(source), "view": ident + ".original",
                            "size": len(raw), "sha256": digest(raw)})
        request = {"schema": "stewart.commission-request/1", "request_id": name,
                   "custodian": "Acceptance investigator", "grants": "Read selected originals.",
                   "limits": "No investigation or result custody is commissioned.", "members": members}
        request_path = base / "request.json"
        write_json(request_path, request)
        bundle = base / "bundle"
        bundle.mkdir()
        observed = witness / name
        observed.mkdir()
        shutil.copyfile(request_path, observed / "request.json")
        for ident, raw in payloads.items():
            # Big controls have an independent digest/size witness, small operands exact bytes.
            if not ident.startswith("large"):
                (observed / ident).write_bytes(raw)
        write_json(observed / "members.json", members)
        return base, sources, request_path, bundle, payloads

    def pin(result):
        value = json.loads(result.stdout)
        return value.get("receipt_sha256") or value.get("acceptance_sha256")

    def snapshot_files(directory):
        return {str(p.relative_to(directory)): digest(p.read_bytes())
                for p in directory.rglob("*") if p.is_file() and not p.is_symlink()}

    def interrupt(request, bundle, label):
        argv = [str(binary), "accept", "--request", str(request), "--bundle", str(bundle)]
        write_json(evidence / f"{label}.start.json", {"argv": argv, "cwd": str(work)})
        with (evidence / f"{label}.stdout").open("xb") as out, (evidence / f"{label}.stderr").open("xb") as err:
            process = subprocess.Popen(argv, cwd=work, stdout=out, stderr=err)
            deadline = time.monotonic() + 15
            observed = []
            while process.poll() is None and time.monotonic() < deadline:
                observed = [str(p.relative_to(bundle)) for p in bundle.rglob("*")
                            if p.is_file() and p.name != "INTENT.json" and p.stat().st_size > 1024*1024]
                if observed:
                    process.send_signal(signal.SIGKILL)
                    break
                time.sleep(0.001)
            if process.poll() is None:
                process.kill()
            result = process.wait()
        write_json(evidence / f"{label}.end.json", {"pid": process.pid, "exit": result,
                                                   "observed_large_files_before_signal": observed})
        check(label + " firing: killed after payload observed", result == -signal.SIGKILL and bool(observed))
        return snapshot_files(bundle)

    try:
        base, sources, request, bundle, payloads = specimen("healthy")
        accepted = run("accept", "--request", request, "--bundle", bundle)
        receipt_pin = pin(accepted) if accepted.returncode == 0 else None
        check("acceptance exposes external receipt pin", isinstance(receipt_pin, str) and len(receipt_pin) == 64)
        pin_args = ["--receipt-sha256", receipt_pin] if receipt_pin else []
        for ident, raw in payloads.items():
            result = run("read", "--bundle", bundle, "--member", ident, *pin_args)
            check("original " + ident + " exact bytes", result.stdout == raw)
        result = run("read", "--bundle", bundle, "--member", "@request", *pin_args)
        check("raw request recovered exactly", result.stdout == request.read_bytes())
        before = snapshot_files(bundle)
        replay = run("accept", "--request", request, "--bundle", bundle)
        check("lost-reply lookup returns same receipt", pin(replay) == receipt_pin)
        check("completed lookup does not add or alter custody records", snapshot_files(bundle) == before)

        # Preserve the inaccessible source and its original witness, then move the delivered bundle.
        sources.rename(base / "sources-unavailable-to-recorded-paths")
        moved = work / "unrelated" / "nested" / "moved-bundle"
        moved.parent.mkdir(parents=True)
        bundle.rename(moved)
        run("inspect", "--bundle", moved, *pin_args)
        result = run("read", "--bundle", moved, "--member", "material", *pin_args)
        check("moved independent read survives original source loss", result.stdout == payloads["material"])
        replay = run("accept", "--request", request, "--bundle", moved)
        check("completed lookup needs no original inputs", pin(replay) == receipt_pin)

        changed_request = json.loads(request.read_text())
        changed_request["grants"] = "A materially different undertaking."
        changed = base / "changed-request.json"
        write_json(changed, changed_request)
        refused = run("accept", "--request", changed, "--bundle", moved, expected=None)
        check("same key cannot bind changed undertaking", refused.returncode != 0)
        check("changed intent refusal preserves delivered bytes", snapshot_files(moved) == before)

        # Changed selected bytes are a new commission, not mutation of the old one.
        sources.mkdir()
        for ident, raw in payloads.items():
            (sources / ident).write_bytes(raw)
        new_raw = payloads["material"] + b"different selected bytes"
        (sources / "material").write_bytes(new_raw)
        new_request = json.loads(request.read_text())
        member = next(item for item in new_request["members"] if item["id"] == "material")
        member.update(size=len(new_raw), sha256=digest(new_raw))
        r2_changed = base / "selected-changed.json"
        write_json(r2_changed, new_request)
        (witness / "changed-selected-material").write_bytes(new_raw)
        bundle2 = work / "same-coordinates-changed-material"
        bundle2.mkdir()
        second = run("accept", "--request", r2_changed, "--bundle", bundle2)
        check("changed selected input changes receipt identity", pin(second) != receipt_pin)
        result = run("read", "--bundle", bundle2, "--member", "material")
        check("differing selection actually recovers different operand", result.stdout == new_raw)
        (sources / "material").write_bytes(payloads["material"])
        invariant_bundle = work / "same-intent-new-destination"
        invariant_bundle.mkdir()
        invariant = run("accept", "--request", request, "--bundle", invariant_bundle)
        check("destination alone leaves receipt binding invariant", pin(invariant) == receipt_pin)

        matches = [p for p in moved.rglob("*") if p.is_file() and p.read_bytes() == payloads["material"]]
        check("damage firing: exact selected payload located", len(matches) == 1)
        if len(matches) == 1:
            matches[0].rename(witness / "held-original-material")
            matches[0].write_bytes(b"corrupt replacement")
            bad = run("read", "--bundle", moved, "--member", "material", *pin_args, expected=None)
            check("changed retained payload refused", bad.returncode != 0 and bad.stdout != payloads["material"])
            good = run("read", "--bundle", moved, "--member", "question", *pin_args)
            check("unaffected selected question still recoverable", good.stdout == payloads["question"])
            check("surrounding damage qualification is present", bool(good.stderr))
        wrong_pin = "0" * 64 if receipt_pin != "0" * 64 else "1" * 64
        bad = run("read", "--bundle", moved, "--member", "question", "--receipt-sha256", wrong_pin, expected=None)
        check("external receipt mismatch refuses bytes", bad.returncode != 0 and not bad.stdout)

        duplicate = base / "duplicate.json"
        duplicate.write_text('{"schema":"stewart.commission-request/1","x":{"a":1,"\\u0061":2}}')
        dup_bundle = base / "duplicate-bundle"
        dup_bundle.mkdir()
        bad = run("accept", "--request", duplicate, "--bundle", dup_bundle, expected=None)
        check("nested escape-equivalent duplicate refused without effects", bad.returncode != 0 and not list(dup_bundle.iterdir()))

        linked = work / "linked"
        linked.symlink_to(bundle2.parent, target_is_directory=True)
        old = snapshot_files(bundle2)
        bad = run("inspect", "--bundle", linked / bundle2.name, expected=None)
        check("linked bundle ancestor refused", bad.returncode != 0)
        check("link refusal preserves outside bundle", snapshot_files(bundle2) == old)
        fifo = work / "request-fifo"
        os.mkfifo(fifo)
        bad = run("accept", "--request", fifo, "--bundle", dup_bundle, expected=None)
        check("special request refuses without blocking", bad.returncode not in (0,124))

        _, _, interrupted_request, interrupted_bundle, _ = specimen("interrupted", large=True)
        partial = interrupt(interrupted_request, interrupted_bundle, "kill-during-copy")
        bad = run("accept", "--request", interrupted_request, "--bundle", interrupted_bundle, expected=None)
        check("ordinary accept does not replay incomplete intake", bad.returncode != 0)
        run("complete", "--request", interrupted_request, "--bundle", interrupted_bundle)
        after = snapshot_files(interrupted_bundle)
        check("explicit completion keeps all partial output unchanged", all(after.get(k) == v for k,v in partial.items()))
        result = run("read", "--bundle", interrupted_bundle, "--member", "question")
        check("completed interruption recovers original question", result.stdout == payloads["question"])

        _, _, abandoned_request, abandoned_bundle, _ = specimen("abandoned", large=True)
        partial = interrupt(abandoned_request, abandoned_bundle, "kill-before-disposition")
        run("abandon", "--bundle", abandoned_bundle, "--actor", "Acceptance manager", "--reason", "Explicitly retain partial material; requested acceptance not completed.")
        after = snapshot_files(abandoned_bundle)
        check("incomplete disposition retains partial evidence", all(after.get(k) == v for k,v in partial.items()))
        bad = run("complete", "--request", abandoned_request, "--bundle", abandoned_bundle, expected=None)
        check("disposed intake cannot acquire later acceptance", bad.returncode != 0)
    except Exception as exc:
        check("driver completed without unexpected exception", False, repr(exc))
    result = {"checks": checks, "passed": sum(item["passed"] for item in checks),
              "total": len(checks), "commands": calls, "work": str(work),
              "scope": "Installed C CLI, original undertaking only; no audit result custody or host-wide enforcement claim."}
    write_json(evidence / "RESULT.json", result)
    print(json.dumps({"passed": result["passed"], "total": result["total"],
                      "failures": [c for c in checks if not c["passed"]], "evidence": str(evidence)}))
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
