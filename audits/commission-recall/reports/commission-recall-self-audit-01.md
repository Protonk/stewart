# Audit commission-recall-self-audit-01

```audit-report
{
  "schema_version": 2,
  "audit_id": "commission-recall-self-audit-01",
  "target_commit": "0dbb2eb0b31b488727c1ad3c8c01c0a4be934652",
  "launch_prompt_commit": "e9060955c01200bf51bec101f30b10f52367ebb0",
  "prompt_sha256": "619c32fe0511a1ae997cefc633a7f7542de87c5b07783408313e00ebab85222d",
  "launch_token": "0adce7ec3235bb31",
  "observed_checkout_commit": "e9060955c01200bf51bec101f30b10f52367ebb0",
  "completion": "complete",
  "report_kind": "answer"
}
```

Completion qualification: Complete bounded static audit of the issued C route and supplied evidence. No project execution or new experiment was performed. Source predictions and attributed prior observations are distinguished below. Completion is not a general correctness or enforcement verdict.

## Answer and implication

C provides bounded support for recovering an **accepted** original commission from a retained bundle without the original conversation or source files. Its receipt chain binds the original request, the planned selection and copied bytes; readback distinguishes recorded acceptance from current material damage. The supplied healthy specimen and selected command streams support that account. I found no supported promotion of an incomplete intake into accepted delivery on the admitted ordinary paths.

There is one concrete loss in the **supported reader presentation**: after a valid incomplete intake is acknowledged with `abandon`, `inspect` ceases to expose the available original undertaking, while `read` requires an acceptance record. The intent still retains the request. This is neither byte destruction nor proof of acceptance; it is an avoidable recall gap for an acknowledged incomplete commission. Reliance on this release should therefore be bounded to verified accepted-bundle recall unless that projection is repaired or the documentation explicitly limits recall after incomplete disposition. A separate small documentation mismatch concerning file modes is identified below.

This conclusion answers the issued distinction-preservation question. It does not require an audit launcher, result reader, new retention service or investigative retry facility.

## Supporting route and observed distinctions

All source coordinates below refer to the pinned checkout. Supplied record names are relative to `audits/commission-recall/inputs/`.

| Boundary | Source and supplied evidence | Supported conclusion |
| --- | --- | --- |
| Requested undertaking to intent | `main.rs:486–565`, request validation at 91–174, `control.rs:8–113`; specimen `INTENT.json` and copied request | The entire UTF-8 request is retained, including formatting, with its digest; parsed roles/views/grants/limits are a projection with exact raw bytes still available. Changed request bytes cannot silently reuse an intent. Nested escaped duplicate keys are rejected by one recursive parser. |
| Intent to completed delivery | `main.rs:416–465`, `safe.rs:226–257` | An attempt records output names before copying. Copied request and all selected members are checked before exclusive acceptance publication; publication is staged and synchronized. This is source evidence conditional on the stated filesystem and cooperative-writer premises. |
| Accepted receipt to current inspection | `main.rs:314–399,597–601` | Receipt pin, intent, writer, attempt, canonical member selection and custodian are checked. A valid acceptance can coexist with `integrity: damaged`; current verification is not silently made a historical acceptance claim. |
| One selected member to consumer | `main.rs:766–803`; command-014/015 streams | A damaged selected material is refused, while the unaffected question is returned exactly with `whole_bundle_integrity: damaged`. The receipt pin is checked before bytes are emitted. Current source paths are not consulted. |
| Incomplete intake to completion/disposition | `main.rs:501–565,567–609,631–764`; command-020/021/023/024 and kill end records | Ordinary `accept` refuses a prior incomplete intent. Explicit completion uses a new attempt. Attributed abandonment retains an incomplete state and blocks later completion; corrupt intent/acceptance produces unresolved acknowledgment, not a claimed successful delivery. |

Direct standard-library inspection of the supplied specimen found these relationships: accepted receipt SHA-256 `831cd6a4aa057baddaa006b495e9377310a1642b019d5b2b133cbe554f060e86` binds the supplied intent and attempt; the intent's decoded `request_utf8` equals the 1,113 copied request bytes exactly; question/material/guidance size and digest match both the requested selection and the actual supplied payloads (59/285/51 bytes). The three staged/published record pairs are byte-equal. Commands 001 and 013 name this same receipt and the same original undertaking at different destinations. These are current supplied-byte comparisons, retained in `notes/BYTE-COMPARISONS.md`, not a claim that I reran C.

The observed command-010 diagnostic is `binding_mismatch` for a changed request. The external driver's changed-selection comparison changes the selected material and expected identity while retaining the other request coordinates (`check_commission.py:176–198`); RESULT reports a changed receipt and changed recovered operand. Its destination-only control reports an invariant receipt, corroborated by supplied commands 001/013. The changed operand's actual command-011/012 streams and original independent witness are not among this assignment's supplied files, so that contrast remains attributed driver evidence rather than my independent operand comparison.

The damaged-member observation is stronger than merely a passing count: command-014 emits no payload and reports `binding_mismatch`; command-015 emits the exact supplied question and expressly says the whole bundle is damaged. The external predicate at `check_commission.py:209` only checks nonempty stderr; the actual supplied stderr and the integration assertion at `cli.rs:249–265` provide the specific qualification evidence.

## First supported reader loss: acknowledged incomplete recall

The comparison is the **same valid incomplete commission immediately before and after ordinary abandonment**, with its intent and partial bytes unchanged. Before abandonment, `inspect` returns `original_undertaking` and `request_id` (`main.rs:606–608`). After abandonment, the branch at 570–586 returns disposition, diagnostics and an inventory but omits both, even though it loaded the valid request and `disposition` checks that request's intent, writer and custodian at 636–648. This is the first consumer projection where the original question identity, selected views, grants and limits stop being presented on this path.

