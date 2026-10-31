#!/bin/sh
# The scripted acceptance tier for the Stewart Rust service, as one container
# suite (Apple `container` 1.6.1): every case of the independent driver, against
# a fake provider, on Linux aarch64 (native) and x86_64 (Rosetta), offline.
# Run it on the host from your own shell: it needs the container services, which
# a sandboxed command shell may not be able to reach.
#
#   sh apparatus/acceptance.sh EVIDENCE_DIR
#
# EVIDENCE_DIR is required and must not exist yet, so each run gets its own:
# give a new folder directly under .scratch/ in the repository, as an absolute
# path. Without it the script prints its usage and exits 2.
# Needs the images stewart-toolchain:1-arm64 and stewart-toolchain:1-amd64 and
# service/vendor, which apparatus/step2.sh produces.
# Footprint: writes under EVIDENCE_DIR only. Pulls the pinned python image for
# linux/arm64 and linux/amd64; that pull is the only network use. Every build
# and every driver run is offline (--network none) in a container removed on
# exit (--rm). Nothing on the host is deleted.
#
# For each architecture it:
#   1. builds, from a git archive of HEAD plus service/vendor, the release binary,
#      the test binary (--features fault-injection,sabotage, its own target folder)
#      and a glibc build used only as a control;
#   2. checks the apparatus with firing controls: both musl binaries pass the
#      static check and the glibc build fails it; the release and test binaries
#      differ under cmp; the release binary lacks all six test-only variable
#      names of INTERFACE Appendix C while the test binary contains them;
#   3. in the pinned python image as an unprivileged user, with no network
#      (loopback only), binaries mounted read-only and archives and homes on the
#      container's own disk: runs the driver's --self-test, then every case with
#      --network-isolated --require-all-controls (every Appendix C.2 sabotage
#      control assigned and fired). The timing gates are on only for the host's
#      native architecture; emulated timings are reported, not gated.
# host/DONE reports failures=N; host/SUMMARY collects the self-test and driver counts.
set -u

# The evidence folder is required; nothing else runs before this check.
[ -n "${1:-}" ] || { echo "usage: sh apparatus/acceptance.sh EVIDENCE_DIR (a new folder directly under .scratch/, as an absolute path)" >&2; exit 2; }
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=$1
PYTHON=docker.io/library/python@sha256:2c90493710bd462e097441e60b0218430d8f7e2b46779bfca3742b2efd386feb
TAG=stewart-toolchain:1
PLATFORMS="arm64 amd64"
# The test-only variable names of INTERFACE Appendix C: only the test build may contain them.
TEST_VARS="STEWART_TEST_FAULT STEWART_TEST_SABOTAGE STEWART_TEST_FAULT_DIR STEWART_TEST_TLS_ROOT STEWART_TEST_PROVIDER_TIMEOUT STEWART_TEST_RETRY_DELAYS"
case "$(uname -m)" in
    arm64 | aarch64) NATIVE=arm64 ;;
    x86_64 | amd64) NATIVE=amd64 ;;
    *) NATIVE=none ;;
esac

[ -e "$OUT" ] && { echo "refusing: $OUT exists; each run needs a new evidence folder" >&2; exit 2; }
[ -d "$REPO/service/vendor" ] || { echo "refusing: $REPO/service/vendor is missing; run apparatus/step2.sh first" >&2; exit 2; }
mkdir -p "$OUT/host" || exit 2
LOG="$OUT/host/driver.log"
FAILURES=0

note() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG" >&2; }
hstep() {
    name=$1
    shift
    note "begin $name: $*"
    "$@" >"$OUT/host/$name.stdout" 2>"$OUT/host/$name.stderr" </dev/null
    rc=$?
    echo "$rc" >"$OUT/host/$name.exit"
    note "end $name exit=$rc"
    return "$rc"
}
fail() { FAILURES=$((FAILURES + 1)); note "FAILED: $*"; }
stop_here() {
    note "STOP: $*"
    printf 'stopped %s failures=%s: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$FAILURES" "$*" >"$OUT/host/DONE"
    exit 1
}
# expect FILE VALUE LABEL: the recorded value must equal VALUE.
expect() {
    if [ -f "$1" ] && [ "$(cat "$1")" = "$2" ]; then
        note "ok: $3"
    else
        fail "$3 (expected $2, found $(cat "$1" 2>/dev/null || echo missing) in $1)"
    fi
}

note "acceptance suite start; repository $REPO; native architecture $NATIVE"
hstep version container --version
grep -q 'version 1\.6\.1 ' "$OUT/host/version.stdout" || stop_here "container is not version 1.6.1"
hstep system-status container system status || stop_here "container services are not running"
hstep help-run container run --help || stop_here "container run is unavailable"
hstep host-uname uname -a
hstep host-sw-vers sw_vers
for p in $PLATFORMS; do
    hstep "toolchain-inspect-$p" container image inspect "$TAG-$p" \
        || stop_here "image $TAG-$p is missing; run apparatus/step2.sh first"
