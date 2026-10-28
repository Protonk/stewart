# Stewart commission bundles

`stewart-commission` accepts a finite original commission and delivers a
self-contained bundle to an existing directory chosen by its manager. The named
manager custodian preserves that directory after delivery. No service owns it,
expires it or deletes it. Acceptance says the original undertaking was copied
and verified, not that an auditor ran or that a result will be produced.

This binary has no audit launch, result storage, result reader or audit close
operation. Python Stewart remains the separate audit and result-custody tool.

## Build and commands

Build with `cargo build --locked --offline --release --manifest-path successor/Cargo.toml`.
The resulting `successor/target/release/stewart-commission` is independent of this
source tree. Local qualification targets Unix descriptor APIs; actual host/test
evidence is recorded separately. No network dependency resolution is performed.

```
stewart-commission accept --request /absolute/request.json --bundle /absolute/existing-directory
stewart-commission complete --request /absolute/request.json --bundle /absolute/existing-directory
stewart-commission inspect --bundle /absolute/existing-directory [--receipt-sha256 HEX]
stewart-commission read --bundle /absolute/existing-directory --member ID [--receipt-sha256 HEX]
stewart-commission read --bundle /absolute/existing-directory --member @request [--receipt-sha256 HEX]
stewart-commission abandon --bundle /absolute/existing-directory --actor NAME --reason TEXT
```

The caller creates a new empty directory before first acceptance and retains its
locator. All paths are explicit absolute paths with no symlink components. An
existing matching accepted request returns its recorded receipt; an interrupted
request requires explicit `complete`. A changed request refuses. `complete` uses
new planned member names and never overwrites a failed copy. `abandon` records
the named actor's acknowledgment that intake remains incomplete and the named
custodian retains all partial bytes and diagnostics; it never deletes anything
or labels the commission accepted. It cannot abandon a verified accepted bundle.

`inspect` returns JSON with the observed intake state and, when its intent is
valid, the original request and commission inventory. An incomplete acknowledgment
does not erase that original undertaking or imply acceptance. Accepted bundles
also expose acceptance identity and individual verification results.

`read` requires a supported accepted bundle and writes one verified member's
exact bytes to stdout and a JSON qualification to stderr. It can recover
a selected verified member even when a different payload is missing; it never
claims whole-bundle integrity in that case. `@request` retrieves the original
request bytes from a supported accepted bundle. Incomplete inspection describes
the original request and retained inventory; it does not promise complete raw
originals or provide incomplete-material retrieval. Reader commands never consult original source paths or execute
recorded code. A bundle can be moved as a whole.

The returned receipt SHA-256 is a reference the caller can retain. Supply it to
independent readback to detect receipt substitution. Self-consistency without an
external pin does not authenticate historical origin, actor identity or honesty.
The manager's supplied custodian and grants/limits are declarations, not verified
authorization or actual harness access enforcement.

## Request

The exact UTF-8 JSON bytes are retained. Repeated keys at every nesting level,
including escaped aliases, are refused. Unknown fields are refused. Example:

```json
{
  "schema": "stewart.commission-request/1",
  "request_id": "parser-question-01",
  "custodian": "Project manager",
  "grants": "Read the selected files; static inspection only.",
  "limits": "No network, fixes, additional files or delegated investigation.",
  "members": [
    {
      "id": "question",
      "role": "question",
      "source": "/absolute/question.md",
      "view": "QUESTION.md",
      "size": 123,
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  ]
}
```

Replace size and digest with the expected exact bytes. Roles are `question`,
`instruction`, `material` or `guidance`, with exactly one question. IDs are unique
ASCII letters/digits plus `-` and `_`, 1–64 characters. Views are supplied names
for recall, never extraction destinations. All material must be explicit regular
files; no recursive selection, symbolic links, special files, Git materialization
or executable replay occurs. The request ID is scoped to its bundle directory;
there is no global registry and no recency-based selection.

Bounds: 128 members, 16 MiB per member, 128 MiB total payload, 1 MiB request.
The original request counts separately from payload. Nonempty custodian, grants,
limits and views are required. Source paths are provenance only; file modes and
executable permissions are not recorded. This bundle does not reconstruct a runnable
environment or promise an atomic multi-file snapshot. Expected identities define
the selection, and each copied file is checked for observed change during reading.

## Custody and failure

An exclusive intent is published before copying. Each attempt first records its
exact output names. Files and receipts are created exclusively, synced, and never
replaced. Final receipt publication uses an exclusive hard link to a fully written,
synced staged receipt, so interruption does not expose a partly written acceptance
record. Staged receipts remain as evidence. The destination directory is synced
before success. This relies on the filesystem honoring synchronization and hard
link semantics; it is not replication, backup or proof against hardware loss.

Mutations take an advisory descriptor lock; cooperating invocations serialize.
This is not protection against a hostile process that can write the manager's
storage. Every path component is opened relative to pinned descriptors without
following links, and special files are refused without blocking. Readback checks
bytes and bindings anew. Missing, invalid, unreadable and unsupported records
have distinct stable reasons and next steps. A terminal error does not erase
partial output. If intent publication itself is incomplete or damaged, inspect
and attributed abandonment remain supported; no acceptance can be inferred.

Keep the directory and original diagnostics when any operation fails. Use its
known locator to inspect a lost reply. Complete only the recorded request, or
acknowledge the incomplete delivery explicitly. A corrupted acceptance remains
an uncertain prior outcome, not proof that acceptance never happened. C cannot
restore unavailable original bytes, repair historical records or adjudicate the
truth of a commission or an audit return.

Intake records pin the creating binary's SHA-256. Incomplete copying or its
ordinary disposition requires that writer; a different installed binary may
inspect/read supported records but cannot silently continue the old undertaking.
No recorded executable is launched automatically. If corrupt intent prevents
establishing the writer or original outcome, `abandon` can only append a new
attributed observation acknowledgment: `unresolved_acknowledged`, still exit 3
on inspection. That does not discharge the damaged original undertaking. Keep
the original records and independently verified writer, or commission fresh
work separately; do not edit records to make the current binary fit them.
