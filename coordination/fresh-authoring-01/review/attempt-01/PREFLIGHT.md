# Initial preflight review

2026-10-27. Reviewer: `fresh_review`. This is the initial static review only;
recipient outcomes and the eventual author selection have not been inspected.

The corrected protocol/tooling is suitable to continue the bounded cooperative
pilot, with the packet checks below performed before recipient dispatch. One
material witness gap was found and corrected before any helper invocation,
according to root's timing account. I verified the corrected source; I did not
observe a helper invocation or execute any subject or authored code.

## Resolved material finding: both author output roots need a witness

The original `pilot_ops.py` (SHA-256
`8602d5b1ca6f7692ecd14b9f3dac3abd7dab69310721fb95b893072d9ae4b824`),
lines 82–84, snapshots only `coordination/fresh-authoring-01/author/attempt-01/`.
The author brief grants an additional scratch output root, while the protocol
promises all saved author files. A saved failed assembly or unselected support
object in that scratch root could therefore escape the independent witness.
That would weaken any later comparison of the selected return against actual
saved work, particularly an omission or cap-pressure account.

I reported this immediately. Root supplied corrected source pinned by
`OPS-IDENTITY-02.json`:
`ec6753fcb21ecd51d148e1d08a493e20e9936da565448aed3204a10f37bcccde`,
10,636 bytes. The correction snapshots the additional scratch root when present,
or records its absence, and writes `SCOPE.json` before helper launch. The diff
contains only that correction. Its hash matches the supplied pin and it parses
as Python without execution. This closes the identified ordinary cooperative
witness gap; it does not establish continuous observation or hostile-writer
isolation. Original finding and diff remain retained.

## Before dispatch and reveal

These are bounded checks on this pilot's evidence, not requirements for a new
custody implementation:

- Compare every recipient's source membership and byte identities against the
  frozen `INPUTS.json` subject inputs. `materialize()` reads the current subject
  directory and records what it copies; it does not itself compare that set or
  those bytes to the dispatch pins. Comparing only the three packets with each
  other could miss common drift. Reject extra/missing source files and preserve
  any diagnostic before dispatch.
- Compare the accepted final snapshot with its witnessed raw envelope and helper
  result, then the materialized selections against that accepted snapshot. The
  ordinary `submit()` path records those raw/decoded comparisons. Its outer
  process can still return success when the helper refused, provided attempted
  bytes match: the child's recorded exit code and structural result must be read.
  A refused attempt is not an accepted final selection. A correction needs fresh
  paths because the utility's draft/final names are exclusive and fixed.
- Freeze the omission decision before responses and identify the intended lost
  inspection, remaining duplicate support and any unsuitable omission. Before
  reveal, verify all six first-response files against `FREEZE.json`. The concrete
  freeze function records completion after copying all six files; reveal checks
  the marker's presence, leaving this substantive verification to the coordinator.
  Preserve initial copies and compare reveal bytes/ID with the frozen omission.

These checks can use standalone reads and hashes. They do not require execution
of the constructed comparison or additional author investigation.

Root subsequently supplied `execution-01/verify_packets.py`, which I reviewed
under an explicit additional grant (SHA-256
`8f1aa3b80640d9681271bc1984361460e078931233a77ca0fc4ddaed43d23479`).
It compares common source membership/bytes with the original input snapshots,
rechecks their pins, and compares packets with the independent final-envelope
witness. This addresses the proposed dispatch gate in source. Its successful
record is required at integration; no packets had been materialized when root
issued this update, and I did not execute the checker. A minor conditional edge
was reported: its unconditional `return/objects` directory iteration fails if
omission leaves zero available objects and that directory was never created.
An absent directory can be treated as an empty population for that case. This
edge need not block a multi-object selection. Root subsequently corrected it;
the pinned checker is now `c8ecef4d5adb404d19f5a30fae923c29f80682c90442478f6b262b08f5f558a9`.
I verified that hash and the exact two-line change, with no execution. The actual
packet gate remains pending. This does not alter the requirement
to inspect the helper's recorded acceptance outcome.

## What the concrete design preserves

The witness is established before dispatch, and saved checkpoint copies precede
helper parsing. Helper stdin comes from the witnessed envelope; raw attempted
bytes, stdout/stderr, child identity/outcome and decoded identities are separately
recorded. The helper preserves over-limit attempts in full and rejects repeated
control keys. Exclusive creation retains prior attempts. The reviewed helper
code does not impose a substantive finding or treat completion as independently
confirmed.

Packet assembly keeps answer bytes, author/completion attribution, support IDs,
roles, encodings and canonical file associations. The omission retains an honest
unavailable descriptor with no content path, and does not reconstruct missing
bytes. The reordered arm reverses the support descriptor order while keeping
all content and ID associations. This is a manifest-order variation; recipient
read order remains a choice and must be reported from actual-read accounts.
No causal or equivalence conclusion follows merely from constructing it.

The recipient template supplies the same original task, excludes author scratch,
witnesses and other arms, forbids external reference-following and execution,
and asks for inspectability and dependency classifications separately from the
execution decision. It requires first memos/read accounts to stop before reveal,
then a separate second memo about changed grounds and recommendations. The
protocol reveals the same selected support bytes to all three recipients.
These are sound procedural boundaries for the stated cooperative study.

The assessment appropriately requires actual inspection loss and repair before
claiming omission sensitivity, records non-firing/redundant support, and keeps
invalid constructions distinct from opaque returns. A prompted self-check is
not a late finding; one author and one reader per arm cannot establish general
adequacy or causal format effects. No preferred substantive answer is introduced
by the reviewed task or helper acceptance rules.

## Evidence and limits

All 12 initial review snapshots match their pinned length and SHA-256. All 17
pre-dispatch input snapshots match their pinned length and SHA-256. The recipient
template matches its additional pin; the corrected utility matches its additional
pin and parses without execution. These are static identity checks, not behavior
or enforcement tests. There were zero project tests, subject trials, authored
checker runs or reviewer helper invocations.

The author output population, omission choice, actual packets, helper attempts,
recipient behavior, freeze timing and reveal outcomes remain for the separately
issued integration review. Source bytes were hash-checked without substantive
inspection. Existing qualifications concerning descriptor races, unsaved work,
continuous preservation, storage failure, durability, cap resource consumption
and procedural access remain accurate and are not additional preflight blockers.

`READS.json` records actual read scope. Detailed outputs are retained beneath
`.scratch/fresh-authoring-01/pilot-01/review/attempt-01/`, including the original
failed output-directory check, pin checks, complete grouped reads and corrective
diff. No deletion or pruning occurred. The initial preflight is complete;
integration review awaits its exact additional grant.
