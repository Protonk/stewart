# Environment and privilege drop shared by the two driver containers.
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
rec env-machine uname -m
rec env-os cat /etc/os-release
rec env-python python3 -VV
rec env-mountinfo cat /proc/self/mountinfo
rec env-network sh -c 'cat /proc/net/route; ls /sys/class/net'
rec env-binaries sha256sum /bin-in/stewart*
rec env-cpuinfo sh -c 'head -20 /proc/cpuinfo'
# The translated Python process keeps the VZ interpreter open. Verify the
# interpreter and CPU marker before exempting the observed empty cache directories.
rec env-interpreter python3 -I -B -c '
import os
try:
    print(os.readlink("/proc/self/fd/4"))
except FileNotFoundError:
    print("absent")
'
EMULATION=""
if [ "${STEWART_EXPECT_ROSETTA:-0}" = 1 ]; then
    [ "$(uname -m)" = x86_64 ] && grep -q VirtualApple /proc/cpuinfo &&
        grep -Fxq /mnt/lima-rosetta/rosetta /out/env-interpreter.stdout || {
            echo "missing expected Rosetta interpreter or CPU marker" >&2
            exit 1
        }
    EMULATION="--emulator-home-artifact .cache/rosetta"
fi
echo "${EMULATION:-none}" >/out/emulation.txt

mkdir -p /work/driver /work/tmp /work/run || exit 1
# The driver is several modules plus test data (apparatus/driver/); its self-test
# also reads docs/, and its walkthrough cases read examples/. Extract all of them.
tar -xf /in/source.tar -C /work/driver apparatus/driver docs examples || exit 1
if ! id -u stewartdrv >/dev/null 2>&1; then
    if command -v useradd >/dev/null 2>&1; then
        rec user-add useradd -u 1000 -M -d /work/tmp -s /bin/sh stewartdrv
    else
        rec user-add adduser -D -H -u 1000 -h /work/tmp -s /bin/sh stewartdrv
    fi
fi
chown 1000:1000 /work/tmp /work/run
chmod 0755 /work /work/driver
rec env-work-mount sh -c 'findmnt --target /work/run && test "$(findmnt -n -o FSTYPE -T /work/run)" = ext4' || exit 1

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
