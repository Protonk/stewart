#!/bin/sh
# Run and retain the independent synthetic adapter checks.
set -u
. "$(dirname "$0")/driver-env.sh"
# The development adapter is checked by its independent synthetic harness.
# This interpreter never launches Claude or authenticates with a provider.
rec runtime-selftest "$@" env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work/tmp \
    python3 -I -B /work/driver/apparatus/driver/claude_code.py --self-test
rec runtime-driver "$@" env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work/tmp \
    python3 -I -B /work/driver/apparatus/driver/claude_code.py \
    --binary /bin-in/stewart-local --release-binary /bin-in/stewart \
    --variant-binary /bin-in/stewart-local-variant --work /work/run/runtime
runtime_rc=$(cat /out/runtime-driver.exit)
[ "$(cat /out/runtime-selftest.exit)" = 0 ] || runtime_rc=1
rec runtime-complete python3 -I -B -c '
import json, sys
with open("/work/run/runtime/RESULT.json", "rb") as source:
    report = json.load(source)
counts = report["counts"]
complete = (not report["not_selected"] and counts["cases"] > 0
            and counts["cases"] == counts["passed"] and counts["failed"] == counts["skipped"] == 0
            and counts["checks"] == counts["checks_passed"] and counts["checks_failed"] == 0
            and counts["controls"] > 0 and counts["controls"] == counts["controls_fired"])
print(json.dumps(counts, sort_keys=True))
sys.exit(0 if complete else 1)
' || runtime_rc=1
copy_runtime_evidence() {
    mkdir /out/runtime-evidence || return 1
    for member in RESULT.json environment.json commands witness driver-snapshot; do
        cp -R "/work/run/runtime/$member" /out/runtime-evidence/ || return 1
    done
}
rec runtime-evidence-copy copy_runtime_evidence || runtime_rc=1
retain_runtime_work() {
    # Some independent launch markers live beside the synthetic executables,
    # outside witness/. Preserve the whole original runtime tree through review
    # rather than guess which fixture members a future inspection will need.
    rec runtime-retention-start date -u +%Y-%m-%dT%H:%M:%SZ || return 1
    rec runtime-retention-archive tar -cpf /out/runtime-work.tar -C /work/run runtime || return 1
    rec runtime-retention-list tar -tf /out/runtime-work.tar || return 1
    rec runtime-retention-sha256 sha256sum /out/runtime-work.tar || return 1
    rec runtime-retention-end date -u +%Y-%m-%dT%H:%M:%SZ || return 1
}
retain_runtime_work
runtime_retention_rc=$?
printf '%s\n' "$runtime_retention_rc" >/out/runtime-retention.exit
[ "$runtime_retention_rc" -eq 0 ] || runtime_rc=1
echo "$runtime_rc" >/out/driver-final.exit
exit "$runtime_rc"
