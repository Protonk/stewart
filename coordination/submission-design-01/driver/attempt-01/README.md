# Independent process driver

This stdlib-only Python driver calls the prototype executable across its published
process interface. It does not import or inspect implementation code. It records
exact inputs, external raw byte witnesses, command argv/cwd/PID, streamed stdout
and stderr, exit status, assertions, per-case store snapshots and actual kernel
stop/signal observations. Each invocation copies and hashes the tested binary.
The selected evidence directory must be new. A retained `/private/tmp` tree holds
unrelated and nested working/store locations; START binds it to this run.

Run with the explicit isolated interpreter:

```
/opt/homebrew/bin/python3.14 -I -B /absolute/driver.py --binary /absolute/stewart-submission-prototype --evidence /absolute/new-evidence
```

`--list` prints selectors; repeat `--only SELECTOR` for a precise subset. Caller
must retain live driver stdout/stderr outside its own evidence directory, along
with caller command/cwd/PID/exit. Every run, including a failing one, stays.
No cleanup or pruning is performed. Source loss uses rename, not unlink.

`run_driver.py` provides the required external stream capture; it creates a new
`<evidence>.launch` sibling containing command, PID, streamed stdout/stderr and
exit records. The writer comparison additionally takes `--other-binary` pointing
to a separately built valid executable with a distinct digest. It never edits
Mach-O bytes. Without that argument the writer-only selector is excluded from
the default population; selecting it explicitly without the binary is an error.

Cases count independent store experiments; assertions count individual recorded
checks, and invocations count all helper subprocesses (including setup). Counts
are distinct and selected cases are recorded exactly. Real hooks must emit the
documented marker and reach observed SIGSTOP before SIGCONT/SIGKILL controls count.
Layout-dependent corruption tests use only the implementer's published README.
The driver never repairs an authoritative record to make a case pass.

Coverage includes ordinary binary/Unicode/empty data, descriptive-name equality
with distinct record identities, exact per-element/count/active-byte/control
bounds, source loss, stale and equal-byte replacements, direct malformed/unknown
and duplicate JSON, exact preparation manifests, dry-run storage invariance,
explicit finality, forged/cross-audit handles, all four documented commit barriers
with continue/kill controls, lost replies and same-operation recovery, conflicting
edit/submit orderings, observed lock contention, and selective corruption. The
corruption comparisons distinguish relevant and unrelated attempts, acknowledged
publication loss, malformed/duplicate records, inconsistent pending plans and
unplanned equal bytes. Distinct-writer refusal is compared with permitted reads
and byte-identical writer mutation.

The comparisons concern this disposable prototype on this local host. They do not
qualify production custody, storage durability under power loss, auditor/manager
confinement, notification/delivery, execution termination, physical reclamation,
close, Linux/WSL or Python product behavior. Recovery commands are development
probes and select no product authoring workflow. Failure-walkthrough notification
and descendant cases test only final edit refusal; the external obligations stay
explicitly unqualified.
