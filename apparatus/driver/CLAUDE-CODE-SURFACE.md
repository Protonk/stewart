# Independent supplied-surface fixture

`claude_code_surface.py` prepares the full selected-family tool inventory and
launch-surface files from the [runtime contract](../../docs/claude-code/CONTRACT.md).
Its independent author does not read the service implementation or tests.
It executes nothing. The [independent observer](CLAUDE-CODE-OBSERVER.md) serves
this fixture on the sockets that the gated binary's relay and hook helpers
reach, using the
[specified private transport](../../docs/claude-code/CONTRACT.md#private-helper-transport-for-independent-fixtures).
The [supplied-surface controller](../claude-code/README.md#supplied-surface-controller)
prepares each comparison with this module.

```sh
python3 -I -B apparatus/driver/claude_code_surface.py --self-test
```

The self-test checks all three families' inventories, initialization, the fixture
gate, one positive effect, invalid/unknown calls, reused identifiers, hook
decisions, invariance and failed witnesses. It also checks exact prepared files
and manifest restrictions. It starts no process or socket. The helpers' own
transport, including the hook helper's refusal of an empty or oversized reply,
is checked by the standalone runtime driver's direct helper case.

The fixture lists every tool in the selected family with its exact transformed
schema. Its sole implemented effect is `record_account` with the declared
synthetic text. Other listed operations return an explicit fixture limitation;
they are not implementations of Stewart's audit core. The controller's hook and
MCP attempts are identified as synthetic controls, not real-harness attempts.
Prepared settings, environment, arguments and input bytes do not establish that
Claude received them. No custody, publication, service conformance, effective
managed configuration, provider traffic or spending claim follows from this fixture.

Hook decision bytes are journaled separately from the bytes supplied on the
connection. Events identify their observer and use the shared Linux kernel clock
`CLOCK_MONOTONIC`. Preparation copies
the fixture and the specification-derived helpers it uses into `sources/`.

`manifest()` builds the `EVIDENCE.json` inventory of regular files by relative
path, size and SHA-256. It excludes itself, `OBSERVATION.json` and a separately
supplied `CHECK.json` to avoid digest cycles. Links and special files refuse.
The module exports the required check inventory, `REQUIRED_CHECKS`, for the
[profile producer](../claude-code/README.md).

This fixture never writes `OBSERVATION.json`, `CHECK.json` or an eligible
profile. A separately commissioned real-harness observation and independent
review must supply fresh authentication/startup and supplied-surface evidence
before a reviewed check can attest compatibility. Raw authentication output must be discarded; only
`loggedIn`, `authMethod` and `configDirectory` may be retained. That initial
compatibility check remains separate from subsequent full-service behavior and
from permission to launch a placement.