The companion record does preserve them: `Intent.request_utf8` holds the complete request, and `abandon` writes only its new receipt (`main.rs:178–183,728–763`). However, `safe::snapshot` emits names, sizes, digests or read diagnostics, not request content (`safe.rs:349–358`). `read @request` and all other reads call `acceptance` first (`main.rs:766–775`), which requires `ACCEPTED.json`. A legitimate incomplete acknowledgment has no such record. Thus none of the documented C reader commands recovers that valid request after acknowledgment. Manually parsing the retained intent could recover it; that does not establish that the ordinary reader route did so.

The supplied command-023 output shows the relevant ordinary state: `incomplete_acknowledged`, no original-intent or prior-acceptance diagnostic, and an inventory containing `INTENT.json` plus a request copy. It preserves the named actor, reason and custodian. Command-024 then refuses completion with `intake_disposed`. There is **no supplied post-abandon inspect/read stream**. The omission and read refusal above are deterministic source predictions, not newly observed CLI results. The command-023 inventory is an observation reported by the old writer; its underlying incomplete bundle is outside the grant.

This matters to the supported account of an original requested undertaking, including incomplete work (CONTRACTS.md:160–168,191–200,240–246). It does not contradict the narrower promise that *accepted* materials are recoverable. The guide's unqualified description of `inspect` exposing the original inventory and `@request` retrieving raw bytes (README.md:37–43) fails to mark this branch. The smallest repair would expose the already validated original undertaking on acknowledged-incomplete inspection, preserving the acknowledgment's meaning. Whether to add raw request recovery for incomplete states is a distinct interface choice; no acceptance may be inferred from it. If that behavior is intentionally deferred, narrow the guide and tell managers that acknowledged incomplete recall currently requires direct interpretation of retained public bundle records.

## Secondary documentation mismatch

README.md:86–87 says input permissions/executable bits and source paths are reported as provenance. Source paths are recorded; input modes are not. `Member` and `Request` have no mode field (`main.rs:73–90`), unknown fields are refused, and `safe::read_file` returns only bytes while outputs are created with mode 0600 (`safe.rs:226–236,297–329`). The supplied request/receipt/inspection records contain no mode provenance. Two otherwise identical source inputs differing only in executable mode therefore have no recorded mode distinction in this design.

No preservation obligation for runnable metadata needs to be added: the commission is defined by selected bytes and explicitly excludes executable replay. Narrow the sentence to say that source paths are provenance and permissions/executable bits are not preserved. This is a documentation correction, not evidence that selected content was lost.

## Evidence limits and smallest discriminating follow-up

The manager's C-ACCEPTANCE.md and implementation record report 14/14 integration tests; their raw execution logs are not supplied. I read all 14 selected test definitions. The external RESULT contains 46/46 checks over 24 ordinary command records and two separately recorded SIGKILL observations; checks include both exits and predicates and are not 46 independent cases. Both kill end records report exit -9 after `copy-000001-003.bin` was observed. The checker polls after a file larger than 1 MiB exists (`check_commission.py:119–139`); it does not identify an exact instruction or prove a partly written large file. Command-021 presents attempt-2 copies; RESULT attributes preservation of the prior partial files to its before/after snapshots. Those snapshots are not independently available here.

All seven granted source/build-guide files listed in implementation-record.json match its recorded size/hash; writer identities in that record, START and specimen agree. That establishes consistency of the supplied identity account, not independent source-to-binary build provenance. I did not inspect the old executable, host or source locations. Current hash checks also cannot authenticate historical actor honesty. The grant is procedural, not OS isolation. Actual hostile-host confinement, power-loss durability, multi-file snapshot atomicity and other-host behavior remain unproved or explicitly excluded; cooperative descriptor locks and no-follow source code alone do not establish those claims.

The smallest useful next check for the reader gap is one separately commissioned before/after comparison on a legitimate incomplete intake with a valid intent and an independently retained original request: capture `inspect` before abandonment, abandon, then capture `inspect` and `read @request`. Keep the witness outside the bundle. Prediction: unchanged intent bytes, original undertaking visible before, absent after, and raw read refused for missing acceptance. Use an otherwise identical unacknowledged incomplete bundle as an invariance control (including with original sources unavailable), and a healthy accepted bundle as the firing control for exact `@request` retrieval. Distinguish this reader projection from the rival explanations of damaged intent, missing original sources or false acceptance. This comparison was proposed independently here and was not executed; it requires no wider codebase audit.

## Stopping reason, failures and deviations

The admitted intake, copy, acceptance, inspect, member-read and disposition route has been traced with its control/safe dependencies, selected tests and supplied observations. The concrete reader projection and documentation mismatch are bounded; accepted-bundle evidence and remaining premises are identified. No implementation, original evidence or private storage was modified. No network, history, nested agent, project build, test or C execution occurred. Only the issued helper operations and permitted isolated standard-library inspection were used; one mistyped helper identity argument was refused as recorded below.

The issued input helper returned exit 0: selected=53, matched=53, failed=0. Declaration start returned exit 0. One combined tool response truncated a source interval; that interval was reread completely, with no unrepaired reading gap. The first declaration-set invocation was refused with exit 2 (`handoff_identity`) because I mistyped the launch commit by adding a digit; the helper reported nothing done and instructed copying the issued command. The subsequent invocation uses the exact issued commit. No source read failed. `notes/READ-ACCOUNT.md` records actual coverage and these limitations; `notes/CLAIM-TRACE.md` records source/evidence trace and proposed comparisons. The declaration is finalized through the issued helper, and its read-only check is the final action before stopping.
