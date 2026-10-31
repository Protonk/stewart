# Build and test apparatus

Development apparatus for the Rust audit service in [`service/`](../service).
It does not ship. Linux containers hold the builds and the scripted acceptance
tier of [ACCEPTANCE.md](../ACCEPTANCE.md): `step2.sh` builds the toolchain
images and vendors the crates, and `acceptance.sh` builds the release and test
binaries and runs the independent driver against them.

[`check_links.py`](check_links.py) checks the relative links and anchors in the
repository's Markdown.

The qualification record, [`qualified.json`](qualified.json), is the tracked
account of what the suites have shown; [`qualified.py`](qualified.py) keeps it
and generates [`qualified.md`](qualified.md) from it.

## Running the scripts

On the development Mac the containers run under Apple `container` 1.6.1. Each
script checks that version and that the container services are running, and
stops otherwise. The scripts need Apple `container` on the host. An agent whose
shell is sandboxed cannot reach it, so the agent prepares the command and the
user runs it. Each script requires one argument, its evidence folder, and
refuses one that exists; give a new folder directly under `.scratch/` as an
absolute path. Without the argument a script prints its usage and exits 2
before doing anything else.

## `step2.sh`: toolchain images, vendored crates and a static build

```sh
sh apparatus/step2.sh "$PWD/.scratch/apparatus-NN"  # from the repository root; NN not yet used
```

It creates `service/vendor` and refuses to start while that folder exists. The
script:

1. Checks the container CLI version, that its services are running and that it
   supports `build`.
2. Archives `service/` and `apparatus/` from `HEAD` with `git archive`. The
   build therefore sees only committed files, and the commit is recorded.
3. With network access:
   - pulls the pinned `rust` and `alpine` images for `linux/arm64` and
     `linux/amd64`;
   - builds `stewart-toolchain:1-arm64` and `stewart-toolchain:1-amd64` from
     [`container/Containerfile`](container/Containerfile), adding the native
     musl target and musl C toolchain;
   - vendors the crates named by `service/Cargo.lock` into `service/vendor`,
     which is not tracked.
4. Without network access, for each architecture:
   - builds the release binary twice, in two fresh containers, and compares
     the binaries;
   - checks the binary has no program interpreter (it is static);
   - runs it in the toolchain image, and runs `stewart help`, which exits 0, in
     the pinned alpine image.

`host/DONE` reports `failures=N`. Every step keeps its stdout, stderr and exit
code under `host/` or the build folder. The toolchain image digests are the
pins for later builds and are recorded in `host/toolchain-inspect-*.stdout`.

The x86_64 builds run under Rosetta emulation. Builds there are slower, and
timings measured there are reported but do not gate (ACCEPTANCE C9).

Vendored crates come from crates.io at the versions and checksums in
`Cargo.lock`. To produce `service/vendor` in another checkout, run `step2.sh`
there with network access. Builds are otherwise offline:
`service/.cargo/config.toml` replaces crates.io with `vendor/`.

## The independent driver

[`driver/stewart_driver.py`](driver/stewart_driver.py) is the independent
black-box driver. Its manager-foundation cases cover `new`, `prepare`,
`commission`, `receipt`, `status`, close before launch and `help`; its run and
after-launch cases are listed under "Cases" below. It was written from
[INTERFACE.md](../docs/INTERFACE.md),
[QUESTION-FORMS.md](../docs/QUESTION-FORMS.md),
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
folder, and inventories every archive (path, type, inode, size, mode, mtime,
SHA-256) before and after every command: an earlier entry may never change or
disappear (C6), except that a file first seen while a Stewart process was
still running may grow, keeping its earlier bytes as a prefix. Folders, homes
and working directories may not change at all, and a destination may only gain
entries once a run can deliver. A case with sabotage controls runs on the
release binary, on the test binary without sabotage, and once per control; a
control fires when one of its target checks fails, and one that does not fire
is reported as a broken check. Fault cases run on the test binary.

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
expectations (the ext4/xfs/btrfs allowlist, OFD lock behavior, byte-string
file names) are skipped with their reason elsewhere. The C9 timing gate (under
100 ms for startup, `status` and `help`) applies only with `--timing-gate on`,
which the container suites set for the native architecture. The evidence
folder holds `START.json`, `RESULT.json`, `RESULTS.md`, each command's argv,
streams, exit status and timing, the inventories, and the witnesses. The exit
status is 0 only when no case failed and every control fired.

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
- What the fake accepts is declared as data (`Accepts` in `fake_provider.py`):
  the request members of the pinned API version, the members of
  `output_config`, the effort levels and on-demand `compaction`. A gate judges every request body
  against it before the case's responder answers, and refuses a mismatch as
  the Messages API does. A case that needs a provider which has moved away from
  what the release sends changes one fact of it (`renamed`, `without`,
  `withdrawn`, `answering`); a parameter added later joins the model the same
  way.
