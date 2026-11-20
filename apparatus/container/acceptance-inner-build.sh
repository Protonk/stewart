#!/bin/sh
# Build the selected Linux suite's binaries offline from /in/source.tar and /vendor.
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
if [ "$suite" = acceptance ]; then
    # The driver's apparatus.identity case owns the test-only names and distinct
    # builds; this step owns static linkage, with a dynamic ELF as its control.
    build test stewart-test release --features fault-injection,sabotage
    echo 'int main(void) { return 0; }' >/work/dynamic-control.c || exit 1
    must build-dynamic-control cc /work/dynamic-control.c -o /out/dynamic-control
    for binary in stewart stewart-test dynamic-control; do
        static_check "$binary"
    done
    step run-release /out/stewart help
    step run-test /out/stewart-test help
else
    # Each listed marker must be absent from the release and present in both
    # development writers, which are the firing controls for the absence check.
    build local stewart-local release --features claude-code
    build local-variant stewart-local-variant release --features claude-code,fault-injection
    must marker-list cp /work/apparatus/claude-code-markers.txt /out/claude-code-markers.txt
    markers=/work/apparatus/check-build-markers.sh
    step markers-release sh "$markers" absent /out/claude-code-markers.txt /out/stewart
    for kind in local local-variant; do
        step "markers-$kind" sh "$markers" present /out/claude-code-markers.txt "/out/stewart-$kind"
    done
fi
exit 0
