#!/bin/sh
# Toolchain images, vendored crates and a reproducible static build for the
# Stewart Rust service (Apple `container` 1.6.1). Run it on the host from your
# own shell: it needs the container services, which a sandboxed command shell
# may not be able to reach.
#
#   sh apparatus/step2.sh [EVIDENCE_DIR]
#
# EVIDENCE_DIR, an absolute path, must not exist yet; it defaults to
# .scratch/apparatus-01 in the repository, which therefore serves only once.
# Footprint: writes under EVIDENCE_DIR, and creates service/vendor from
# service/Cargo.lock (refused if it exists). Pulls the pinned rust and alpine
# images for linux/arm64 and linux/amd64, builds the toolchain images
# stewart-toolchain:1-arm64 and stewart-toolchain:1-amd64, and runs containers
# with --rm. The network is used only for pulls, toolchain image builds and
# crate vendoring; every build and run of the binary has no network. Nothing on
# the host is deleted.
set -u

REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$REPO/.scratch/apparatus-01}
RUST=docker.io/library/rust@sha256:81015672d6939b0265f09adf96d5de125482bb1330106076956b0518e74edc90
ALPINE=docker.io/library/alpine@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
TAG=stewart-toolchain:1
PLATFORMS="arm64 amd64"

[ -e "$OUT" ] && { echo "refusing: $OUT exists; each run needs a new evidence folder" >&2; exit 2; }
[ -e "$REPO/service/vendor" ] && { echo "refusing: $REPO/service/vendor exists" >&2; exit 2; }
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

note "step2 apparatus check start; repository $REPO"
hstep version container --version
grep -q 'version 1\.6\.1 ' "$OUT/host/version.stdout" || stop_here "container is not version 1.6.1"
hstep system-status container system status || stop_here "container services are not running"
hstep help-build container build --help || stop_here "container build is unavailable"
for flag in --platform --tag --file; do
    grep -qE -- "(^|[[:space:],])$flag([[:space:],=]|\$)" "$OUT/host/help-build.stdout" \
        || stop_here "container build lacks $flag"
done

# Source identity: a git archive of HEAD, so the build cannot see uncommitted files.
mkdir -p "$OUT/staging"
hstep commit git -C "$REPO" rev-parse HEAD || stop_here "not a git checkout"
hstep worktree git -C "$REPO" status --porcelain -- service apparatus
[ -s "$OUT/host/worktree.stdout" ] && note "note: service/ or apparatus/ differ from HEAD; the build uses HEAD"
hstep archive git -C "$REPO" archive --format=tar -o "$OUT/staging/source.tar" HEAD service apparatus \
    || stop_here "git archive failed"
cp "$OUT/host/commit.stdout" "$OUT/staging/COMMIT"
shasum -a 256 "$OUT/staging/source.tar" >"$OUT/host/source.sha256"

# Phase A (network): images, toolchains and vendored crates.
for p in $PLATFORMS; do
    hstep "pull-rust-$p" container image pull --platform "linux/$p" "$RUST" || stop_here "pull rust $p"
    hstep "pull-alpine-$p" container image pull --platform "linux/$p" "$ALPINE" || stop_here "pull alpine $p"
done
for p in $PLATFORMS; do
    hstep "toolchain-$p" container build --platform "linux/$p" --tag "$TAG-$p" \
        --file "$REPO/apparatus/container/Containerfile" "$REPO/apparatus/container" \
        || stop_here "toolchain image build for $p"
    hstep "toolchain-inspect-$p" container image inspect "$TAG-$p"
done
mkdir -p "$OUT/vendor-out"
hstep vendor container run --rm --platform linux/arm64 \
    --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
    --mount "type=bind,source=$OUT/vendor-out,target=/out" \
    "$TAG-arm64" sh -c 'mkdir /work && tar -xf /in/source.tar -C /work && cd /work/service && cargo vendor --locked --versioned-dirs /out/vendor >/out/vendor-config.toml' \
    || stop_here "cargo vendor"
(cd "$OUT/vendor-out" && find vendor -type f -exec shasum -a 256 {} + | LC_ALL=C sort) >"$OUT/host/vendor.sha256"
cp -R "$OUT/vendor-out/vendor" "$REPO/service/vendor" || stop_here "copy vendor into service/"

# Phase B (no network): two independent builds per platform, then a foreign-userland run.
for p in $PLATFORMS; do
    for i in 1 2; do
        b="build-$p-$i"
        mkdir -p "$OUT/$b"
        hstep "$b" container run --rm --network none --init --cpus 4 --memory 4G --platform "linux/$p" \
            --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
            --mount "type=bind,source=$OUT/vendor-out,target=/vendor,readonly" \
            --mount "type=bind,source=$OUT/$b,target=/out" \
            "$TAG-$p" sh -c 'mkdir -p /tmp/s && tar -xf /in/source.tar -C /tmp/s apparatus/container/inner-build.sh && sh /tmp/s/apparatus/container/inner-build.sh' \
            || fail "$b"
    done
    a="$OUT/build-$p-1/stewart"
    c="$OUT/build-$p-2/stewart"
    if [ -f "$a" ] && [ -f "$c" ] && cmp -s "$a" "$c"; then
        note "reproducible $p: identical binaries"
        echo same >"$OUT/host/reproducible-$p"
    else
        fail "reproducible $p: binaries differ or are missing"
        echo differ >"$OUT/host/reproducible-$p"
    fi
    if [ -f "$a" ]; then
        mkdir -p "$OUT/alpine-$p"
        cp "$a" "$OUT/alpine-$p/stewart"
        # `help` exits 0 and involves no archive (INTERFACE 1.6, 5.9); with no
        # command stewart is a usage error and exits 2.
        hstep "alpine-run-$p" container run --rm --network none --platform "linux/$p" \
            --mount "type=bind,source=$OUT/alpine-$p,target=/b,readonly" \
            "$ALPINE" /b/stewart help || fail "alpine-run-$p"
    fi
done

shasum -a 256 "$OUT"/build-*/stewart >"$OUT/host/binaries.sha256" 2>/dev/null
printf 'done %s failures=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$FAILURES" >"$OUT/host/DONE"
note "finished with failures=$FAILURES; evidence in $OUT"
[ "$FAILURES" -eq 0 ]