- Witnesses outside every archive, under the case's evidence folder: each
  request and response byte for byte (`provider-<label>/`), CONNECT requests
  and tunnel counts, the auditor's goals, calls, replies and anomalies
  (`SUMMARY.json`), and the expected answer, rendering and manifest bytes
  computed by `answer_witness.py` from the goals and the material witness.
- Accounting: each attempt's charge under INTERFACE 6.4 is computed by the
  fake from what it did (reported usage, replacing top-level totals with valid
  iteration sums when supplied; an estimate for a lost response; or none); `run_ended` usage, run and status allowances and re-entry allowances
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
emits an opaque `compaction` block in an ordinary response and discards its own
memory. This tests re-entry after fake memory loss; it does not exercise provider
summary requests or establish live model compaction. Every new conversation
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

`cases_run.py` holds the run adapter and answer protocol cases,
`cases_compaction.py` the provider summary transitions and accounting,
`cases_effort.py` the effort setting and provider rejection cases, and
`cases_after_launch.py` the delivery, close and status cases after launch
(T8–T10, T13 and T14), marked "after launch" in the table. They build on
`run_support.py`, whose public functions are a stable API. Fault points are
Appendix C.1 `point=action` items; controls are C.2 names. Every C.2 name is
assigned to at least one case (fourteen of them to manager-foundation cases); a
name may serve a manager and an auditor case.

