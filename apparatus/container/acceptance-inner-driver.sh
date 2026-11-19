#!/bin/sh
# Run the release driver in the offline Linux container.
set -u
KEEP_WORK=${1:-failed}
case "$KEEP_WORK" in failed|all) ;; *) exit 2 ;; esac
. "$(dirname "$0")/driver-env.sh"
rec env-component-source-mount sh -c 'stat -f -c "%T" /component-source-work; grep " /component-source-work " /proc/self/mountinfo'
rec selftest "$@" env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work/tmp \
    python3 -I -B /work/driver/apparatus/driver/stewart_driver.py --self-test
rec driver "$@" env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work/tmp \
    python3 -I -B /work/driver/apparatus/driver/stewart_driver.py \
    --binary /bin-in/stewart --test-binary /bin-in/stewart-test \
    --evidence /work/run/evidence --work /work/tmp \
    --component-source-work /component-source-work \
    --network-isolated --require-all-controls --keep-work "$KEEP_WORK" $EMULATION
final_rc=$(cat /out/driver.exit)
[ "$(cat /out/selftest.exit)" = 0 ] || final_rc=1
rec driver-complete python3 -I -B -c '
import json, sys
with open("/work/run/evidence/RESULT.json", "rb") as source:
    report = json.load(source)
counts = report["counts"]["cases"]
complete = (counts["selected"] > 0 and counts["selected"] == counts["passed"]
            and counts["failed"] == counts["skipped"] == 0)
print(json.dumps(counts, sort_keys=True))
sys.exit(0 if complete else 1)
' || final_rc=1
rec evidence-copy cp -R /work/run/evidence /out/evidence || final_rc=1
# The independent witness survives either policy. A failed export keeps the
# original container available for review, including special Linux files.
retain_work() {
    printf '%s\n' "$KEEP_WORK" >/out/keep-work.txt || return 1
    if [ "$KEEP_WORK" = all ] || [ "$final_rc" -ne 0 ]; then
        printf 'working files retained for review\n' >/out/retention.txt || return 1
        rec retention-start date -u +%Y-%m-%dT%H:%M:%SZ || return 1
        rec retention-archive tar -cpf /out/work.tar -C /work tmp || return 1
        rec retention-list tar -tf /out/work.tar || return 1
        rec retention-sha256 sha256sum /out/work.tar || return 1
        rec retention-end date -u +%Y-%m-%dT%H:%M:%SZ || return 1
    else
        printf 'passed; no working archive requested\n' >/out/retention.txt || return 1
    fi
}
retain_work
retention_rc=$?
printf '%s\n' "$retention_rc" >/out/retention.exit
[ "$retention_rc" -eq 0 ] || final_rc=1
echo "$final_rc" >/out/driver-final.exit
exit "$final_rc"
