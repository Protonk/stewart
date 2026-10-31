#!/bin/sh
# Acceptance-suite driver run, inside the pinned python image with no network
# (loopback only: the fake provider listens on 127.0.0.1).
#   sh acceptance-inner-driver.sh GATE   GATE: on (native architecture) or off
# Inputs: /in/source.tar (git archive of HEAD), /bin-in/stewart and
# /bin-in/stewart-test (read-only). Output: /out.
#
# Starts as root only to record the environment, create an unprivileged user
# (uid 1000) and its work folder on the container's own disk, then, as that user,
# runs the driver's --self-test (no binary needed) and the whole driver with
# --network-isolated --require-all-controls --keep-work all. Archives, folders
# and homes live under /work/tmp. After the driver returns, copy its independent
# evidence to /out/evidence and archive the work in /out/work.tar for review.
# The host retains this container too, including if export fails.
set -u
GATE=${1:-off}
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
rec env-binaries sha256sum /bin-in/stewart /bin-in/stewart-test
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
    --network-isolated --require-all-controls --keep-work all $EMULATION
final_rc=$(cat /out/driver.exit)
[ "$(cat /out/selftest.exit)" = 0 ] || final_rc=1
rec evidence-copy cp -R /work/run/evidence /out/evidence || final_rc=1
# Observe after the driver has returned. Keep the independent witness separate
# from the work archive. tar preserves Linux names, modes and links inside one
# regular host file; special-file warnings remain in retention-archive.stderr.
# Original work remains in the retained container even on export failure.
rec retention-start date -u +%Y-%m-%dT%H:%M:%SZ || final_rc=1
rec retention-archive tar -cpf /out/work.tar -C /work tmp || final_rc=1
rec retention-list tar -tf /out/work.tar || final_rc=1
rec retention-sha256 sha256sum /out/work.tar || final_rc=1
rec retention-end date -u +%Y-%m-%dT%H:%M:%SZ || final_rc=1
echo "$final_rc" >/out/driver-final.exit
exit "$final_rc"
