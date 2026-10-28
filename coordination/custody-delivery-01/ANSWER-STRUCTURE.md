# Provisional answer structure for the first leg

Coordinator proposal for discussion, 2026-10-28 UTC, from source `f784001`. Not
agreed and not a CONTRACTS change. It elaborates PLAN-FIT item 2 at the user's
request. Revision 2 incorporates a read-only check (workflow `wf_91217239-a10`:
document fidelity and outcome-pressure lenses; returns in
`.scratch/answer-structure-check-01/`). Root accepted its material findings; the
reviewed first draft, never committed, is preserved there as `DRAFT-01.md`.

## What is being decided

DEVELOPMENT-PLAN's answer-protocol inquiry sets a decision point before the
durable submission interface: choose a provisional common structure, requirements
per admitted question type, and explicit unsupported capabilities. Before attempt
custody it also asks for snapshot assembly, payload bounds, repeated-attempt
identity and result lifetime. The decided prepare/manifest direction answers
snapshot assembly; operation references and handles answer repeated-attempt
identity; this note proposes the rest.

Already decided (CONTRACTS, successor answer construction and manager receipt):
the submission tool controls construction, artifact identity, edits, generated
mechanical metadata and the exact recorded selection, without authority to assess
or rewrite content; add, handle-based replace and delete; prepare and dry-run
submit; collect; a verifiably empty selection yields an honest empty return.
CONTRACTS' agnosticism principle requires that participants can express, inspect
and contest the responses a question permits, including no supported finding,
missing evidence, an unresolved premise or a reframe; restrictions that exclude or
privilege outcomes need explicit deliberation. Representation was left for design.

Evidence: the reviewed receipt-challenge recommendation (PROVISIONAL-INTERFACE)
favours a readable primary answer plus ordered, explicitly selected artifacts,
the issued commission bound by the receiving operation, and optional attributed
semantic hints; it disclaims minimality. Every studied form kept the primary text
separate from its artifacts. The bounded prototype modelled elements as
tool-assigned identity, version, name, size and digest, admitted empty files and
non-answer text, and allowed equal names. Fresh returns observed so far held
1–18 selected artifacts and about 9–60 KB; none included executed-experiment
outputs, and the studies justify no product size cap.

## Proposal

**1. Common structure: an optional readable account plus ordered artifacts.**

- An element is exact bytes of any content (text, data, scripts, plots, archives,
  empty), with a tool-assigned identity and version and an auditor-chosen name.
- One element may be marked as the **account**: the readable response the
  question permits, whether a finding, no supported finding, missing evidence, an
  unresolved premise, a reframe, a blocked or refused return, or partial work,
  with its grounds and limits. The marker is structural, not semantic: Stewart
  does not read it, and a selection without an account is admitted. Replace keeps
  the marker; delete removes the element. This keeps the studied primary/artifact
  split without needing the account to be added first.
- Other elements are artifacts in addition order; replace keeps position. No
  reorder operation in the first leg; the account's separate place removes the
  main reason to reorder.
- Names are uninterpreted label text, generously bounded in length. They may
  contain `/`, so an auditor can label files with their relative layout while each
  file stays individually digested. Unique names are guidance, not a rule:
  prepare and dry run list duplicates as an informational note. Retries are
  identified by operation reference, never by name or content.
- Element and answer metadata carry no outcome, kind, completion or role field
  and no required declaration. Per element: identity, version, account marker,
  position, name, size, digest, and the observed source as attributed provenance.
- Stewart also keeps its mechanical records: operation references and outcomes,
  refusals with retained failure evidence, preparation handles and manifests,
  membership revisions, and submit/collect provenance.
- An empty selection is admitted on submit as well as collect; attribution keeps
  an empty auditor submission distinguishable from an empty manager collection.