done

# Source identity: a git archive of HEAD; uncommitted files are not built or run.
mkdir -p "$OUT/staging"
hstep commit git -C "$REPO" rev-parse HEAD || stop_here "not a git checkout"
hstep worktree git -C "$REPO" status --porcelain -- service apparatus docs
[ -s "$OUT/host/worktree.stdout" ] && note "note: service/, apparatus/ or docs/ differ from HEAD; the suite uses HEAD"
# docs/ goes in too: the driver's self-test compares its pinned texts with QUESTION-FORMS.
hstep archive git -C "$REPO" archive --format=tar -o "$OUT/staging/source.tar" HEAD service apparatus docs \
    || stop_here "git archive failed"
cp "$OUT/host/commit.stdout" "$OUT/staging/COMMIT"
shasum -a 256 "$OUT/staging/source.tar" >"$OUT/host/source.sha256"
(cd "$REPO/service" && find vendor -type f -exec shasum -a 256 {} + | LC_ALL=C sort) >"$OUT/host/vendor.sha256"

# The only network step: the pinned python image for both architectures.
for p in $PLATFORMS; do
    hstep "pull-python-$p" container image pull --platform "linux/$p" "$PYTHON" || stop_here "pull python $p"
done
hstep python-inspect container image inspect "$PYTHON"

for p in $PLATFORMS; do
    b="build-$p"
    mkdir -p "$OUT/$b"
    hstep "$b" container run --rm --network none --init --cpus 4 --memory 4G --platform "linux/$p" \
        --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
        --mount "type=bind,source=$REPO/service/vendor,target=/vendor,readonly" \
        --mount "type=bind,source=$OUT/$b,target=/out" \
        "$TAG-$p" sh -c 'mkdir -p /tmp/s && tar -xf /in/source.tar -C /tmp/s apparatus/container/acceptance-inner-build.sh && sh /tmp/s/apparatus/container/acceptance-inner-build.sh' \
        || { fail "$b"; continue; }
    expect "$OUT/$b/build-release.exit" 0 "$p: release build"
    expect "$OUT/$b/build-test.exit" 0 "$p: test build"
    expect "$OUT/$b/static-stewart.exit" 0 "$p: release binary is static"
    expect "$OUT/$b/static-stewart-test.exit" 0 "$p: test binary is static"
    expect "$OUT/$b/build-glibc.exit" 0 "$p: glibc control builds"
    expect "$OUT/$b/static-stewart-glibc.exit" 1 "$p: control fired: the static check rejects the glibc build"
    expect "$OUT/$b/cmp-release-test.exit" 1 "$p: control fired: cmp distinguishes the release and test binaries"
    for var in $TEST_VARS; do
        expect "$OUT/$b/strings-stewart-$var.exit" 1 "$p: release binary lacks $var"
        expect "$OUT/$b/strings-stewart-test-$var.exit" 0 "$p: control fired: the test binary contains $var"
    done
    expect "$OUT/$b/run-release.exit" 0 "$p: release binary runs (help)"
    if [ ! -f "$OUT/$b/stewart" ] || [ ! -f "$OUT/$b/stewart-test" ]; then
        fail "$p: binaries missing; driver not run"
        continue
    fi
    mkdir -p "$OUT/bin-$p"
    cp "$OUT/$b/stewart" "$OUT/$b/stewart-test" "$OUT/bin-$p/"
    gate=off
    [ "$p" = "$NATIVE" ] && gate=on
    d="driver-$p"
    mkdir -p "$OUT/$d"
    hstep "$d" container run --rm --network none --init --cpus 4 --memory 4G --platform "linux/$p" \
        --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
        --mount "type=bind,source=$OUT/bin-$p,target=/bin-in,readonly" \
        --mount "type=bind,source=$OUT/$d,target=/out" \
        "$PYTHON" sh -c "mkdir -p /tmp/s && tar -xf /in/source.tar -C /tmp/s apparatus/container/acceptance-inner-driver.sh && sh /tmp/s/apparatus/container/acceptance-inner-driver.sh $gate" \
        || fail "$d: the self-test or the driver reported failures or broken checks (see $OUT/$d/)"
    expect "$OUT/$d/selftest.exit" 0 "$p: driver self-test"
    {
        echo "== $p (timing gate $gate) =="
        tail -1 "$OUT/$d/selftest.stdout" 2>/dev/null
        sed -n '/^## Counts/,/^## Timing gate/p' "$OUT/$d/evidence/RESULTS.md" 2>/dev/null | sed '$d'
        echo "driver exit: $(cat "$OUT/$d/driver-final.exit" 2>/dev/null || echo missing)"
    } >>"$OUT/host/SUMMARY"
done

shasum -a 256 "$OUT"/build-*/stewart* >"$OUT/host/binaries.sha256" 2>/dev/null
printf 'done %s failures=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$FAILURES" >"$OUT/host/DONE"
note "finished with failures=$FAILURES; evidence in $OUT"
[ "$FAILURES" -eq 0 ]
