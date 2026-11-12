# Independent supplied-surface fixture

`claude_code_surface.py` prepares the full selected-family tool inventory and
launch-surface files from the [runtime contract](../../docs/claude-code/CONTRACT.md).
Its independent author does not read the service implementation or tests.
It invokes only the gated Stewart binary's actual relay and hook helpers, using
the [specified private transport](../../docs/claude-code/RUNTIME-REFERENCE.md#private-helper-transport-for-independent-fixtures)
against fixture-owned sockets. It has no Claude, authentication or model launcher.

Run with an explicit isolated Python interpreter:

```sh
python3 -I -B apparatus/driver/claude_code_surface.py --self-test
python3 -I -B apparatus/driver/claude_code_surface.py \
  --binary /absolute/path/to/gated/stewart \
  --work /absolute/path/to/fresh-evidence
```

The self-test checks all three families' inventories, initialization, the fixture
gate, one positive effect, invalid/unknown calls, reused identifiers, hook
decisions, invariance and failed witnesses. It also checks exact prepared files,
manifest restrictions and actual socketpair reply bytes, including an empty reply
beside normal/invariance controls. It executes no helper or harness process.

The rehearsal runs seven separately supervised helper comparisons: positive MCP
traffic, a closed fixture gate, positive invariance, hook allow, closed-gate deny,
unpinned-tool deny and the hook helper's empty-reply failure. It requires a host
that permits Unix socket listeners and observation/signalling of owned process
groups. Denied observations fail; they are not treated as passing controls.
Each worker has an eight-second whole-worker watchdog plus up to 1.5 seconds for
observed group stopping. Setup, helper creation, reads and cleanup run inside the
worker. Unknown stopping prevents later helpers from starting. The owner and host
must continue running for that bound to hold.

`--work` is a new evidence directory. The separate retained helper workspace is
printed and named in `scope.json`; sockets remain outside the evidence tree.
`--family` selects `open-inquiry`, `inquiry-framing` or `comparison`.
`--launch` optionally supplies the exact bytes of a launch JSON value, without
surrounding whitespace, and `--model` supplies its model binding. Defaults are
explicitly synthetic. The launch file's executable is never invoked, and no
credential directory is opened, copied or hashed. Only `--binary` is executed,
with the two fixed helper commands. The static gated-binary check prevents an
ordinary mistaken executable selection; it is not hostile-program confinement.

The fixture lists every tool in the selected family with its exact transformed
schema. Its sole implemented effect is `record_account` with the declared
synthetic text. Other listed operations return an explicit fixture limitation;
they are not implementations of Stewart's audit core. The controller's hook and
MCP attempts are identified as synthetic controls, not real-harness attempts.
Prepared settings, environment, arguments and input bytes do not establish that
Claude received them. No custody, publication, service conformance, effective
managed configuration, provider traffic or spending claim follows from this run.

Independent received/supplied bytes, client observations, fixture effects and
process results remain under `witness/`. Hook decision bytes are separate from
the bytes actually supplied, so the empty-response control cannot be mistaken
for a delivered JSON response. Events identify their observer and shared kernel
clock: `CLOCK_UPTIME_RAW` on macOS and `CLOCK_MONOTONIC` on Linux. `sources/` binds
the fixture and the specification-derived helpers it used. Keep originals through
review under the repository's [evidence rules](../../development/DEVELOPMENT.md#evidence-and-retention).

`EVIDENCE.json` inventories regular files by relative path, size and SHA-256.
It excludes itself, `OBSERVATION.json` and a separately supplied `CHECK.json` to
avoid digest cycles. Links and special files refuse. `OBSERVATION.json` binds
the exact `inputs/launch.json`, `inputs/surface.json` and `inputs/tools.json`
bytes and the manifest. Its mode is always `synthetic-rehearsal`; authentication
and real-harness startup are explicitly unexercised. The module exports the
required check inventory for the [profile producer](../claude-code/README.md).

This fixture never writes `CHECK.json` or an eligible profile. A future separately
commissioned real-harness observer and independent review must supply fresh
authentication/startup and supplied-surface evidence before a reviewed check can
attest compatibility. Raw authentication output must be discarded; only
`loggedIn`, `authMethod` and `configDirectory` may be retained. That initial
compatibility check remains separate from subsequent full-service behavior and
from permission to launch a placement.
