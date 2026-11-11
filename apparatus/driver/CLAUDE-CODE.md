# Offline development profile checks

`claude_code.py` independently checks preparation, custody and synthetic runtime behavior in the
[Claude Code development runtime contract](../../docs/claude-code/CONTRACT.md).
Its author works from that contract, the common specifications and this driver's
specification-owned forms, without reading the service implementation or tests.
It is a standalone native driver; it is not registered in the release suite.

Run from the repository root with an explicit Python interpreter:

```sh
python3 -I -B apparatus/driver/claude_code.py --self-test
python3 -I -B apparatus/driver/claude_code.py --list
python3 -I -B apparatus/driver/claude_code.py \
  --binary /absolute/path/to/development/stewart \
  --release-binary /absolute/path/to/featureless/stewart \
  --work /absolute/path/to/fresh-work-directory
```

`--work` must be absent and its parent must exist. Use a physical absolute path
without symlink components because the profile contract requires no-follow
reads. Keep the selected binary in a separate directory from the work tree;
the launch directory must also be outside the writer tree.
`--release-binary` is optional; omitting it reports the featureless-build
case as skipped. The driver never substitutes a skipped check for a pass.
Use repeatable `--case NAME` options to diagnose selected cases; `RESULT.json`
names the unselected cases separately. The default runs every case.

The preparation cases use local `new`, `prepare`, `commission`, `receipt` and
`status` operations and a shell canary that records an unexpected invocation.
Runtime cases call `run` with a synthetic executable implemented by this driver.
It supplies synthetic authentication and startup observations and talks to the
actual Stewart MCP adapter through its configured stdio command. It never invokes
a Claude executable, real authentication probe, login, provider or model.
The embedded installation and check entries are
synthetic attestations for offline input validation; they establish no signature
verification, installation check or authority for a real session.

MCP envelopes and independent transport witnesses use a separate JSON decoder
that accepts signed JSON-RPC error codes. Embedded Stewart core replies and
archive records retain their strict control decoding. Envelope checks follow
the [MCP base protocol](https://modelcontextprotocol.io/specification/2025-11-25/basic)
and [stdio framing](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
The self-test exercises a negative transport error through witness readback and
the invalid-startup checks, with malformed and duplicate-member controls.

The cases exercise all three question families, exact transformed MCP schemas
and pinned texts, profile/check binding refusals, strict JSON and profile path
controls, placement bounds, API-field rejection and captured receipt readback.
Invariance cases change outer profile whitespace, manager HOME/CWD and accepted
source files. A recorded canary start fails the local-operation check. The
driver inventories every archive before and after each operation and fails if
an earlier record changes or disappears. Runtime controls include successful
auditor submission and verified delivery, attempted authoring before rejected
startup, interrupted work followed by a fresh session, placement exhaustion,
deadline and owner-death stopping with a resistant descendant, and API credential
option rejection. A controlled missing-stop case retains the original process
metadata, substitutes an independently owned live group, and checks that restart
and close cannot silently treat it as stopped or signal that unrelated group.
A recorder-failure case waits for independently witnessed startup, removes write
permission from the synthetic run directory, proves a directory write is refused,
and releases one witnessed authoring attempt. It requires actual group stopping,
no answer mutation and an explicit capture/write diagnostic. Permissions are
restored only after observed stopping; the permission witness stays outside the
archive. Running as root skips this case explicitly because root can bypass the
permission control.
Harness observations and attempted MCP calls are independently
witnessed outside the archive. Missing final checkpoints must remain unknown.

`RESULT.json` reports per-case outcomes, check counts, explicit skipped cases,
firing controls and timings. `commands/` retains exact argv, stdout and stderr;
`witness/` retains independent question, material, profile and tool inputs outside
the archive. `driver-snapshot/` preserves the executable synthetic harness and
its specification-derived helpers used by that run. Keep the work directory
through review, then apply the repository's
[evidence retention rules](../../development/DEVELOPMENT.md#evidence-and-retention).
Native results are development evidence only. Synthetic runtime checks can
demonstrate the exercised adapter and local process controls; they establish no
real harness behavior, provider consumption or Linux qualification.
