# Build and test apparatus

Development apparatus for the Rust audit service in [`service/`](../service).
It does not ship. Linux containers hold the build and, later, the scripted
acceptance tier; see [ACCEPTANCE.md](../ACCEPTANCE.md).

## Container access

On the development Mac the containers run under Apple `container` 1.6.1. That
service cannot be reached from a sandboxed agent shell, so the apparatus is a
set of host scripts that a person runs directly. Each script writes a new
evidence folder and refuses to reuse an existing one.

## Step 2: toolchain, vendored crates and a static build

```sh
sh apparatus/step2.sh                 # evidence in .scratch/apparatus-01
sh apparatus/step2.sh /abs/new/folder # or a folder you choose
```

The script:

1. Checks the container CLI version and that it supports `build`.
2. Archives `service/` and `apparatus/` from `HEAD` with `git archive`. The
   build therefore sees only committed files, and the commit is recorded.
3. With network access:
   - pulls the pinned `rust` and `alpine` images for `linux/amd64` (the arm64
     ones are already present);
   - builds `stewart-toolchain:1-arm64` and `stewart-toolchain:1-amd64` from
     [`container/Containerfile`](container/Containerfile), adding the native
     musl target and musl C toolchain;
   - vendors the crates named by `service/Cargo.lock` into `service/vendor`,
     which is not tracked.
4. Without network access, for each architecture:
   - builds the release binary twice, in two fresh containers, and compares
     the binaries;
   - checks the binary has no program interpreter (it is static);
   - runs it in the toolchain image and again in the pinned alpine image.

`host/DONE` reports `failures=N`. Every step keeps its stdout, stderr and exit
code under `host/` or the build folder. The toolchain image digests are the
pins for later builds and are recorded in `host/toolchain-inspect-*.stdout`.

The x86_64 builds run under Rosetta emulation. Builds there are slower, and
timings measured there are reported but do not gate (ACCEPTANCE C9).

Vendored crates come from crates.io at the versions and checksums in
`Cargo.lock`. To rebuild `service/vendor` elsewhere, run the vendoring step
again with network access. Builds are otherwise offline:
`service/.cargo/config.toml` replaces crates.io with `vendor/`.

## Step 3: the manager foundation acceptance driver

[`driver/stewart_driver.py`](driver/stewart_driver.py) is the independent
black-box driver. Its manager-foundation cases cover `new`, `prepare`,
`commission`, `receipt`, `status`, close before launch and `help`; its run
cases are listed under "Driver plan" below. It was written from
[INTERFACE.md](../docs/INTERFACE.md), [QUESTION-FORMS.md](../docs/QUESTION-FORMS.md),
[CONTRACTS.md](../CONTRACTS.md) and [ACCEPTANCE.md](../ACCEPTANCE.md) without
reading `service/`, and drives two binaries only through their command line:
the release build and the test build (`--features fault-injection,sabotage`,
INTERFACE Appendix C). It uses the Python standard library only.

