"""Record one explicitly requested frozen-writer operation for this study."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--configuration", type=Path, required=True)
parser.add_argument("--records", type=Path, required=True)
parser.add_argument("--label", required=True)
parser.add_argument("--key")
parser.add_argument("--lifetime")
parser.add_argument("operation", nargs=argparse.REMAINDER)
args = parser.parse_args()
if not args.label or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.label):
    parser.error("label must be a new ordinary ASCII record name")
operation = args.operation[1:] if args.operation[:1] == ["--"] else args.operation
if not operation:
    parser.error("an explicit operation is required")
config = json.loads(args.configuration.read_text())
args.records.mkdir(parents=True, exist_ok=True)
argv = [config["python"], "-I", "-B", "-m", "stewart", "--repo", config["repo"],
        "--workspace", config["workspace"], "--json"]
if args.key:
    argv += ["--request-key", args.key]
if args.lifetime:
    argv += ["--lifetime", args.lifetime]
argv += operation
start = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "argv": argv,
         "cwd": config["repo"], "STEWART_MANAGER_HOME": config["manager_home"]}
with (args.records / (args.label + ".START.json")).open("x") as stream:
    json.dump(start, stream, indent=2)
environment = dict(os.environ)
environment["STEWART_MANAGER_HOME"] = config["manager_home"]
with (args.records / (args.label + ".stdout")).open("xb") as out, (args.records / (args.label + ".stderr")).open("xb") as err:
    child = subprocess.Popen(argv, cwd=config["repo"], env=environment, stdout=out, stderr=err)
    with (args.records / (args.label + ".PID.json")).open("x") as stream:
        json.dump({"pid": child.pid}, stream)
    code = child.wait()
with (args.records / (args.label + ".END.json")).open("x") as stream:
    json.dump({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "exit": code}, stream, indent=2)
print(json.dumps({"operation": args.label, "exit": code, "stdout": str(args.records / (args.label + ".stdout"))}))
raise SystemExit(code)
