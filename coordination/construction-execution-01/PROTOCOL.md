# Bounded run and independent observation

The commission authorizes one invocation of the unchanged selected observer,
emitting six specimen evaluations in fixed A–F order. The question is whether
these observed outputs match the already-authored predictions. A mismatch is
evidence, not a reason to tune inputs or repeat the run. An observer/tool failure
ends the invocation; partial output, stderr and process status remain preserved.

## Inputs and staging

Use the final envelope committed at 9ffad1f and the earlier accepted snapshot
only after comparing them and their retained identities. The original subject
packet remains pinned to 81b557a. Verify the three full source files actually
used or hashed against that Git revision; verify the finite packet against its
manifest. Never load source or specimens from live author scratch during the run.

Create `.scratch/construction-execution-01/` exclusively. Root separately retains
the original envelope/snapshot/acceptance, source packet, predictions and staged
bytes under `witness/`. Materialize exactly:

- `stage/packet/`: ledger.py, _json.py, test_stewart_ledger.py.
- `stage/specimens/`: review.json, A-complete.jsonl, B-duplicate.jsonl,
  C-note-invariant.jsonl, D-control-extinguished.jsonl,
  E-admission-before-reach.jsonl, F-parse-problem.jsonl, PREDICTIONS.md,
  CONSTRUCTION.md, observe-proposed.py.

These 13 files are the protected selection. Names are chosen by this protocol,
not interpreted as paths from arbitrary return references. Each must match its
selected UTF-8 bytes or pinned source bytes. Freeze lengths, hashes, file modes
and observed device/inode identities. Stage files are mode 0444, directories
0555, with no symlinks, special files, `.pyc` or `__pycache__` entries. No other
worker may write staging, witness or execution outputs. All staged originals
and witnesses remain after the run; no disposal is part of the experiment.

## Interpreter and launch

Resolve `/opt/homebrew/bin/python3.14` to the actual interpreter. Capture its
binary identity and a standard-library-only `-I -B -S` probe: Python version,
implementation, executable/base paths, flags, platform/machine, sys.path and
startup cache/site state. Require Python 3.14, isolated mode, no site and no
bytecode writes. The interpreter and standard library are trusted host inputs;
this does not pin every dynamic library or qualify a hostile interpreter.

The exact resolved argv, cwd and environment go into PREPARATION.json before
review and into RUN-PLAN.json before launch. Use the stage root as cwd, stdin
closed, and an explicit minimal child environment (`PATH=/usr/bin:/bin`,
`LC_ALL=C`, `TZ=UTC`). The unchanged observer receives absolute staged packet
and specimen paths. No shell, network, installation, wrapper or pytest is used.

Root's independent driver opens fresh binary stdout/stderr records before the
child starts. It writes an exclusive RUN-RESERVATION.json before any launch;
that reservation is never reusable, even if launch or capture fails. Record
the child PID and eventual exit status separately. A 30-second runaway guard
bounds this finite small-file process; on expiry record the intervention before
terminating its new process group, retain partial output, and do not rerun.
A caught parent failure after launch also attempts recorded bounded shutdown and
reaping before inventory. If termination remains unresolved, record that instead
of presenting a posttermination inventory. Abrupt parent/host death and failure
of all recording channels remain unqualified. Independent preflight may revise
the driver before launch without rewriting PREPARATION: its disposition must
bind the exact reviewed driver identity and preserve the originally prepared
driver. The reservation records the driver actually used.

## Preservation and interpretation

Root verifies all 13 input identities against the independent witness immediately
before launch and after termination, including actual inventory membership and
absence of bytecode caches. The child emits its own before/after hashes and each
specimen's read-byte hash; compare those to root's independently staged identities.
Read-only modes are observed permissions, not proof against their owner changing
them. Fresh cache-free staging and `-B -S` address ordinary cached-code and startup
ambiguities; they are not general enforcement qualification. Standard-library
startup reads and runtime imports remain trusted.

This is a cooperative, singly owned execution. There is no continuous monitor
proving the absence of every changed-and-restored byte. Endpoint identities and
child reports retain their actual scope; the result must explicitly leave
continuous preservation unestablished. No universal counterexample or malicious
writer claim is sought. Preserve discrepancies between parent and child accounts.

Capture raw output before parsing it. The comparison requires exactly one before
record, six ordered specimen records, and one after record; exit status and stderr
remain separate. Compare the authored complete summary predictions, prerequisites,
row counts and parse-problem expectations. F's decoder error wording is intentionally
unspecified: require the separate line-11 invalid-JSON problem, not one exact
implementation-specific sentence. Check A/B's fixed raw row count and unchanged
control, C's summary/prerequisite invariance, D's operand-sensitive control, E's
sequence gap and F's parse/summary separation. No preferred audit outcome is a grade.

A fresh reviewer checks preparation before launch, then independently inspects
captured bytes, membership, frozen predictions, preservation records and root's
comparison. It must not execute the observer or subject. Record actual checks
and any disagreement. The project installed-wheel checker is not invoked for
this standalone frozen-source experiment: zero pytest nodes; one observer process
and, if it reaches them, six specimen evaluations. This does not replace project
acceptance or broaden support beyond the recorded host/interpreter.
