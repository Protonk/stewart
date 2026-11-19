# Common host setup for the offline Linux release and runtime suites.
PYTHON=docker.io/library/python@sha256:2c90493710bd462e097441e60b0218430d8f7e2b46779bfca3742b2efd386feb
TAG=stewart-toolchain:1
PLATFORMS="arm64 amd64"
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

note "$SUITE suite start; repository $REPO; native architecture $NATIVE"
note "working-file retention: $KEEP_WORK; independent evidence retained through review"
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


build_arch() {
    b="build-$p"
    mkdir -p "$OUT/$b"
    hstep "$b" container run --rm --network none --init --cpus 4 --memory 4G --platform "linux/$p" \
        --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
        --mount "type=bind,source=$REPO/service/vendor,target=/vendor,readonly" \
        --mount "type=bind,source=$OUT/$b,target=/out" \
        "$TAG-$p" sh -c 'mkdir -p /tmp/s && tar -xf /in/source.tar -C /tmp/s apparatus/container && sh /tmp/s/apparatus/container/acceptance-inner-build.sh "$1"' sh "$SUITE" \
        || { fail "$b"; return 1; }
}

run_driver() {
    d="driver-$p"
    mkdir -p "$OUT/$d" "$OUT/bin-$p" || stop_here "$p: create driver workspace"
    for binary do
        cp "$OUT/$b/$binary" "$OUT/bin-$p/" || { fail "$p: missing $binary"; return 1; }
    done
    set --
    if [ "$SUITE" = acceptance ]; then
        mkdir "$OUT/component-source-$p" && chmod 1777 "$OUT/component-source-$p" || stop_here "$p: prepare component source workspace"
        set -- --mount "type=bind,source=$OUT/component-source-$p,target=/component-source-work"
    fi
    driver_container="stewart-$SUITE-$p-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    printf '%s\n' "$driver_container" >"$OUT/host/$d.container"
    hstep "$d" container run --name "$driver_container" --network none --init --cpus 4 --memory 4G --platform "linux/$p" \
        --mount "type=bind,source=$OUT/staging,target=/in,readonly" \
        --mount "type=bind,source=$OUT/bin-$p,target=/bin-in,readonly" \
        --mount "type=bind,source=$OUT/$d,target=/out" "$@" \
        "$PYTHON" sh -c 'mkdir -p /tmp/s && tar -xf /in/source.tar -C /tmp/s apparatus/container && sh "/tmp/s/apparatus/container/$1" "$2"' sh "$DRIVER_SCRIPT" "$KEEP_WORK" \
        || fail "$d: the $SUITE driver reported a failure (see $OUT/$d/)"
    note "$p: driver container $driver_container retained until review"
}

finish_suite() {
    shasum -a 256 "$OUT"/build-*/stewart* >"$OUT/host/binaries.sha256" 2>/dev/null
    printf 'done %s failures=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$FAILURES" >"$OUT/host/DONE"
    note "finished with failures=$FAILURES; evidence in $OUT"
    [ "$FAILURES" -eq 0 ]
}
