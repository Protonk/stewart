# Independent service return witness

`claude_code_service_witness.py` reviews complete delivered packages against
an immutable outside witness. Its native rehearsal uses the actual gated Stewart
binary with the existing [synthetic runtime driver](CLAUDE-CODE.md). It never
accepts an installed profile, installation receipt, authentication session or real
harness. Synthetic attestations belong only to the existing offline fixtures.
No output is an eligible profile check or a grant of invocation authority.

```sh
python3 -I -B apparatus/driver/claude_code_service_witness.py --self-test
python3 -I -B apparatus/driver/claude_code_service_witness.py \
  --rehearse --binary /absolute/gated-stewart \
  --work /private/tmp/fresh-service-witness
```

The self-test creates synthetic packages and exercises the reviewer without
launching a subprocess. The rehearsal needs native Unix sockets and process
observation. Its work path must be fresh, physical and absolute, outside the
repository; the binary must be outside the work directory. Keep the binary
unchanged during the run. A host watchdog should bound the whole command.
Neither that watchdog nor this adapter claims it can stop a process group that
escaped its ownership. An unknown stop blocks further starts.

## Review API

`write_witness(path, entries, revision, *, family, writer, actor, reference, status_raw,
inputs, provenance)` writes a fresh read-only witness file and returns its
SHA-256 pin. `entries` contains specification-derived `answer_witness.Entry`
objects with known produced payloads. `inputs` maps names to exact outside
witness bytes. `provenance` requires nonempty `kind` and `description` strings;
the caller is responsible for their truth. This writer confers no independent
authenticity on the supplied evidence.

The `stewart.claude-code.service-witness/1` document contains:

| Member | Attribution |
| --- | --- |
| `selection` | Known entry IDs/versions, kinds, labels, payload bytes, citations, encodings and revision supplied by the independent witness. |
| `bindings` | Expected family, writer digest and actor, with audit/store identifiers and seal time learned from manager observations. Expected actor and revision must agree with those observations. |
| `inputs` | Original input bytes, sizes and digests, including the independent synthetic peer transcript in a rehearsal. |
| `provenance` | The declared origin of the expected selection. A synthetic peer's fixed account is not an oracle for future real model answers. |
| `manager_observations` | Exact status bytes and reference. Audit/store identifiers and seal timestamp are learned through the manager interface, not independently predicted. |

`expected_package(value)` validates these bindings and reconstructs
`answer.json`, `answer.md`, all selected artifacts and the exact manifest using
the independent [answer witness](answer_witness.py). This initial reviewer
expects produced entries and complete delivery; loss/surrender comparisons are
outside its current scope.

`review_package(package, witness_file, evidence_dir, *, witness_sha256,
archive_root)` launches nothing. The caller supplies the separately retained
witness pin. All paths must be normalized and absolute, with physical directory
ancestry. Witness and output must remain outside the package and archive;
the reviewer never reads archive content. An unsafe output location or an
existing output directory refuses before writes, leaving the caller to retain
that exception. A safe output records diagnostics even when an input cannot be
read.

The reviewer opens package ancestors and files without following symlinks,
reads only regular files, and checks identities before and after reading.
Containment checks compare ancestor inode identities as well as paths, so case
aliases on a case-insensitive filesystem cannot place evidence inside an input.
Links, special files and unexpected directories are inventoried and refused;
directories are never traversed. Unexpected regular files are retained and fail
membership comparison. Reads are bounded at 64 MiB per file and 256 MiB per
package. A bound failure is an incomplete failed observation, not a pass.
Package mode must be 0700 and member modes 0600. Changes during observation,
missing members, extra members and byte differences fail.

Each fresh review directory retains:

| Path | Content |
| --- | --- |
| `WITNESS.json` | Exact expected witness bytes, including a pin mismatch when readable. |
| `expected/` | Independently reconstructed package bytes when the witness validates. |
| `actual/` | Exact readable regular-file package bytes, including unexpected regular members. |
| `REVIEW.json` | `stewart.claude-code.service-package-review/1`: outcome, checks/counts, complete-capture flag, full inventory, provenance and diagnostics. |
| `EVIDENCE.json` | `stewart.claude-code.service-evidence/1`: relative paths, byte counts and SHA-256 values for retained review members. |

Review is a byte/provenance comparison. It grades no substantive finding, answer
quality, completeness of understanding or hidden provider activity.

## Synthetic service rehearsal

A narrow subclass runs the existing `runtime-submit` and `runtime-interruption`
cases. This creates three audits: baseline submission, fresh-session/workspace
invariance, and a harness exit after a completed record followed by a fresh
placement, re-entry and submission without adding the entry again. The last is
not an externally triggered interruption.

The adapter preserves the existing preparation, receipt readback, launch and
traffic comparisons. It additionally binds the synthetic peer's single
completed account call to the outside expectation, reviews the whole package,
closes every audit, repeats close and verifies refusal of a later run without a
new launch. Two-placement continuation uses its actual placement count. Exact
package snapshots are retained before close, after close and after repeated
close/refused run.
Each synthetic fixture permits at most two placements with a 15-second deadline
per placement. These are offline rehearsal limits, not a real-harness cap study.

Before another start, owned groups must be independently observed absent.
Missing process records, unknown/present groups, or an exception leaving command
termination uncertain block every later `run`, including the next iteration
inside an existing case. The inherited command timeout is an offline test bound,
not a live commissioning mechanism. No automatic replacement run is attempted.
An unexpected success when a post-close run should refuse also blocks subsequent
mutations. Before close, `witness/<audit>/stopping-run-NNNN.json` preserves exact
service-owned process and stop records, separately attributed read-only group
probes and their monotonic timing. Copying service metadata does not turn it into
an independent launch observation.

The original driver reports two selected cases in `RESULT.json`
(`stewart.claude-code.offline-driver/2`), with its actual checks and failures.
`REHEARSAL.json` (`stewart.claude-code.service-rehearsal/1`) repeats those counts,
records the nine required package reviews and any launch block, and states the
remaining unexercised work. A failed or skipped selected case, missing review or
failed package comparison makes the rehearsal exit nonzero.

The work directory retains exact manager commands/results in `commands/`, raw
synthetic peer and input witnesses in `witness/`, and the new module,
`answer_witness.py` and existing driver/helper sources in `driver-snapshot/`.
Each `witness/<audit>/` contains `complete-return-witness.json` and three review
directories: `package-before-close`, `package-after-close` and
`package-after-repeat`. The top-level `EVIDENCE.json` binds the regular command,
witness, source and report files. Original runtime work and service-owned archive
captures remain in place with that provenance; they are not relabeled independent
peer witnesses or automatically exported.

Native rehearsal is development evidence. An eligible real-harness profile,
bounded live commission, full-service live launcher/comparison, external
interruption barrier, actual compaction observations, turn/output enforcement and
Linux qualification remain separate work. Retain original evidence through review
under the [development evidence rules](../../development/DEVELOPMENT.md#evidence-and-retention).
