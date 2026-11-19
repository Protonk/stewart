#!/bin/sh
# Build the selected Linux suite's binaries offline from /in/source.tar and /vendor.
# The runtime suite uses a featureless release as its negative control.
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

must toolchain cat /toolchain-versions.txt
must network sh -c 'cat /proc/net/route; ls /sys/class/net'
must unpack sh -c 'mkdir -p /work && tar -xf /in/source.tar -C /work && cp -R /vendor /work/service/vendor'
case "$1" in acceptance|runtime) suite=$1 ;; *) exit 2 ;; esac

build() {
    label=$1
    binary=$2
    profile=$3
    shift 3
    if [ "$profile" = release ]; then set -- --release "$@"; fi
    must "build-$label" sh -c 'cd /work/service && cargo build --locked --offline --target "$0" "$@"' "$MUSL" "$@"
    must "copy-$label" cp "/work/service/target/$MUSL/$profile/stewart" "/out/$binary"
}

static_check() {
    binary=$1
    if ! readelf -lh "/out/$binary" >"/out/static-$binary.readelf" 2>&1 ||
       ! readelf -d "/out/$binary" >"/out/static-$binary.dynamic" 2>&1; then
        echo 2 >"/out/static-$binary.exit"
    elif grep -q 'program interpreter' "/out/static-$binary.readelf" || grep -q '(NEEDED)' "/out/static-$binary.dynamic"; then
        echo 1 >"/out/static-$binary.exit"
    else
        echo 0 >"/out/static-$binary.exit"
    fi
}

build release stewart release
must marker-list cp /work/apparatus/claude-code-markers.txt /out/claude-code-markers.txt
markers=/work/apparatus/check-build-markers.sh
step markers-release sh "$markers" absent /out/claude-code-markers.txt /out/stewart
if [ "$suite" = acceptance ]; then
    build test stewart-test release --features fault-injection,sabotage
    set -- stewart stewart-test
    # A real dynamically linked ELF exercises the same readelf check as both writers.
    echo 'int main(void) { return 0; }' >/work/dynamic-control.c || exit 1
    must build-dynamic-control cc /work/dynamic-control.c -o /out/dynamic-control
    static_check dynamic-control
    step cmp-release-test cmp -s /out/stewart /out/stewart-test
    step markers-test sh "$markers" absent /out/claude-code-markers.txt /out/stewart-test
    for writer do
        for var in STEWART_TEST_FAULT STEWART_TEST_SABOTAGE STEWART_TEST_FAULT_DIR STEWART_TEST_TLS_ROOT \
            STEWART_TEST_PROVIDER_TIMEOUT STEWART_TEST_RETRY_DELAYS; do
            step "strings-$writer-$var" grep -a -F -q "$var" "/out/$writer"
        done
    done
else
    build local stewart-local release --features claude-code
    build local-variant stewart-local-variant debug --features claude-code,fault-injection
    set -- stewart stewart-local stewart-local-variant
    step cmp-local-variant cmp -s /out/stewart-local /out/stewart-local-variant
    for kind in local local-variant; do
        step "markers-$kind" sh "$markers" present /out/claude-code-markers.txt "/out/stewart-$kind"
    done
fi
for writer do
    static_check "$writer"
    case "$writer" in stewart) label=release ;; *) label=${writer#stewart-} ;; esac
    step "run-$label" "/out/$writer" help
done
exit 0