**2. Requirements per question type: none at admission.** The four bundled
recipes' Supply, Return and Stop expectations remain instructions to the auditor
and an inspection guide for the manager; Stewart does not check them, because a
mechanical check would grade substance or push authors toward a shape. The
bundled bytes stay unchanged. Their pointers to the frozen three-kind report
declaration and the Python program executor are frozen-baseline material: new
successor auditor guidance, written in this leg, says the outcome is stated in
the account, that no kind is required, and how the account marker works.

**3. Explicitly unsupported in the first leg.**

- Directories as elements. Each element is one regular file's bytes or supplied
  bytes; an archive is opaque bytes whose members Stewart does not list.
- Materializing name-labelled layout as directories in the delivered copy.
- References in place of bytes: a path, URL or digest in the text is only text.
  Stewart fetches nothing; links grant no access; no verified external-asset route.
- Symlinks, FIFOs, sockets and devices as sources (custody read rules).
- Semantic hints or per-artifact roles as fields. This departs from the
  recommendation's optional hints: no first-leg consumer needs them.
- Validation that the text's references match element names.
- History browsing of superseded payloads (retained until close, not served).
- Content transformation: no newline, encoding or Unicode normalization.
- Execution witnessing: logs, outputs and exit statuses are auditor-supplied,
  auditor-attributed bytes; Stewart verifies bytes, not that execution happened.
- A human auditor's manual equivalent, which belongs to the human-handback work.

Material referenced but not recorded is not a return member. Existing
partial-work and preservation obligations toward it are unaffected.

**4. Bounds, chosen together with the missing reference route.** Proposed
unevidenced starting values: 256 elements, 64 MiB per element, 256 MiB in the
current selection. Superseded and deleted payloads stay held until close, so a
separate 1 GiB retained-bytes cap protects the host. It can refuse only additions
or replacements larger than 1 MiB; smaller edits draw on a fixed 64 MiB reserve,
so the account can always be revised. Delete, prepare, submit and collect never
refuse on it. Each bound is stated in help and in the commission as a limit of
the custody undertaking. A `limit_exceeded` refusal reports the remaining
allowance and says the bytes are not in custody and remain under existing
preservation obligations. Stewart records each such refusal (operation, name,
size, bound) as its own observation, and the return's provenance lists them, so
an exclusion is visible even if the auditor never mentions it. Bounds, the
retained cap and the absence of a reference route together determine what
support cannot be delivered.

**5. Lifetime and delivered layout.** Audit custody holds the answer until
authorized close; the manager's copy is independent afterward (decided). Inside
the decided return package (question and instructions, commission receipt,
manifest, selected bytes, provenance), each element is stored under a
Stewart-generated name: position plus, where the label ends in a conservative
extension, that extension, so plots and archives open by type. A plain-text
index maps generated files to labels; the manifest is authoritative and carries
an explicit format version. Delivery timing is PLAN-FIT decision 3.

## Reversibility

Leg-1 audits are specimens, so every choice here is cheap to revisit now. Later,
optional fields can be added in new record versions, but sealed answers never
acquire them, so consumers must keep accepting answers without them. Any admission
rule adopted now becomes something consumers rely on, so admission stays minimal.
The most persistent commitment is the delivered copy's layout and manifest,
because managers keep those copies and Stewart never rewrites them; hence the
explicit manifest version from the first leg.

## What stays open

Whether more structure would help readers. W01's open coverage remains:
unexpected late findings, substantive reframing, refusal or blocked returns,
broader fresh instrument discrimination and question-specific schemas. Within
the bounds, none is excluded by an admission rule; none is tested in this
container. CONTRACTS' residual auditor claim that a commission does not authorize
receipt of something is expressible only as account text in the first leg.

## Choices for the user

1. Adopt this content-neutral structure, with a distinguished optional account
   element, as the provisional structure.
2. Admit an empty selection on auditor submit, not only manager collect.
3. Names as free labels that may contain `/`; uniqueness as guidance only.
4. Confirm or change the bounds, the retained-bytes cap and reserve, and the
   absence of an external-asset route, as one set.
5. Keep semantic hints out of the first leg.
6. Delivered layout: generated names with extensions plus an index; layout
   materialization unsupported.
