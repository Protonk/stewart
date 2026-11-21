# Independent service return witness

`claude_code_service_witness.py` reviews complete delivered packages against
an immutable outside witness. It launches nothing and never accepts an
installed profile, installation receipt, authentication session or real
harness. No output is an eligible profile check or a grant of invocation
authority. The [service comparison procedure](../claude-code/README.md#service-comparison-procedure)
uses it for every submitted package, including in its synthetic rehearsal
against the actual gated binary.

```sh
python3 -I -B apparatus/driver/claude_code_service_witness.py --self-test
```

The self-test creates synthetic packages and exercises the reviewer without
launching a subprocess. Its valid selection includes binary and UTF-8 artifacts;
an independently corrupted witness using `text` as an encoding is refused, and
the original valid package remains unchanged and reviewable.

## Review API

`write_witness(path, entries, revision, *, family, writer, actor, reference, status_raw,
inputs, provenance)` writes a fresh read-only witness file and returns its
SHA-256 pin. `entries` contains specification-derived `answer_witness.Entry`
objects with known produced payloads. `inputs` maps names to exact outside
witness bytes and must include the original body as `question-body`.
`provenance` requires nonempty `kind` and `description` strings;
the caller is responsible for their truth. This writer confers no independent
authenticity on the supplied evidence.

The `stewart.claude-code.service-witness/2` document contains:

| Member | Attribution |
| --- | --- |
| `selection` | Known entry IDs/versions, kinds, labels, payload bytes, citations, encodings and revision supplied by the independent witness. |
| `bindings` | Expected family, writer digest and actor, with audit/store identifiers and seal time learned from manager observations. Expected actor and revision must agree with those observations. |
| `inputs` | Original input bytes, sizes and digests, including the independent synthetic peer transcript in a rehearsal. |
| `provenance` | The declared origin of the expected selection. A synthetic peer's fixed account is not an oracle for future real model answers. |
| `manager_observations` | Exact status bytes and reference. Audit/store identifiers and seal timestamp are learned through the manager interface, not independently predicted. |

`expected_package(value)` validates these bindings and reconstructs
`question.md` from the original body, along with `answer.json`, `answer.md`,
all selected artifacts and the exact manifest using
the independent [answer witness](answer_witness.py). This initial reviewer
expects produced entries and complete delivery; loss/surrender comparisons are
outside its current scope. Artifact encodings are `utf-8` for a `text` input and
`binary` for a `base64` input, as specified by
[the recording tools](../../docs/INTERFACE.md#74-recording-and-editing).

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
