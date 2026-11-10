#!/bin/sh
# Check every literal line in MARKERS against BINARY, including stripped builds.
# An empty/unreadable list, unreadable binary or grep error is never a pass.
set -u
[ "$#" -eq 3 ] || { echo "usage: sh check-build-markers.sh absent|present MARKERS BINARY" >&2; exit 2; }
case "$1" in absent) expected=1 ;; present) expected=0 ;; *) echo "expected absent or present" >&2; exit 2 ;; esac
markers=$2
binary=$3
[ -f "$markers" ] && [ -r "$markers" ] || { echo "cannot read marker list: $markers" >&2; exit 2; }
[ -f "$binary" ] && [ -r "$binary" ] || { echo "cannot read binary: $binary" >&2; exit 2; }
count=0
failures=0
while IFS= read -r marker || [ -n "$marker" ]; do
    count=$((count + 1))
    if [ -z "$marker" ]; then
        echo "empty marker at line $count" >&2
        failures=$((failures + 1))
        continue
    fi
    LC_ALL=C grep -a -F -q -e "$marker" "$binary"
    found=$?
    if [ "$found" -eq "$expected" ]; then
        printf 'ok: marker %s %s in %s: %s\n' "$count" "$1" "$binary" "$marker"
    else
        printf 'FAIL: marker %s expected %s in %s, grep exit %s: %s\n' "$count" "$1" "$binary" "$found" "$marker" >&2
        failures=$((failures + 1))
    fi
done <"$markers"
[ "$count" -gt 0 ] || { echo "marker list is empty: $markers" >&2; exit 2; }
printf 'markers: %s checked, %s failed\n' "$count" "$failures"
[ "$failures" -eq 0 ]