The driver is a directory of modules; `stewart_driver.py` is the entrypoint and
puts its own directory on `sys.path` (isolated mode does not). The framework
(`driver_core.py`) holds the case registry, the per-case context, inventories
and evidence; support modules hold the fake Messages API (`fake_provider.py`),
the reacting auditor (`reacting_auditor.py`), a scripted auditor for exact
protocol-shape cases (`procedure.py`: a case writes its calls as a generator
and reads Stewart's actual replies), the expected answer, rendering
and manifest bytes (`answer_witness.py`), byte-exact JSON spans (`rawjson.py`)
and the run harness (`run_support.py`). Cases live in `cases_*.py` files, which
the entrypoint imports in name order, so a new group of cases is a new file.
`mini_stewart.py` is a small stand-in used only by self-tests; it is never run
against a binary. Test-only TLS certificates are in
[`driver/testdata/`](driver/testdata/README.md).

Each case keeps its own witness of everything it supplies under the evidence
folder, and inventories every archive (path, inode, size, mode, mtime,
SHA-256) before and after every command: an earlier entry may never change or
disappear (C6), and folders, destinations, homes and working directories may
not change at all. A case with sabotage controls runs on the release binary,
on the test binary without sabotage, and once per control; a control fires
when one of its target checks fails, and one that does not fire is reported as
a broken check. Fault cases run on the test binary.

Natively, for example on the development Mac against a development build
(not qualification evidence):

```sh
python3 -I -B apparatus/driver/stewart_driver.py --list
python3 -I -B apparatus/driver/stewart_driver.py --self-test
python3 -I -B apparatus/driver/stewart_driver.py \
    --binary /abs/stewart --test-binary /abs/stewart-test \
    --evidence /abs/new-folder [--case 'c17.*'] [--exclude 'close.*'] [--skip-heavy]
```

Build the test binary into its own target folder, for example with
`CARGO_TARGET_DIR`, so the two builds never share artifacts. Linux-only
expectations (the ext4/xfs/btrfs allowlist, OFD lock behaviour, byte-string
file names) are skipped with their reason elsewhere. The C9 timing gate (under
100 ms for startup, `status` and `help`) applies only with `--timing-gate on`,
which the container suite sets for the native architecture. The evidence
folder holds `START.json`, `RESULT.json`, `RESULTS.md`, each command's argv,
streams, exit status and timing, the inventories, and the witnesses. The exit
status is 0 only when no case failed and every control fired.

The container suite is the step 3 evidence:

```sh
sh apparatus/step3.sh                 # evidence in .scratch/step3-01
sh apparatus/step3.sh /abs/new/folder # or a folder you choose
```

It needs the step 2 toolchain images and `service/vendor`, and pulls the
pinned python image (its only network use). For each architecture, offline,
it builds from a `git archive` of `HEAD` the release binary, the test binary
and a glibc control build; checks that both musl binaries are static and the
glibc build is not, that `cmp` tells the release and test binaries apart, and
that only the test binary contains `STEWART_TEST_FAULT` and
`STEWART_TEST_SABOTAGE`; then runs the driver in the python image as an
unprivileged user, with the binaries mounted read-only and archives on the
container's own disk. `host/DONE` reports `failures=N`; `host/SUMMARY` gives
the driver's counts per architecture, and `driver-<arch>/evidence/` holds its
full results. Timings under x86_64 emulation are reported but do not gate.

## The acceptance suite: the whole scripted tier

```sh
sh apparatus/acceptance.sh                 # evidence in .scratch/acceptance-01
sh apparatus/acceptance.sh /abs/new/folder # or a folder you choose
```

It generalizes the step 3 suite (which stays as it was) to the whole driver.
It needs the step 2 toolchain images and `service/vendor`, and pulls the pinned
python image (its only network use). It archives `service`, `apparatus` and
`docs` from `HEAD`, and for each architecture, offline:

1. builds the release binary, the test binary and the glibc control;
2. checks that both musl binaries are static and the glibc build is not, that
   `cmp` tells the release and test binaries apart, and that only the test
   binary contains the six test-only variable names of INTERFACE Appendix C;
3. in the pinned python image with `--network none` (loopback only), as an
   unprivileged user, runs the driver's `--self-test`, then every case with
   `--network-isolated --require-all-controls`: every Appendix C.2 sabotage
   control must be assigned to a case and fire. The timing gates (startup,
   `status` and `help`; protocol calls) are on only for the native
   architecture; Rosetta's home cache is recorded as an emulator artifact.

`host/DONE` reports `failures=N`; `host/SUMMARY` gives the self-test line and
the driver's counts per architecture; `driver-<arch>/evidence/` holds the
driver's full results, and `driver-<arch>/selftest.stdout` its self-test.

## Driver plan: run, answer protocol, seal, delivery and close

This plan extends the driver to everything after launch. Its end point is one
Linux container suite (aarch64 native, x86_64 under Rosetta, `--network none`)
that runs the whole driver with `--network-isolated --require-all-controls`:
every Appendix C.2 sabotage control assigned to a case and fired, every driver
control fired, counts reported.

### Provider, network and witnesses

- The fake Messages API (`fake_provider.py`) listens only on `127.0.0.1` with
  port 0, and the driver connects only to ports its own listeners hold; both
  rules are enforced in code (`Listener`, `own_connect`). Modes: plain HTTP
  (`STEWART_PROVIDER_URL=http://127.0.0.1:PORT`, release and test binaries),
  HTTPS with the test CA (`STEWART_TEST_TLS_ROOT`, test binary), and HTTPS to
  `provider.test` through the CONNECT proxy (`HTTPS_PROXY`). The case where the
  binary itself resolves `provider.test` runs only with `--network-isolated`.
  Where listening is not permitted, cases needing the fake skip with
  "loopback listening unavailable".
- Witnesses outside every archive, under the case's evidence folder: each
  request and response byte for byte (`provider-<label>/`), CONNECT requests
  and tunnel counts, the auditor's goals, calls, replies and anomalies
  (`SUMMARY.json`), and the expected answer, rendering and manifest bytes
  computed by `answer_witness.py` from the goals and the material witness.
- Accounting: each attempt's charge under INTERFACE 6.4 is computed by the
  fake from what it did (reported usage, an estimate for a lost response, or
  none); `run_ended` usage, run and status allowances and re-entry allowances
  are compared with those sums. A case that kills a run before an attempt
  record exists overrides that attempt's charge to the estimate 6.4 states.
- Protocol timing (C9): for a response holding one tool call, the time from
  its last byte to the next request's connection. Gated under 100 ms on the
  native architecture (`c9.protocol-timing-gate`), except a search over the
  whole default scope; the `slow_list` control is judged relatively (list's
  interval against the median of the others), so it fires under emulation too.

### The reacting auditor

`reacting_auditor.py` is a deterministic policy with a goal list (label, kind,
text, citations; optionally a draft replaced later, a text or base64 artifact,
or a deliberately refused first attempt). Per conversation it: reads the
question through every page; in the first conversation lists and reads every
material, checking pages, ranges, `cite` and `lines` against the witness and
the 7.2 page rule; calls `what_am_i_working_with` through every page and reads
every listed entry by its handle, matching entries to goals by label and bytes;
then records the goals it cannot see (several calls per response when
configured), replaces drafts, prepares, reads both prepared views and compares
them with the witness bytes, dry-runs and submits with `confirm: true`. It
follows the replies' `next` calls for pages. At configured mutation counts it
emits a `compaction` block and discards its memory; every new conversation
(a continuation after a kill) starts with empty memory and checks the first
message's question and continuation notice bytes. It never consults earlier
replies except through its memory. Each reply is checked as it arrives
(envelope, `is_error`, effects keys, no host paths or manager identifiers,
citations as recorded, allowances against the fake's charges, reminder and
near-limit text and their once-per-audit allowance); each failed expectation is
an anomaly that becomes a failed check `auditor.<check>`. Because it re-adds
only what re-entry does not show, an omitted entry produces a duplicate, and
the duplicate is counted in the selection bytes Stewart produced. Endings:
`submit`, or `ordinary` (end the turn; after the reminder either submit or end
again).

### Cases

`cases_run.py` (run adapter and answer protocol, all written) and a separate
`cases_after_launch.py` (delivery, close and status after launch, T8–T10, T13
and T14, by a second author) both build on `run_support.py`, whose public
functions are a stable API. Fault points are Appendix C.1 names; controls are C.2
names. Every C.2 name is assigned to at least one case (the manager-foundation
cases already hold fourteen); a name may serve a manager and an auditor case.

| Claim | Case | Pass; differing; invariance | Controls | Fault points |
| --- | --- | --- | --- | --- |
| C1 | `c1.requests` | Every request: 6.1 line and exactly the six headers, the 4.5 splice of pinned model, system and tools bytes, tools equal the family's, `max_tokens` within limits; receipt's arrangement is the one carried. Differing: comparison family changes tools by exactly its recording tools and the second system block. Invariance: other materials, same tools and system bytes. | `extra_tool`, `arrangement_mismatch` | none |
| C1 | `c1.outside-paths` | `read`, `search`, `list` with `../`, absolute and host-only names refuse `source_unknown`; no archive path, folder, reference, store or family name in any reply. | none (C20 holds the custody-path control) | none |
| C1, C12 | `c1.tls-proxy` | HTTPS through CONNECT `provider.test:443`, SNI, key never in clear, run_started and status show URL and proxy. Differing: untrusted certificate fails every attempt (`connection_failed`). | none | none |
| C2 | `c2.question-and-reads` | First message holds the body bytes exactly; every material read over every page equals the witness (CRLF, BOM, multibyte, long lines, blank pages in `data.text`). Differing: a one-byte different question differs in exactly that byte. Invariance: same materials from another folder path read identically. | `read_live_source`, `normalize_read`, `paraphrase_question` | none |
| C2, C19 | `c19.paging` | Long lines span read pages without lost bytes or split code points; search reports every literal hit (overlapping ones too) with positions, scope, bounded pages and explicit completion; an incomplete search never claims absence. | `read_truncate_silently`, `search_omit_last_page` | none |
| C3 | `c3.edits` (T5) | Stale `replace`/`delete` refused with the current handle; repeated delete `already_removed`; equal-byte adds distinct; a repeated `tool_use` ID with identical raw input is a replay (`replay_of`), with other input `invocation_id_reused`. | `merge_equal_adds`, `replay_reexecutes`, `stale_target_overwrites` | none |
| C3 | `c3.interruptions` | Kills while appending (`stage.torn:entry`), after an entry (`entry.after_link`), during seal and delivery: re-entry and status show exactly the complete records; a torn stage file is a diagnostic. | `torn_as_entry` | `stage.torn:entry`, `entry.after_link`, `log.publish:seal`, `seal.after_link` |
| C3 | `c3.submit-races-close` (T6) | Submit paused before its seal link, close requested, released: refused `authoring_ended`, manager seal; reverse order keeps the auditor seal; repeated each way. | `manager_seal_as_auditor` | `log.publish:seal=pause` |
| C3 | `c3.limits` (heavy) | 256 entries admitted, the 257th `entry_limit`; a 4 MiB+1 call `input_too_large`; edits allowed at the limits. | none | none |
| C4 | `c4.reentry` | Compaction midway; 65+ entries over two re-entry pages and a question over one read page with its essential text last; stale page cursor after an edit `stale_view`; a damaged result record appears in `gaps`. Differing: a refusal keeps its operation and revision. Invariance: the same goals without compaction seal the same `answer.json` bytes. | `reentry_omit_entry`, `reentry_truncate_page`, `reentry_omit_last_page`, `reentry_mix_revisions`, `reentry_placement_allowances` | none |
| C6 | `c6.records` | Inventories around every command (archives and destinations only grow); access log equals the auditor's list/read/search calls with exact input bytes, refused calls and replays included; `run_ended` usage equals the fake's charges. | `rewrite_record_in_place` (run records), `remove_superseded_payload`, `skip_search_capture` | none |
| C7 | `c7.families` | Each family's instructions and tools; inability as an ordinary account; comparison's observations counted but not a section; prepare notices; empty answer (T12) `answer_empty` and `No answer entries recorded.`; citation controls (range, quote, both, irrelevant but valid; changed range, missing and ambiguous quotes refused with no entry; prose not scraped). | `framing_task_elsewhere`, `grade_support`, `block_incomplete` | none |
| C7 | `c7.prompts` | The reminder once per audit, not resent by a continuation; `max_tokens` the lesser of 16,000 and the remaining output; the near-limit notice once with exact remaining amounts; `limit_reached` after the last call, no seal, then `authoring_ended` (limit). | `reset_notice_allowance` | none |
| C9 | `c9.protocol-timing` | Interval per call (above); every auditor and manager reply passes the envelope schema. | `slow_list`, `omit_effects_on_refusal` (auditor refusal) | none |
| C12 | `c12.run-environment` | Not accepted; missing, empty or invalid key; invalid URL; invalid proxy: each refused before any request, nothing published, same run line offered. | none | none |
| C12 | `c12.test-variables` | Test build: invalid `STEWART_TEST_PROVIDER_TIMEOUT` or `STEWART_TEST_RETRY_DELAYS` refuses `test_variable_invalid`, an invalid `STEWART_TEST_TLS_ROOT` `test_tls_root_invalid`, before any request. Differing: the release build ignores the same environment and runs. | none | none |
| C12 | `e2e.reacting-audit` | The receipt's run line from another directory and HOME runs to a sealed, verified delivery; status from a third directory; ordinary close. | none | none |
| C12 | `c12.run-refusals` | `authoring_ended` with `ended_by` and its record (ordinary ending, limit, seal); `reference_closed`; `run_held` with the holder's observations while a paused run holds the lock; commission needs no key or network. Invariance: another directory and HOME change only `run_started` observations. (T13's close behaviour is in `cases_after_launch.py`.) | `relative_run_line`, `commission_over_network` | `run.after_started=pause` |
| C13 | `c13.t7-kill-after-entry` | Killed after an entry: status `interrupted`; `run` reconciles `process_gone`, continues with the notice, re-adds nothing, seals each goal once. | none | `entry.after_link` |
| C13 | `c13.continuation` | Kills during a request, while a result is written and between turns; the continuation carries the same system and tools bytes, cumulative limits and every earlier element once. Differing: killed after a confirmed submit, `run` refuses and close delivers. Invariance: the same goals without a kill seal the same answer. | `reset_limits_on_continuation`, `fresh_ledger_on_continuation` | `provider.sent:<k>`, `stage.torn:tool_result`, `run.between_turns:<k>`, `seal.after_link` |
| C13 | `c13.provider-shapes` (T15) | Thinking, redacted, compaction and unknown blocks echoed; `max_tokens` with and without a tool call; `refusal`, `pause_turn`, unknown stop reason, `model_context_window_exceeded`; undecodable complete 200s (not JSON, missing usage, repeated member, gzip) as `response_undecodable`, a 200 cut off mid-body or by a reset as `connection_lost` (retried), a cut-off error body as `http_error`; U+0000 in a `tool_use` ID (unanswerable) or name (`tool_unknown`), in `model` or `error.*` (recorded null) and in `stop_reason` (unknown stop reason); chunked and close-delimited bodies; timeout (`STEWART_TEST_PROVIDER_TIMEOUT`); `tool_use` without an ID; limits: `max_tokens` lowered near the output limit, `limit_reached` below 1,024. | none | none |
| C13 | `t16.provider-unavailable` | 529 four times; retry-after 61; 413. | none | none |
| C13 | `c13.stopping` | Close during a stalled request (`aborted_by_close`, `stopped_by_close`); SIGTERM, SIGINT, SIGHUP (`aborted_by_signal`, exit 5); a signal after the seal fails delivery with cause `signal`, ending `sealed`. | none | none |
| C14 | `c14.refusals-recorded` | Every refused call keeps its call capture and result record with reason and bytes; gaps listed with dispositions; no verdict fields. Differing: another refusal kind has its own reason. Invariance: without the refused call, the same sealed answer. | `drop_refused_capture`, `manifest_verdict` | none |
| C20 | `c20.tool-inputs` | Duplicate and escape-equivalent keys, unknown fields, `"true"`, out-of-bound integers, NUL, non-object input refuse `input_invalid` with a JSON pointer; raw bytes kept; prepare has no sealer; uncertain seal `seal_uncertain`; submit claims no delivery. | `accept_unknown_tool_field`, `leak_custody_path`, `prepare_claims_seal`, `stale_preparation_retargets`, `seal_uncertain_as_none`, `submit_claims_delivery` | `log.dirsync:seal=eio` |
| C5 | `c5.package` (after launch) | The delivered return equals the witness: members, bytes and manifest; differing answers differ only there; paths change nothing. | `drop_last_entry`, `deliver_conversation`, `regenerate_rendering`, `render_conclusion` | none |
| C5 | `c5.partial-delivery` (after launch) | A partial delivery keeps its package and names its missing member; close copies afresh; verification catches a corrupted member. | `skip_delivery_verification`, `remove_partial_package` | `delivery.member_corrupt:answer.json`, `delivery.member_write:answer.md` |
| C5 | `c5.t9-destination` (after launch) | T9: an unavailable destination; close retries it, then copies to a replacement under `--destination`. | none | none |
| C5 | `c5.conflicting-package` (after launch) | An existing path with the package's name is neither adopted, emptied nor overwritten. | none | none |
| C5 | `c5.lost-run-reply` (after launch) | A run killed after its verified delivery: status shows it; close confirms it without a second copy. | none | `delivery.after_ended` |
| C5 | `c5.t10-damaged-payload` (after launch) | T10: a payload damaged after it was recorded is a named, surrendered loss, never delivered as good. | none | none |
| C5 | `c5.payload-corrupt-fault` (after launch) | Payloads damaged as they were written are unproduced members, never good ones. | none | `entry.payload_corrupt` |
| C5 | `c5.unknown-membership` (after launch) | A seal manifest that cannot be verified: membership unknown, delivery failed, never an empty return. | `unknown_membership_empty` | `close.after_seal` |
| C8 | `c8.close-every-state` (after launch) | Close before launch, after an ordinary ending (T8), after delivery, an interruption, an empty answer and a damaged log. | `skip_confirmation`, `empty_return_before_launch` | none |
| C8 | `c8.close-faults` (after launch) | Close killed after its request, after its seal, after delivery (T14) and after closed; a run killed after its seal or before its first request. | none | `close.after_requested`, `close.after_seal`, `delivery.after_ended`, `close.after_closed_link`, `seal.after_link`, `run.after_started` |
| C8 | `c8.close-running` (after launch) | T13: close stops a held run; a stopped holder leaves close `run_still_held`; a seal alone is not a stop. | `seal_as_stopped` | `delivery.after_member:1` |
| C16 | `c16.status-after-launch` (after launch) | Status at every lifecycle point after launch: distinct facts, human and JSON agree, time changes nothing. | `ended_as_submitted`, `seal_as_delivered` | `run.between_turns:7`, `seal.after_link`, `close.after_requested`, `delivery.member_write:answer.md` |
| C17 | `c17.close-failures` (after launch) | Close's write failures and a lost close reply keep their causes, effects and retained partials. | none | `prepared.write`, `seal.manifest_write` |
| C18 | `c18.after-launch-custody` (after launch) | Originals read back after the sources are gone and after close; the delivered return verifies without the archive. | none | none |

