# Common host setup for the offline Linux release and runtime suites.
PYTHON=docker.io/library/python@sha256:2c90493710bd462e097441e60b0218430d8f7e2b46779bfca3742b2efd386feb
TAG=localhost/stewart-toolchain:1
PLATFORMS="arm64 amd64"
case "$(uname -m)" in
    arm64 | aarch64) NATIVE=arm64 ;;
    x86_64 | amd64) NATIVE=amd64 ;;
    *) NATIVE=none ;;
esac

[ -e "$OUT" ] && { echo "refusing: $OUT exists; each run needs a new evidence folder" >&2; exit 2; }
[ -d "$REPO/service/vendor" ] || { echo "refusing: $REPO/service/vendor is missing; run apparatus/step2.sh first" >&2; exit 2; }
mkdir -p "$(dirname "$OUT")" && mkdir -m 0700 "$OUT" && mkdir "$OUT/host" || exit 2
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

note "$SUITE suite start; repository $REPO; native architecture $NATIVE"
note "working-file retention: $KEEP_WORK; independent evidence retained through review"
. "$REPO/apparatus/container/podman-images.sh"
podman_host || stop_here "need rootless Podman 5 on cgroup v2"
hstep host-uname uname -a
hstep host-os cat /etc/os-release
for p in $PLATFORMS; do
    toolchain_identity "$p" || stop_here "need the toolchain image for $p from step2.sh"
done

# Source identity: a git archive of HEAD; uncommitted files are not built or run.
mkdir -p "$OUT/staging"
hstep commit git -C "$REPO" rev-parse HEAD || stop_here "not a git checkout"
hstep worktree git -C "$REPO" status --porcelain -- service apparatus docs examples
[ -s "$OUT/host/worktree.stdout" ] && note "note: service/, apparatus/, docs/ or examples/ differ from HEAD; the suite uses HEAD"
# docs/ and examples/ go in too: the driver's self-test compares its pinned texts
# with them, and its walkthrough cases run the documented commands.
hstep archive git -C "$REPO" archive --format=tar -o "$OUT/staging/source.tar" HEAD service apparatus docs examples \
    || stop_here "git archive failed"
cp "$OUT/host/commit.stdout" "$OUT/staging/COMMIT"
sha256sum "$OUT/staging/source.tar" >"$OUT/host/source.sha256"
(cd "$REPO/service" && find vendor -type f -exec sha256sum {} + | LC_ALL=C sort) >"$OUT/host/vendor.sha256"

# The only network step: the pinned python image for both architectures.
image_index python "$PYTHON" || stop_here "resolve or pull the pinned driver images"

build_arch() {
    b="build-$p"
    mkdir -p "$OUT/$b"
    hstep "$b" podman run --pull=never --rm --network none --init --cpus 4 --memory 4G --platform "linux/$p" \
        --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
        --mount "type=bind,source=$REPO/service/vendor,target=/vendor,readonly" \
        --mount "type=bind,source=$OUT/$b,target=/out" \
        "$(cat "$OUT/host/toolchain-$p.id")" sh -c 'mkdir -p /tmp/s && tar -xf /in/source.tar -C /tmp/s apparatus/container && sh /tmp/s/apparatus/container/acceptance-inner-build.sh "$1"' sh "$SUITE" \
        || { fail "$b"; return 1; }
}

run_driver() {
    d="driver-$p"
    mkdir -p "$OUT/$d" "$OUT/bin-$p" || stop_here "$p: create driver workspace"
    chmod 0755 "$OUT/bin-$p" || stop_here "$p: make binary mount traversable"
    for binary do
        install -m 0555 "$OUT/$b/$binary" "$OUT/bin-$p/$binary" || { fail "$p: missing $binary"; return 1; }
    done
    set --
    if [ "$SUITE" = acceptance ]; then
        source_dir=/var/lib/stewart/fixtures/names/$(basename "$OUT")-$p
        [ "$(findmnt -n -o FSTYPE -T /var/lib/stewart/fixtures/names)" = vfat ] && mkdir "$source_dir" || stop_here "$p: need a fresh guest VFAT filename fixture"
        set -- --mount "type=bind,source=$source_dir,target=/component-source-work"
    fi
    driver_container="stewart-$SUITE-$p-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    printf '%s\n' "$driver_container" >"$OUT/host/$d.container"
    rosetta=0
    if [ "$p" = amd64 ] && [ "$NATIVE" = arm64 ]; then rosetta=1; fi
    hstep "$d" podman run --pull=never --name "$driver_container" --env "STEWART_EXPECT_ROSETTA=$rosetta" --network none --init --cpus 4 --memory 4G --platform "linux/$p" \
        --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
        --mount "type=bind,source=$OUT/bin-$p,target=/bin-in,readonly" \
        --mount "type=bind,source=$OUT/$d,target=/out" "$@" \
        --mount "type=volume,source=$driver_container-work,target=/work" \
        "$(cat "$OUT/host/python-$p.ref")" sh -c 'mkdir -p /tmp/s && tar -xf /in/source.tar -C /tmp/s apparatus/container && sh "/tmp/s/apparatus/container/$1" "$2"' sh "$DRIVER_SCRIPT" "$KEEP_WORK" \
        || fail "$d: the $SUITE driver reported a failure (see $OUT/$d/)"
    note "$p: driver container $driver_container retained until review"
}

finish_suite() {
    sha256sum "$OUT"/build-*/stewart* >"$OUT/host/binaries.sha256" 2>/dev/null
    printf 'done %s failures=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$FAILURES" >"$OUT/host/DONE"
    note "finished with failures=$FAILURES; evidence in $OUT"
    [ "$FAILURES" -eq 0 ]
}
