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
