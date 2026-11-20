#!/bin/sh
# Synthetic Linux checks for the source-only adapter and its distinct development writer.
set -u

# The evidence folder is required; nothing else runs before this check.
[ -n "${1:-}" ] || { echo "usage: sh apparatus/runtime-acceptance.sh EVIDENCE_DIR (a new folder directly under .scratch/, as an absolute path)" >&2; exit 2; }
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=$1
[ "$#" -eq 1 ] || { echo "usage: sh apparatus/runtime-acceptance.sh EVIDENCE_DIR" >&2; exit 2; }
KEEP_WORK=all
SUITE=runtime
DRIVER_SCRIPT=runtime-inner-driver.sh
. "$REPO/apparatus/container/suite-host.sh"

for p in $PLATFORMS; do
    build_arch || continue
    expect "$OUT/$b/build-release.exit" 0 "$p: release build"
    expect "$OUT/$b/build-local.exit" 0 "$p: development build"
    expect "$OUT/$b/build-local-variant.exit" 0 "$p: second development build"
    expect "$OUT/$b/markers-release.exit" 0 "$p: release binary lacks all adapter markers"
    expect "$OUT/$b/markers-local.exit" 0 "$p: control fired: development binary contains every adapter marker"
    expect "$OUT/$b/markers-local-variant.exit" 0 "$p: control fired: second development binary contains every adapter marker"
    run_driver stewart stewart-local stewart-local-variant || continue
    expect "$OUT/$d/runtime-selftest.exit" 0 "$p: synthetic runtime self-test"
    expect "$OUT/$d/runtime-driver.exit" 0 "$p: synthetic runtime driver"
    expect "$OUT/$d/runtime-complete.exit" 0 "$p: synthetic runtime has no skipped or unselected cases"
    expect "$OUT/$d/runtime-evidence-copy.exit" 0 "$p: independent runtime evidence retained"
    expect "$OUT/$d/runtime-retention.exit" 0 "$p: runtime working-file retention completed"
    {
        echo "== $p =="
        tail -1 "$OUT/$d/runtime-selftest.stdout" 2>/dev/null
        tail -2 "$OUT/$d/runtime-driver.stdout" 2>/dev/null
    } >>"$OUT/host/SUMMARY"
done
finish_suite
