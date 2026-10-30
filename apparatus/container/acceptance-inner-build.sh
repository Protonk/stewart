#!/bin/sh
# Acceptance-suite builds, inside stewart-toolchain:1-<arch> with no network.
# Inputs: /in/source.tar (git archive of HEAD), /vendor (the vendored crates,
# read-only). Output: /out.
#
# Builds three binaries from the same sources, each in its own target folder:
#   stewart        release, <arch>-unknown-linux-musl
#   stewart-test   release profile with --features fault-injection,sabotage (musl)
#   stewart-glibc  release, <arch>-unknown-linux-gnu: the firing control for the
#                  static check, which must reject it
# and records the apparatus checks the host script evaluates:
#   static-<name>.exit        0 when the binary has no program interpreter and no
#                             NEEDED entries, 1 otherwise
#   cmp-release-test.exit     cmp's status (1 = the binaries differ)
#   strings-<name>-<VAR>.exit grep's status for each of the six test-only
#                             variable names (0 = present)
# Every step keeps its stdout, stderr and exit code. A failed required step stops.
set -u
step() {
    name=$1
    shift
    "$@" >"/out/$name.stdout" 2>"/out/$name.stderr" </dev/null
    rc=$?
    echo "$rc" >"/out/$name.exit"
    return "$rc"
}
must() { step "$@" || { echo "step $1 failed" >&2; exit 1; }; }
ARCH=$(uname -m)
MUSL="$ARCH-unknown-linux-musl"
GNU="$ARCH-unknown-linux-gnu"

must toolchain cat /toolchain-versions.txt
must network sh -c 'cat /proc/net/route; ls /sys/class/net'
must unpack sh -c 'mkdir -p /work && tar -xf /in/source.tar -C /work && cp -R /vendor /work/service/vendor'
must build-release sh -c "cd /work/service && CARGO_TARGET_DIR=/work/target-release cargo build --locked --offline --release --target $MUSL"
must build-test sh -c "cd /work/service && CARGO_TARGET_DIR=/work/target-test cargo build --locked --offline --release --features fault-injection,sabotage --target $MUSL"
step build-glibc sh -c "cd /work/service && CARGO_TARGET_DIR=/work/target-glibc cargo build --locked --offline --release --target $GNU"

must copy-release cp "/work/target-release/$MUSL/release/stewart" /out/stewart
# The test build is named stewart-test (INTERFACE Appendix C); accept either a
# dedicated stewart-test target or the stewart binary built with the features.
if [ -f "/work/target-test/$MUSL/release/stewart-test" ]; then
    must copy-test cp "/work/target-test/$MUSL/release/stewart-test" /out/stewart-test
else
    must copy-test cp "/work/target-test/$MUSL/release/stewart" /out/stewart-test
fi
[ -f "/work/target-glibc/$GNU/release/stewart" ] && step copy-glibc cp "/work/target-glibc/$GNU/release/stewart" /out/stewart-glibc

static_check() {
    readelf -lh "$2" >"/out/static-$1.readelf" 2>&1
    readelf -d "$2" >"/out/static-$1.dynamic" 2>&1
    if grep -q "program interpreter" "/out/static-$1.readelf" || grep -q "(NEEDED)" "/out/static-$1.dynamic"; then
        echo 1 >"/out/static-$1.exit"
    else
        echo 0 >"/out/static-$1.exit"
    fi
}
for name in stewart stewart-test stewart-glibc; do
    [ -f "/out/$name" ] && static_check "$name" "/out/$name"
done

cmp -s /out/stewart /out/stewart-test
echo $? >/out/cmp-release-test.exit
for name in stewart stewart-test; do
    for var in STEWART_TEST_FAULT STEWART_TEST_SABOTAGE STEWART_TEST_FAULT_DIR STEWART_TEST_TLS_ROOT \
        STEWART_TEST_PROVIDER_TIMEOUT STEWART_TEST_RETRY_DELAYS; do
        grep -a -F -q "$var" "/out/$name"
        echo $? >"/out/strings-$name-$var.exit"
    done
done
step sha256 sha256sum /out/stewart /out/stewart-test
step run-release /out/stewart help
step run-test /out/stewart-test help
exit 0
