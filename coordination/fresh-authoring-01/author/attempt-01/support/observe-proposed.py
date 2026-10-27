"""UNEXECUTED proposal: emit observations, never an experiment verdict.

Future execution requires a separate grant and independent output capture.
No project installation, sys.path mutation, wrapper operation or subprocess.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


PINNED = {
    "ledger.py": "e77d83e723d28385b73370832d6a2b0f2f87fcc84c6ad2905135d68eb0ee9696",
    "_json.py": "794f886883bab334582a4b16e9d60137498c2e7c2f3de259b0ce9680a05ada92",
    "test_stewart_ledger.py": "332e4a1ad8cd409b520ca7d11242ee7f2779e7aed5bbf0ab3376232c810c01ce",
}
SPECIMENS = (
    "A-complete.jsonl",
    "B-duplicate.jsonl",
    "C-note-invariant.jsonl",
    "D-control-extinguished.jsonl",
    "E-admission-before-reach.jsonl",
    "F-parse-problem.jsonl",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(value):
    print(json.dumps(value, sort_keys=True, allow_nan=False), flush=True)


def load_selected(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--specimens", required=True, type=Path)
    args = parser.parse_args()
    paths = {"packet/" + name: args.packet / name for name in PINNED}
    paths.update({"authored/" + name: args.specimens / name for name in (
        "review.json", "PREDICTIONS.md", "CONSTRUCTION.md", *SPECIMENS
    )})
    paths["observer"] = Path(__file__)
    before = {name: digest(path) for name, path in paths.items()}
    emit({"stage": "before", "python": sys.version, "executable": sys.executable,
          "hashes": before, "continuous_preservation_established": False})
    for name, expected in PINNED.items():
        if before["packet/" + name] != expected:
            raise RuntimeError("Pinned input differs; stop before loading: " + name)
    ledger = load_selected("selected_ledger", args.packet / "ledger.py")
    decoder = load_selected("selected_control_json", args.packet / "_json.py")
    review = decoder.loads_control((args.specimens / "review.json").read_bytes())
    # The supplied validator constraints require prior maintainer inspection.
    # This observer does not call or replace the wrapper review validator.
    for name in SPECIMENS:
        raw = (args.specimens / name).read_bytes()
        rows, problems = ledger.parse_rows(raw)
        summary = ledger.summarize(rows, cases=review["cases"])
        emit({"stage": "specimen", "name": name,
              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
              "parsed_rows": len(rows),
              "raw_valid_compare_rows": sum(row["kind"] == "compare" for row in rows),
              "parse_problems": problems, "summary": summary,
              "prerequisites": ledger.prerequisites(summary)})
    after = {name: digest(path) for name, path in paths.items()}
    emit({"stage": "after", "hashes": after, "same_at_endpoints": before == after,
          "continuous_preservation_established": False})
    if before != after:
        raise RuntimeError("Protected bytes differ at endpoints; retain output and stop")


if __name__ == "__main__":
    main()