Linux-only parts (skipped with their reason elsewhere): everything observed
through the OFD lock (`run_held`, `run_active`, interruption with a free lock,
close waiting on a run, T13), `/proc` observations (`start_ticks`, `boot_id`),
the archive filesystem allowlist and byte-string names. The timing gates apply
to the native architecture only.

### Expectations changed by the post-launch interface

The manager-foundation cases (`cases_foundation.py`) were updated where the
extended interface changed what is expected before launch: status data now has
its members in the 5.6 order, with `runs.holder`, `allowances` (null before
acceptance, zero against the limits after it), `provider_proxy`, and `closure`
with its eight keys (null placement and surrender before launch); close before
launch refuses `--confirm`/`--surrender` (`confirmation_mismatch`) and
`--destination` (`destination_not_replaceable`) publishing nothing, a closed
reference ignores options, the `closed` body carries `accepted` and its
`outcome`, and `close_requested` carries `flags` and `observations`; an
unfinished close reports `closure: unfinished` (not `requested`) with its
`intake` and next calls `close` and `status`; close on a damaged log reports
every effect `unknown` and its `bad_records`; `close_unfinished` status offers
`status` too; `--surrender` without `--confirm` and `--destination` with it are
usage errors (exit 2), as are malformed `run` operands; the identity check
covers all six test-only variable names; and `run` exits 5 for an interrupted
placement.

## Evidence retention

Evidence folders under `.scratch/` follow the retained-run rules in
[DEVELOPMENT.md](../DEVELOPMENT.md). The report or plan that cites a run keeps
its record.
