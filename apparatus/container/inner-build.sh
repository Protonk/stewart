#!/bin/sh
# Runs inside a toolchain container with no network. Inputs: /in/source.tar (a
# git archive of the repository), /vendor/vendor (vendored crates). Output: /out.
# Each step's stdout, stderr and exit code are kept; a failed step stops the build.
set -u
step() {
    name=$1
    shift
    "$@" >"/out/$name.stdout" 2>"/out/$name.stderr" </dev/null
    rc=$?
    echo "$rc" >"/out/$name.exit"
    [ "$rc" -eq 0 ] || { echo "step $name failed with exit $rc" >&2; exit 1; }
}
TARGET="$(uname -m)-unknown-linux-musl"
step toolchain cat /toolchain-versions.txt
step network sh -c 'cat /proc/net/route; ls /sys/class/net'
step unpack sh -c 'mkdir -p /work && tar -xf /in/source.tar -C /work && cp -R /vendor/vendor /work/service/vendor'
step build sh -c "cd /work/service && cargo build --locked --offline --release --target $TARGET"
step copy cp "/work/service/target/$TARGET/release/stewart" /out/stewart
step sha256 sha256sum /out/stewart
step readelf readelf -lh /out/stewart
step static sh -c '! grep -q "program interpreter" /out/readelf.stdout'
step run /out/stewart help