| Claim | Case | Pass; differing; invariance | Controls | Fault points |
| --- | --- | --- | --- | --- |
| C1 | `c1.requests` | For each family, and for open inquiry with other materials, an audit lists the materials and ends ordinarily. Every request: 6.1 line and exactly the seven headers in order, including the compaction beta, the 4.5 splice of the pinned model, system and tools bytes, no `output_config` (no effort is set) and a pinned `request_extra` of `{}`, tools equal to the family's, `max_tokens` from 1,024 to 16,000 and 16,000 first; the receipt and `run_started` name the arrangement whose bytes were carried. Differing: comparison and inquiry framing each differ from open inquiry exactly by their recording tools, sharing the first system block and differing in the second (instructions). Invariance: other materials, same tools and system bytes. | `extra_tool`, `arrangement_mismatch` | none |
| C1 | `c1.outside-paths` | `read` refuses `source_unknown` for names that leave the material (`../`, absolute host and archive paths, archive names, near misses, directories), and `search` for the first six of them; a near miss (`materials/A.py`) names the real name as a hint; a constructed `list` cursor refuses `handle_invalid`; no host or archive path, reference, store or family name in any reply. Differing: the real name reads. Invariance: a second audit elsewhere refuses the same relative names with the same reasons. | none (C20 holds the custody-path control) | none |
| C1, C19, C20 | `c1.effort-levels` | Prepare accepts each effort level of 3.2 (`low`, `medium`, `high`, `xhigh`, `max`): the prepared record's settings carry `effort` right after `limits` (with `inquiry` and `varies` after it when given), the reply shows no other level, and the arrangement pins `request_extra` `{"output_config":{"effort":<level>}}`. Differing: without the key the settings have no `effort` and `request_extra` is `{}`. Refused `setting_invalid`, recording no preparation: `High`, `MAX`, `xHigh`, `extreme`, `none`, `default`, `minimal`, `3`; a second `effort` line is `front_matter_invalid`. | none | none |
| C1, C2 | `c1.effort` | The same question and materials commissioned with `effort: high` and without; each run meets a 529 with retry-after 61 (one attempt), then continues, lists, reads and ends ordinarily. With the effort, every request (first and continuation) has `,"output_config":{"effort":"high"}` spliced after `tools` and nothing else added, matching the pinned `request_extra`; the fake's model of the pinned API version accepts each; no system block, tool or message contains the word effort; first messages carry the question exactly. Differing: without it the arrangement differs only in `request_extra` (`{}`), no request has `output_config` and a provider model without `output_config` accepts every request; request by request the system, tools and messages bytes are equal and each body is the other with exactly that member removed. | `misspell_effort`, `effort_in_prompt` | none |
| C1, C12 | `c1.tls-proxy` | Through `HTTPS_PROXY` every attempt is CONNECT `provider.test:443` with host `provider.test:443`, then TLS with SNI `provider.test`, the key never in clear; the run ends ordinarily; `run_started` records the base URL, override, proxy and API version, and status shows the override and proxy. Differing: a certificate from another CA fails all four attempts (`connection_failed`), no request reaches the fake, and the run ends `interrupted` `provider_unavailable` with every provider fact null (request 1, attempt 4). | none | none |
| C2 | `c2.question-and-reads` | The first message holds the question body exactly (CRLF, over one read page, essential text last); the reacting auditor reads the question and every material page by page, each page's range, bytes, `cite` and lines equal to the 7.2 page rule and the witness (CRLF, BOM, multibyte, long lines, a hidden file, a lone CR, blank and empty pages in `data.text`); a material rewritten in the folder after commission still reads as captured; the access log equals the reads. Differing: a question one byte different arrives different in exactly that byte. Invariance: the same materials from another folder read identically. | `read_live_source`, `normalize_read`, `paraphrase_question` | none |
| C2, C19 | `c19.paging` | A line of three-byte characters pages at 65,534 bytes, never splitting a code point or losing bytes; a start inside a code point is `range_invalid` naming the nearest boundaries, a start past the end `range_invalid`, and a start at the end gives an empty complete page. Search reports every literal hit, overlapping ones included, in position order with its `cite` and line, over pages of at most 128 hits with cursors and the last page complete; absence is reported only with `complete: true`; a 1,025-byte search text is refused and 1,024 bytes accepted. Differing: `aaa` gives one hit per line. Invariance: naming the default scope (the question, then the materials in index order) gives the same hits. | `read_truncate_silently`, `search_omit_last_page` | none |
| C3 | `c3.edits` (T5) | Equal-byte adds are distinct entries, the second with `label_duplicate`; a stale `replace` or `delete` refuses `stale_entry` with the current handle, which still reads its bytes; a repeated delete reports `already_removed`; a `tool_use` ID repeated with identical raw input is a replay (the same result, `replay_of`, no entry), with other input `invocation_id_reused`, and a fresh call with the same arguments is a new entry; reads change no revision; the prepared selection equals the witness at revision 6. | `merge_equal_adds`, `replay_reexecutes`, `stale_target_overwrites` | none |
| C3 | `c3.interruptions` | Killed while appending an entry (a torn stage file) or before linking it (a complete stage file never linked): status `interrupted` counts no entry and reports the stage file, the continuation's re-entry shows none, the auditor adds each goal once and every sealed entry has its entry record. Killed before the seal link: no seal, and the continuation seals. Killed after it: status `sealed_undelivered` with the auditor's seal, and `run` refuses `authoring_ended` (`ended_by` seal) without a request. | `torn_as_entry` | `stage.torn:entry=kill`, `log.publish:entry=kill`, `log.publish:seal=kill`, `seal.after_link=kill` |
| C3 | `c3.submit-races-close` (T6) | Close wins: with the run paused before its seal link, close is requested and the run released; submit refuses `authoring_ended` (`ended_by` close, `close_requested_at`, no seal or sealer), the run ends `stopped_by_close` and close seals revision 1 as manager. Submit wins: with the run paused after its seal link, close is requested and the run released; it ends `sealed` and the only seal is the auditor's. Each order twice. | `manager_seal_as_auditor` | `log.publish:seal=pause`, `seal.after_link=pause` |
| C3 | `c3.limits` (heavy) | 256 entries recorded in four responses of 64 calls; the 257th refuses `entry_limit` with the answer unchanged; at the limit a replace and a delete work, then one add fits and the next refuses; a record input of 4 MiB + 1 byte refuses `input_too_large` and one of exactly 4 MiB is recorded. | none | none |
| C4 | `c4.reentry` | Seventy entries come back over two re-entry pages (64, then 6 with only `entries` and `page`); a page cursor taken before an edit refuses `stale_view` with a call to start again; a refused citation is listed in `latest_refusals` with its operation and revision. An unavailable provider ends run 1 and a result record is then damaged: the continuation's re-entry reports run 2, all 71 entries, the damaged record in `gaps` and the cumulative allowances. Invariance: the reacting auditor seals the same `answer.json` bytes with and without fake memory loss, including an entry longer than one read page. | `reentry_omit_entry`, `reentry_truncate_page`, `reentry_omit_last_page`, `reentry_mix_revisions`, `reentry_placement_allowances` | none |
| C4, C1, C6, C18 | `c4.provider-compaction` | Two top-level usage totals reach exactly 150,000 with input, cache and output all contributing; iteration totals deliberately differ. Summary requests carry the pinned beta, model, effort, system, tools and every pending tool result. Signed content arrays, including unknown fields, whitespace and escapes, replace the active context exactly; the next request has the post-compaction notice. Re-entry still sees both existing entries. Every original request reconstructs from retained captures and reset markers, and responses, charges and call captures match the external witness. One placement, three answer entries and one seal. Differing: 149,999 top-level tokens with larger iteration sums sends no summary. Invariance: identical sealed answer. | `omit_compaction`, `alter_compaction_summary`, `retain_precompaction_context`, `ignore_compaction_usage` | none |
| C4, C13, C14 | `c4.compaction-failures` | Missing, unsigned, empty, mistyped, repeated-type and multiple signed blocks; tools alone or beside a summary; ordinary stop, output cutoff, refusal and exhausted context; absent/null/empty/repeated/malformed usage iterations, unknown types, missing/negative/noninteger/repeated counts and count/sum overflow. Each keeps the raw response, interrupts with the specified cause and charge, executes no summary tools and consumes no reminder. | none | none |
| C4, C13 | `c4.compaction-budgets` | Turn, input and output allowances each stop before the summary when exhausted, or after accounted summary iterations without sending another request. Output cap shrinks to 1,200 on the summary; an ended audit cannot resume. | none | none |
| C4, C7, C13 | `c4.compaction-notices` | A near-limit notice triggered by summary usage follows the signed block beside the post-compaction notice, with exact remaining allowances. A second specimen shows a successful summary leaves the ordinary-stop reminder available. | none | none |
| C4, C9, C13 | `c4.compaction-rejection` | A provider schema that rejects the summary parameter, and a provider refusing the beta header, each interrupt with the provider's own facts, retain captures and make no fallback request. Status remains interrupted. | none | none |
| C4, C13 | `c4.compaction-usage-fallback` | Ordinary absent/null iterations use top-level counts; valid message/compaction iterations replace them. Malformed iteration data in an ordinary response is undecodable rather than falling back to smaller top-level totals. | none | none |
| C4, C13 | `c4.compaction-retries` | A 529 on the summary request retries identical bytes, counts no usage for the HTTP error, accounts the summary response once, then resets to an ordinary request. | none | none |
| C4, C13, C8 | `c4.compaction-stopping` | SIGTERM, SIGINT, SIGHUP and close during an in-flight summary abort through the normal path with estimated usage, retained request capture and no reminder. | none | none |
| C6 | `c6.records` | `list`, `read`, `search`, a refused read and a replayed search are in the access log in order with their exact input bytes and outcomes, and the search is captured; a replace keeps both versions' payload files with their bytes; every run record decodes strictly; `run_ended` usage equals the fake's charges; inventories around every command (archives and destinations only grow). | `rewrite_record_in_place` (run records), `remove_superseded_payload`, `skip_search_capture` | none |
| C7 | `c7.families` | Each family's requests carry its own system and tools bytes. With no entries, prepare gives only `answer_empty`, and its views are the empty selection and `No answer entries recorded.`; after an account saying the question cannot be answered as asked, prepare lists one `section_unfilled` per unfilled expected section in tools order and names no sealer, and submit seals; comparison counts an observation without expecting it as a section. Open-inquiry citation controls: a range, a quote, both, an irrelevant but valid citation and a read page's `cite` are recorded with Stewart's additions; a changed range, a missing quote and an ambiguous quote (its occurrences listed) refuse with no entry; prose resembling a citation is not scraped. T12: an empty answer seals and delivers an empty `answer.json` and the rendering `No answer entries recorded.` | `framing_task_elsewhere`, `grade_support`, `block_incomplete` | none |
| C7 | `c7.prompts` | An ordinary stop gets the exact reminder; after an unavailable provider interrupts the run, a stop in the continuation ends it without a second reminder (one per audit). With a 10,000-token output limit, `max_tokens` is the lesser of 16,000 and the remaining output; the near-limit notice is sent once with the exact remaining amounts; the run ends `limit_reached` after executing the last call, with no seal, and `run` then refuses `authoring_ended` (limit). | `reset_notice_allowance` | none |
| C9 | `c9.protocol-timing` | One call per response (`list` three times, `read` twice, `search`, `what_am_i_working_with`, a record, `prepare` and a refused read): each interval is measured (above), and `list` may not exceed the median of the others by 250 ms; every reply, the refusal included, passes the envelope rules. | `slow_list`, `omit_effects_on_refusal` (auditor refusal) | none |
| C9, C6 | `c9.provider-rejections` | One commission with `effort: xhigh` per drift of the fake's declarative provider model (`fake_provider.Accepts`, judged by `Gate` in front of the auditor): the effort renamed, `output_config` removed, the level withdrawn, `output_config` removed with an HTML 400 page instead of an error object (no request ID), and with a message over 1,024 bytes whose cut falls inside a character. Runs 1 and 2 each make one attempt, end `interrupted` `provider_rejected` with exit 5, and give status, error type, error message (cut as the attempt record cuts it) and request ID in the run reply and `run_ended` exactly as the fake sent them, or null; the attempt record is `http_error`, `then` `end`, charged none; the raw response capture holds the body sent; run 2 reports the same refusal; status says `interrupted`. Every request carries the effort. Invariance: with the model moved back to the pinned API version's, run 3 of the same commission is accepted and ends ordinarily. | `hide_provider_message`, `rejection_as_unavailable` | none |
| C12 | `c12.run-environment` | Before acceptance `run` refuses `not_accepted`. After it, a missing or empty key, a key with bytes outside 0x21–0x7E, a provider URL with another scheme, user information, a query, a fragment or a trailing slash (a non-loopback `http://` URL only with `--network-isolated`) and an invalid proxy are each refused before any request, publishing nothing and offering the same run line; status stays `not_started`. | none | none |
| C12 | `c12.test-variables` | Test build: invalid `STEWART_TEST_PROVIDER_TIMEOUT` or `STEWART_TEST_RETRY_DELAYS` refuses `test_variable_invalid`, an invalid `STEWART_TEST_TLS_ROOT` `test_tls_root_invalid`, before any request. Differing: the release build ignores the same environment and runs. | none | none |
| C12 | `e2e.reacting-audit` | The receipt's run line, from another directory and HOME, runs the reacting auditor with fake memory loss to a sealed, verified delivery equal to the witness; every request's shape, the echoed history, the access log and `run_ended` usage are checked; status from a third directory; an ordinary close. | none | none |
| C12 | `c12.run-refusals` | Commission succeeds with no key while the provider URL names the fake, which sees no connection, and its run line names the absolute writer. `run` refuses `authoring_ended` with `ended_by` `ordinary_ending` (naming its record), `limit` or `seal`; `reference_closed` after close; `run_held` with the holder's observations while a paused run holds the lock. Invariance: the same ordinary run from other directories and HOMEs gives the same ending, usage and notices, and `run_started` observations name a process and user ID. (T13's close behavior is in `cases_after_launch.py`.) | `relative_run_line`, `commission_over_network` | `run.after_started=pause` |
| C13 | `c13.t7-kill-after-entry` | Killed after an entry: status `interrupted`; `run` reconciles `process_gone`, continues with the notice, re-adds nothing, seals each goal once. | none | `entry.after_link=kill` |
| C13 | `c13.continuation` | Killed with a request in flight (its answer never read, charged an estimate), while a result is written and between turns: each status `interrupted` with one run; the continuation carries the same system and tools bytes and the continuation notice, cumulative allowances and every earlier element once; both `run_ended` usages equal the fake's charges. Invariance: each continuation seals the same `answer.json` bytes as an unkilled reference. | `reset_limits_on_continuation`, `fresh_ledger_on_continuation` | `provider.sent:12=kill`, `stage.torn:tool_result=kill`, `run.between_turns:11=kill` |
| C13 | `c13.provider-shapes` (T15) | One audit, one placement per shape, each continuing the last: thinking, redacted, compaction and unknown blocks echoed byte for byte through chunked and close-delimited bodies; `max_tokens` with a call continues and without one interrupts; `refusal`, `pause_turn`, an unknown stop reason; T15: `model_context_window_exceeded` with one call executes and records it and sends no further request; complete but undecodable 200s (not JSON, missing usage, repeated member, gzip, and over 32 MiB unless `--skip-heavy`) as `response_undecodable`; a 200 cut off mid-body as `connection_lost` (retried) and a cut-off 500 as `http_error`; timeouts under `STEWART_TEST_PROVIDER_TIMEOUT=1`; a `tool_use` without an ID or with U+0000 in it, captured and not executed; stop reason `tool_use` without a `tool_use` block; U+0000 in a tool name (`tool_unknown`), in `model` (recorded null) and `stop_reason`, and in an error body's type and message (recorded null in the attempt record and the run reply); a retry-after date ignored for the test delay. Each ending, cause, attempt outcome and charge as 6.3 to 6.6 state. | none | none |
| C13 | `t16.provider-unavailable` | Four 529s: four attempts with the same bytes, none charged, ending `interrupted` `provider_unavailable` with exit 5, the run reply and `run_ended` giving the last attempt's status, error type, error message and request ID (request 1, attempt 4). Continuing, a 529 with retry-after 61 ends after one attempt (`provider_unavailable`), and a 413 after one attempt (`provider_rejected`). | none | none |
| C13 | `c13.stopping` | SIGTERM, SIGINT and SIGHUP during a stalled request each abort it (`aborted_by_signal`, charged an estimate) and end the placement `interrupted` with cause `signal`, exit 5; close during one aborts it (`aborted_by_close`) and the run ends `stopped_by_close`. After a seal, SIGTERM while delivery is paused fails the delivery with cause `signal`, ending `sealed`. | none | `delivery.after_member:1=pause` |
| C14 | `c14.refusals-recorded` | A refused citation, a path outside the material, a stale replace and a duplicate-key input each keep a call capture with the exact block bytes and a result record with the reason, `is_error` and the content sent, creating no entry; the audit seals and delivers; no manifest, log record, result envelope, run reply or status holds a key that grades the answer, and the manifest has exactly its 8.2 keys. Differing: each kind has its own reason. Invariance: without the refused calls, the same `answer.json` bytes. | `drop_refused_capture`, `manifest_verdict` | none |
| C20 | `c20.tool-inputs` | Duplicate and escape-equivalent keys, an unknown field (naming the expected keys), NUL, a non-object input, a wrong type, nesting deeper than 16, out-of-bound and non-integer starts and a missing field refuse `input_invalid` (naming the field's JSON pointer), raw bytes kept; an unknown tool refuses `tool_unknown`, and constructed entry and view handles `handle_invalid`; no reply carries a custody path; prepare names no sealer; a stale preparation refuses `stale_preparation` with `revision_now`; `"true"` for `confirm` is `input_invalid`; a dry run seals nothing; the confirmed submit's data is exactly the seal facts, claiming no delivery. Test build: an uncertain seal publication fails `seal_uncertain` with `effects.seal` unknown and the same submit as next call. | `accept_unknown_tool_field`, `leak_custody_path`, `prepare_claims_seal`, `stale_preparation_retargets`, `seal_uncertain_as_none`, `submit_claims_delivery` | `log.dirsync:seal=eio` |
| C5 | `c5.package` (after launch) | Five goals (quoted and ranged citations, a replaced draft, a text and a binary artifact) are delivered as exactly `manifest.json`, `answer.json`, `answer.md` and two artifact members, equal to the witness, mode 0700/0600, verifying from their own manifest, whose digest the run printed at seal; status `delivered_open`; an ordinary close confirms placement with no provider request or second copy. Differing: one changed byte in an entry's text changes `answer.json` and `answer.md` only there. Invariance: another archive, destination, directory and HOME give the same members, byte for byte, apart from the manifest. | `drop_last_entry`, `deliver_conversation`, `regenerate_rendering`, `render_conclusion` | none |
| C5 | `c5.partial-delivery` (after launch) | A failed `answer.md` write leaves the run's attempt 1 partial (`write_failed`, the package kept) and the run still ends `sealed`; status `sealed_undelivered` offers `--destination`. Close with `answer.json` corrupted in the copy makes attempt 2 partial (`not_verified`), since verification reads members back; close again makes a verified attempt 3, presented for confirmation as a copy made after the close request. Packages 1 and 2 keep their bytes; confirming closes. | `skip_delivery_verification`, `remove_partial_package` | `delivery.member_write:answer.md=eio`, `delivery.member_corrupt:answer.json=corrupt` |
| C5 | `c5.t9-destination` (after launch) | T9: with the commissioned destination removed after commission, the run's attempt 1 and close's attempt 2 fail, and close stays unfinished offering `--destination`; a missing path or a file as `--destination` is `destination_invalid`, publishing nothing; `--destination DIR` makes a verified attempt 3 there for confirmation, after which another `--destination` is `delivery_already_verified`. Confirming closes; the commissioned path is not recreated and no close sends a provider request. | none | none |
| C5 | `c5.conflicting-package` (after launch) | With a directory planted under the first package's name, attempt 1 ends `name_taken` and attempt 2 delivers `-002`, equal to the witness; the planted directory is neither adopted, emptied nor overwritten; an ordinary close confirms the copy. | none | none |
| C5 | `c5.lost-run-reply` (after launch) | A run killed after its verified delivery and before `run_ended`: status shows the delivery; close from another directory and HOME reconciles the run (`process_gone`) and closes `delivered_before_close` with no other attempt or copy. | none | `delivery.after_ended=kill` |
| C5 | `c5.t10-damaged-payload` (after launch) | T10: with one bit of a payload flipped after an ordinary ending, close seals as manager with that entry unproduced (`damaged`) and no `answer.md`, delivered `verified_with_losses` for confirmation; `--destination` is `delivery_already_verified`, `--confirm` alone or surrendering one of the two losses `surrender_required`, an unknown loss `handle_invalid`, `--surrender` without `--confirm` a usage error; surrendering both closes `closed_with_surrendered_losses`, and status never shows a complete delivery. | none | none |
| C5 | `c5.payload-corrupt-fault` (after launch) | Payloads corrupted as they were written, then an ordinary ending: close seals as manager with exactly those entries unproduced, delivers `verified_with_losses` and closes only when every loss is surrendered. | none | `entry.payload_corrupt=corrupt` |
| C5 | `c5.unknown-membership` (after launch) | Close killed after its manager seal, then the archived seal manifest damaged: close's attempt fails `manifest_unavailable` with no package, token or loss IDs, as does an attempt to a new `--destination`, which stays empty; `--confirm` is refused; nothing is closed and no empty return is delivered. | `unknown_membership_empty` | `close.after_seal=kill` |
| C8 | `c8.close-every-state` (after launch) | Close before launch (`closed_before_launch`, nothing sealed or delivered) and after a failed intake (`closed_without_acceptance`). T8, after an ordinary ending: `--destination` and `--confirm` are refused before any copy; close seals as manager and delivers for confirmation; a repeat re-presents the same token publishing nothing, a wrong token is refused, and `--confirm` closes. Differing: a copy delivered before the close request is confirmed by an ordinary close (`delivered_before_close`). Also an interruption sealed by the manager with its entry, an empty answer's honest empty return, and a damaged log (status `log_damaged`, close unfinished publishing nothing, `run` refused). | `skip_confirmation`, `empty_return_before_launch` | none |
| C8 | `c8.close-faults` (after launch) | Close killed after its request (status `close_unfinished`, `run` refuses `reference_closed`, close continues to a manager seal), after its seal (close delivers without sealing again), after its delivery (T14: status shows the token, and close from another directory and HOME re-presents it) and after `closed` (status closed, close `already_closed`). A run killed after its seal (close reconciles it, keeps the auditor's seal and delivers) or before its first request (close seals an empty selection as manager). | none | `close.after_requested=kill`, `close.after_seal=kill`, `delivery.after_ended=kill`, `close.after_closed_link=kill`, `seal.after_link=kill`, `run.after_started=kill` |
| C8 | `c8.close-running` (after launch) | T13: while a run stalls in a request, a second run refuses `run_held`; close stops the run (`aborted_by_close`, `stopped_by_close`, exit 0), seals its entry as manager and delivers for confirmation. A SIGSTOPped holder leaves close `run_still_held` after about 30 s; continued, it stops by close and a later close resumes. A run paused in delivery after its seal still holds the lock: close replies `run_still_held` with the auditor's seal, never treating the seal as a stop. | `seal_as_stopped` | `delivery.after_member:1=pause` |
| C16 | `c16.status-after-launch` (after launch) | Status in JSON and for people, with the same facts, and unchanged by elapsed time, after: a kill between turns, its continuation to a delivery (a changed delivered copy changes nothing) and close; an ordinary stop, a close killed after its request, awaiting confirmation and closed; a limit stop; a kill after the seal (`sealed_undelivered`, close delivers without a provider request); a partial delivery; a close with surrendered losses (`delivered.verified` false). | `ended_as_submitted`, `seal_as_delivered` | `run.between_turns:7=kill`, `close.after_requested=kill`, `seal.after_link=kill`, `delivery.member_write:answer.md=eio` |
| C17 | `c17.close-failures` (after launch) | After an ordinary ending, a failed preparation write and then failed seal-manifest and diagnostic writes each fail close `record_failed` with the original cause first, stated effects and retained locations, status `close_unfinished` between them; a close whose reply is lost does its work, status supplies the token, and a repeat re-presents the same attempt publishing nothing; confirming closes; every retained path still exists. | none | `prepared.write=eio`, `seal.manifest_write=eio`, `diag.write=eio`, `reply.write=epipe` |
| C18 | `c18.after-launch-custody` (after launch) | With the original question and materials removed after acceptance, every receipt item reads back before and after close; the archive holds only the 4.2 layout and keeps the superseded draft payload; the archived seal manifest is the delivered one. With the archive moved away, status and receipt refuse `archive_unavailable` without recreating it, and the package still verifies; restored, status is unchanged; an externally removed member changes nothing status reports and causes no copy. | none | none |

Linux-only parts (skipped with their reason elsewhere): everything observed
through the OFD lock (`run_held`, `run_active`, interruption with a free lock,
close waiting on a run, T13), `/proc` observations (`start_ticks`, `boot_id`),
the archive filesystem allowlist and byte-string names. The timing gates apply
to the native architecture only.

### Pre-launch expectations of the full interface

The manager-foundation cases (`cases_foundation.py`) check the pre-launch side
of the interface that run, delivery and close extend: status data has its
members in the 5.6 order, with `runs.holder`, `allowances` (null before
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

## `acceptance.sh`: the scripted acceptance tier

```sh
sh apparatus/acceptance.sh "$PWD/.scratch/acceptance-NN"  # from the repository root; NN not yet used
```

One container suite runs the whole driver on Linux aarch64 and x86_64 (on the
development Mac, aarch64 natively and x86_64 under Rosetta), offline. It needs
the toolchain images and `service/vendor` from `step2.sh`, and pulls the pinned
python image (its only network use). It archives `service`, `apparatus` and
`docs` from `HEAD` (the driver's self-test compares its pinned texts and
examples with `docs/`), and for each architecture, offline:

1. builds the release binary, the test binary and the glibc control, each in
   its own target folder;
2. checks that both musl binaries are static and the glibc build is not, that
   `cmp` tells the release and test binaries apart, and that only the test
   binary contains the six test-only variable names of INTERFACE Appendix C;
3. in the pinned python image with `--network none` (loopback only), as an
   unprivileged user, with the binaries mounted read-only and archives and
   homes on the container's own disk, runs the driver's `--self-test`, then
   every case with `--network-isolated --require-all-controls`: every Appendix
   C.2 sabotage control must be assigned to a case and fire, and every driver
   control must fire. The timing gates (startup, `status` and `help`; protocol
   calls) are on only for the native architecture; Rosetta's home cache is
   recorded as an emulator artifact.

`host/DONE` reports `failures=N`; `host/SUMMARY` gives the self-test line and
the driver's counts per architecture; `driver-<arch>/evidence/` holds the
driver's full results, and `driver-<arch>/selftest.stdout` its self-test.

ACCEPTANCE also requires the scripted tier natively on WSL2, from a handoff
package of the same binary, driver and fake provider; no script here builds or
runs that package.

## Evidence retention

Evidence folders under `.scratch/` follow "Evidence and retention" in
[DEVELOPMENT.md](../DEVELOPMENT.md#evidence-and-retention). After a run of
`acceptance.sh` or `step2.sh`, `qualified.py extract` reads it into the
qualification record (`--suite acceptance` or `--suite toolchain`); commit
`qualified.json` and `qualified.md` together. `qualified.py candidates` lists
the folders that nothing keeps, under the rules in DEVELOPMENT.md, as removal
candidates; removal is by hand, and only after a run that exits 0.
