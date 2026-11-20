#!/bin/sh
# Offline release acceptance on Linux ARM64 and x86_64, including fault and sabotage controls.
set -u

# The evidence folder is required; nothing else runs before this check.
[ -n "${1:-}" ] || { echo "usage: sh apparatus/acceptance.sh EVIDENCE_DIR [failed|all] (a new folder directly under .scratch/, as an absolute path)" >&2; exit 2; }
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=$1
KEEP_WORK=${2:-failed}
case "$KEEP_WORK" in failed|all) ;; *) echo "retention must be failed or all" >&2; exit 2 ;; esac
[ "$#" -le 2 ] || { echo "usage: sh apparatus/acceptance.sh EVIDENCE_DIR [failed|all]" >&2; exit 2; }
SUITE=acceptance
DRIVER_SCRIPT=acceptance-inner-driver.sh
. "$REPO/apparatus/container/suite-host.sh"

for p in $PLATFORMS; do
    build_arch || continue
    expect "$OUT/$b/build-release.exit" 0 "$p: release build"
    expect "$OUT/$b/build-test.exit" 0 "$p: test build"
    expect "$OUT/$b/static-stewart.exit" 0 "$p: release binary is static"
    expect "$OUT/$b/static-stewart-test.exit" 0 "$p: test binary is static"
    expect "$OUT/$b/build-dynamic-control.exit" 0 "$p: dynamic ELF control builds"
    expect "$OUT/$b/static-dynamic-control.exit" 1 "$p: control fired: the static check rejects the dynamic ELF"
    expect "$OUT/$b/run-release.exit" 0 "$p: release binary runs (help)"
    expect "$OUT/$b/run-test.exit" 0 "$p: test binary runs (help)"
    run_driver stewart stewart-test || continue
    expect "$OUT/$d/selftest.exit" 0 "$p: driver self-test"
    expect "$OUT/$d/driver-complete.exit" 0 "$p: release driver completed every selected case without skips"
    expect "$OUT/$d/evidence-copy.exit" 0 "$p: independent driver evidence retained"
    expect "$OUT/$d/retention.exit" 0 "$p: requested working-file retention completed"
    {
        echo "== $p =="
        tail -1 "$OUT/$d/selftest.stdout" 2>/dev/null
        sed -n '/^## Counts/,/^## Timings/p' "$OUT/$d/evidence/RESULTS.md" 2>/dev/null | sed '$d'
        echo "driver exit: $(cat "$OUT/$d/driver-final.exit" 2>/dev/null || echo missing)"
    } >>"$OUT/host/SUMMARY"
done
finish_suite
