#!/bin/sh
# Acceptance-suite driver run, inside the pinned python image with no network
# (loopback only: the fake provider listens on 127.0.0.1).
#   sh acceptance-inner-driver.sh GATE [KEEP_WORK]
# GATE: on (native architecture) or off. KEEP_WORK: failed (default) or all.
# Inputs: /in/source.tar (git archive of HEAD), /bin-in/stewart and
# /bin-in/stewart-test, /bin-in/stewart-local and /bin-in/stewart-local-variant
# (read-only). Output: /out.
#
# Starts as root only to record the environment, create an unprivileged user
# (uid 1000) and its work folder on the container's own disk, then, as that user,
# runs the driver's --self-test (no binary needed) and the whole driver with
# --network-isolated --require-all-controls. Archives, folders and homes live
# under /work/tmp. Copy independent evidence to /out/evidence. Export remaining
# working files only after failure or when full retention was requested.
# The host retains this container too, including if export fails.
set -u
GATE=${1:-off}
KEEP_WORK=${2:-failed}
case "$KEEP_WORK" in failed|all) ;; *) echo "KEEP_WORK must be failed or all" >&2; exit 2 ;; esac
rec() {
    name=$1
    shift
    "$@" >"/out/$name.stdout" 2>"/out/$name.stderr" </dev/null
    rc=$?
    echo "$rc" >"/out/$name.exit"
    return "$rc"
}
rec env-id id
rec env-uname uname -a
rec env-os cat /etc/os-release
rec env-python python3 -VV
rec env-mountinfo cat /proc/self/mountinfo
rec env-network sh -c 'cat /proc/net/route; ls /sys/class/net'
rec env-binaries sha256sum /bin-in/stewart /bin-in/stewart-test /bin-in/stewart-local /bin-in/stewart-local-variant
rec env-cpuinfo sh -c 'head -20 /proc/cpuinfo'
# Under Rosetta (an x86_64 kernel on a VirtualApple CPU) the emulator writes its
# own translation cache to $HOME/.cache/rosetta; the driver records that as an
# emulator artifact rather than as a write by Stewart.
EMULATION=""
if [ "$(uname -m)" = x86_64 ] && grep -q VirtualApple /proc/cpuinfo 2>/dev/null; then
    EMULATION="--emulator-home-artifact .cache/rosetta"
fi
echo "${EMULATION:-none}" >/out/emulation.txt

mkdir -p /work/driver /work/tmp /work/run || exit 1
# The driver is several modules plus test data (apparatus/driver/); its self-test
# also reads docs/QUESTION-FORMS.md and docs/INTERFACE.md. Extract all of them.
tar -xf /in/source.tar -C /work/driver apparatus/driver docs || exit 1
if ! id -u stewartdrv >/dev/null 2>&1; then
    if command -v useradd >/dev/null 2>&1; then
        rec user-add useradd -u 1000 -M -d /work/tmp -s /bin/sh stewartdrv
    else
        rec user-add adduser -D -H -u 1000 -h /work/tmp -s /bin/sh stewartdrv
    fi
fi
chown 1000:1000 /work/tmp /work/run
chmod 0755 /work /work/driver
rec env-work-mount sh -c 'stat -f -c "%T" /work/tmp 2>/dev/null || true; grep -E " / | /work" /proc/self/mountinfo'

if command -v setpriv >/dev/null 2>&1; then
    set -- setpriv --reuid=1000 --regid=1000 --clear-groups
elif command -v su-exec >/dev/null 2>&1; then
    set -- su-exec 1000:1000
else
    echo "no setpriv or su-exec to drop privileges" >/out/drop.stderr
    echo 2 >/out/driver.exit
    exit 2
fi
rec env-unprivileged "$@" id
rec env-loopback cat /proc/net/if_inet6 /proc/net/dev
rec selftest "$@" env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work/tmp \
    python3 -I -B /work/driver/apparatus/driver/stewart_driver.py --self-test
rec driver "$@" env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work/tmp \
    python3 -I -B /work/driver/apparatus/driver/stewart_driver.py \
    --binary /bin-in/stewart --test-binary /bin-in/stewart-test \
    --evidence /work/run/evidence --work /work/tmp --timing-gate "$GATE" \
    --network-isolated --require-all-controls --keep-work "$KEEP_WORK" $EMULATION
final_rc=$(cat /out/driver.exit)
[ "$(cat /out/selftest.exit)" = 0 ] || final_rc=1
rec evidence-copy cp -R /work/run/evidence /out/evidence || final_rc=1
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
[ "$runtime_rc" -eq 0 ] || final_rc=1
echo "$final_rc" >/out/driver-final.exit
exit "$final_rc"
