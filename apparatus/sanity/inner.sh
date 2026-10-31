#!/bin/sh
# Offline rehearsal only. All work stays in the retained Linux container.
set -u
rec() {
    name=$1
    shift
    "$@" >"/out/$name.stdout" 2>"/out/$name.stderr" </dev/null
    step_rc=$?
    echo "$step_rc" >"/out/$name.exit"
    return "$step_rc"
}
rec environment sh -c 'id; uname -a; stat -f -c %T /work; cat /proc/net/route' || exit 1
mkdir -p /work/state || exit 1
chown 1000:1000 /work/state || exit 1
rec exercise setpriv --reuid=1000 --regid=1000 --clear-groups \
    env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work/state \
    python3 -I -B /work/code/apparatus/sanity/exercise.py /bin-in/stewart /work/state
final_rc=$(cat /out/exercise.exit)
rec evidence-copy cp -R /work/state/evidence /out/evidence || final_rc=1
rec retention-start date -u +%Y-%m-%dT%H:%M:%SZ || final_rc=1
rec retention-archive tar -cpf /out/work.tar -C /work state || final_rc=1
rec retention-list tar -tf /out/work.tar || final_rc=1
rec retention-sha256 sha256sum /out/work.tar || final_rc=1
rec retention-end date -u +%Y-%m-%dT%H:%M:%SZ || final_rc=1
echo "$final_rc" >/out/final.exit
exit "$final_rc"
