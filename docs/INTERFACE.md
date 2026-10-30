# Stewart interface specification

This is the exact interface of the Rust audit service: the manager CLI, the
archive and its records, the run adapter and the auditor's tools. It
instantiates [CONTRACTS.md](../CONTRACTS.md), which remains the behavioral
authority, and is exercised by [ACCEPTANCE.md](../ACCEPTANCE.md). The question
families, their instruction texts and the renderer are specified in
[QUESTION-FORMS.md](QUESTION-FORMS.md).

Status: specified, not implemented. Where this document and CONTRACTS differ,
CONTRACTS wins and this document is corrected. Linux is the only platform; the
filesystem calls named here are Linux calls.

Examples use illustrative identifiers. Tests match identifiers, digests, times
and paths by their stated patterns and every other value exactly, except prose:
`message`, `why`, `summary` and help text are checked for presence and
relevance, not exact bytes. The pinned texts in QUESTION-FORMS are exact.

## 1. Conventions

### 1.1 Versions

Each versioned thing has its own identifier. A change to one never redefines
another.

| Identifier | Names |
| --- | --- |
| `stewart.reply/1` | Reply envelope for manager JSON and auditor tool results |
| `question/1` | Front matter grammar of `question.md` |
| `stewart.record/1` | Archive record header (4.3) |
| `stewart.preparation/1`, `stewart.arrangement/1`, `stewart.receipt/1` | Manager preparation, pinned arrangement, acceptance receipt |
| `stewart.answer/1`, `stewart.return/1` | Structured answer, return manifest |
| `open-inquiry/1`, `inquiry-framing/1`, `comparison/1` | Families: instructions, recording tools, coverage sections |
| `stewart.orientation/1`, `stewart.render/1` | Auditor orientation text; Markdown renderer |
| `utf8-text/1` | The material reader: exact UTF-8 bytes, no transformation |

The writer is identified separately, by the SHA-256 of the executable (4.7).

### 1.2 Strict control JSON

Every JSON value Stewart interprets as control data is decoded strictly:
auditor tool inputs, archive records read back, and the JSON that tests send.
Provider response envelopes are captured raw and decoded tolerantly (6.2); the
`input` object of each `tool_use` block inside them is decoded strictly from its
raw bytes.

- UTF-8 only; no byte-order mark; one top-level value; nothing after it except
  JSON whitespace.
- Objects: a key repeated at any depth is refused, comparing keys after escape
  decoding, so `"a"` and `"\u0061"` are the same key. Unknown keys are refused.
  Required keys must be present.
- Strings: escapes decode to Unicode scalar values; a lone surrogate escape is
  refused. NUL (`\u0000`) is refused in every control string.
- Booleans are the literals `true` and `false`. A string `"true"` is a type error.
- Integers: no sign other than none, no leading zero, no fraction or exponent,
  within the field's published bound. A number that is not an integer is refused.
- Nesting depth is at most 16. Bounds on sizes are per field and per input.

A refusal names the JSON pointer of the defect (`/citations/2/start`), the rule
and, for an unknown key, the expected keys. The raw input was captured before
decoding (C14), and the refusal says so.

### 1.3 Reply envelope

Manager commands given `--json` write exactly one JSON object to stdout. Progress
and incidental diagnostics go to stderr. Without `--json` the same result is
printed for people. Raw readback (`receipt --read`) is the one exception: stdout
carries only the bytes (5.5).

```json
{"schema": "stewart.reply/1", "operation": "prepare", "outcome": "completed",
 "effects": {"preparation": "recorded"}, "next": [], "data": {}}
```

`outcome` is `completed`, `refused` or `failed`. These describe the invocation
only, never an audit or an answer. The envelope's keys, in this order:

| Field | Present | Meaning |
| --- | --- | --- |
| `schema` | always | `stewart.reply/1` |
| `operation` | always | The command or tool name |
| `outcome` | always | `completed`, `refused` or `failed` |
| `reason` | refused, failed | Stable identifier (Appendix A). Tests assert on it. |
| `message` | refused, failed | One or two plain sentences: what Stewart could not do and why. |
| `effects` | always | Operation-specific facts (1.4), on completed replies too. |
| `retained` | manager refused or failed | Archive locations holding attempts, partials and diagnostics: every location this invocation created and kept, each directory it created (a capture attempt, a preparation, a run directory, a delivery package) and each file it created in a directory it did not create (an entry payload, a seal manifest, a delivery plan, its diagnostic when that was written); and, on `log_damaged`, the log directory. Log records and stage files are not listed: the log holds the records, and status reports a stage file without its record as an interrupted publication (4.3). |
| `causes` | failed, or `effects.diagnostic` is `reported_only` | The original cause first, then any reporting failure. |
| `next` | always | Supported next calls, each with an explanation (1.5). May be empty. |
| `data` | completed; refused or failed when useful | Operation data, such as the current entry handle on a stale target. |

`next` is always this top-level field, never a member of `data`. On the wire a
reply is compact JSON: no whitespace between tokens, keys in the order above.
Examples in this document are spaced for reading.

Auditor tool results use the same envelope in the first text block of the
`tool_result`, without `retained` and without host paths (7.1).

### 1.4 Effects

Every reply carries `effects`, including a completed one. Values come from this
closed set.

| Key | Values |
| --- | --- |
| `reference` | `none`, `created`, `unknown` |
| `preparation` | `none`, `recorded`, `unknown` |
| `attempt` | `none`, `recorded`, `partial`, `unknown` |
| `acceptance` | `absent`, `accepted`, `unknown` |
| `run` | `not_started`, `started`, `ended`, `still_held`, `unknown` |
| `answer` | `unchanged`, `changed`, `unknown` |
| `seal` | `none`, `recorded`, `existing`, `unknown` |
| `delivery` | `none`, `failed`, `partial`, `verified_with_losses`, `verified`, `unknown` |
| `closure` | `none`, `requested`, `unfinished`, `complete`, `unknown` |
| `raw_capture` | `recorded`, `failed`, `not_applicable` |
| `diagnostic` | `durable`, `reported_only` |

Each operation reports exactly these keys:

| Operation | Effect keys |
| --- | --- |
| `new` | `reference` |
| `prepare` | `preparation` |
| `commission` | `acceptance`, `attempt` |
| `receipt`, `status` | none: `effects` is the empty object |
| `run` | `run`, `answer`, `seal`, `delivery` |
| `close` | `run`, `seal`, `delivery`, `closure` |
| `record_<kind>`, `record_artifact`, `replace`, `delete` | `answer`, `raw_capture` |
| `submit` | `seal`, `raw_capture` |
| `list`, `read`, `search`, `what_am_i_working_with`, auditor `prepare` | `raw_capture` |

`diagnostic` is added to any of them when the operation wrote, or tried to
write, a diagnostic (4.8).

`unknown` is used whenever Stewart cannot establish the fact, including after a
failure partway through publication. It is never replaced by the absent value.

For `run`, `close` and the auditor tools the values mean:

| Key | Meaning |
| --- | --- |
| `run` | `not_started`: no placement has started; `started`: this run's placement started and its ending could not be recorded; `ended`: no placement is live, because each has a recorded ending or its process is gone with the active lock free (the next `run` or `close` records that ending); `still_held`: a placement still holds the active lock |
| `answer` | `changed`: this invocation recorded at least one entry; `unchanged`: it recorded none |
| `seal` | `none`: no seal exists; `recorded`: this invocation published the seal; `existing`: a seal existed before it |
| `delivery` | The outcome (8.3) of the newest delivery attempt this invocation made or presented; on a refusal, which makes and presents nothing, the outcome of the newest recorded attempt; `none` when there is no such attempt. An attempt that ended `name_taken` is reported `failed`. |
| `closure` | `none`: no close requested; `requested`: this invocation published `close_requested` and its reply is `failed` (its other effects say what else it established); `unfinished`: requested and not closed, otherwise; `complete`: closed |
| `raw_capture` | `recorded`: the call capture (4.5) was written before the call ran; `failed`: it could not be, and the call did not run |

### 1.5 Next calls

Manager `next` items are `{"argv": [...], "why": "..."}`. Auditor `next` items
are `{"tool": "...", "input": {...}, "why": "..."}`. They are suggestions under
existing authority, never instructions to repeat a mutation blindly. Where the
manager has a choice, such as `run` against `close`, both appear. There is no
`retryable` flag. Every suggested manager `argv` begins with the recorded
writer path (4.7), never a bare `stewart`; examples use `/usr/local/bin/stewart`.

### 1.6 Exit status

| Code | Meaning |
| --- | --- |
| 0 | Completed, including an unfinished close. For `run`: the placement ended and its ending is recorded, other than interrupted. |
| 2 | Usage: the arguments could not be parsed. No operation began. |
| 3 | Refused. |
| 4 | Failed; `effects` states what is known. |
| 5 | `run` only: the placement was interrupted and recorded (outcome `completed`); `run` may continue it. |

A missing reply or a process killed before replying is unknown, not a code.

## 2. Identifiers, the reference and handles

### 2.1 Store and audit identifiers

A store identifier is `s` followed by 16 lowercase base32 characters
(`a`–`z`, `2`–`7`) encoding 80 random bits from `getrandom`. An audit identifier
has the same form with the prefix `a`. Both are created once and recorded.

### 2.2 The manager reference

```
stw1:<audit-id>:<store-id>:<encoded archive root>
stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/home/ana/stewart-archive
```

The encoded root is the absolute archive root path. Every byte outside
`A–Z a–z 0–9 / . _ -` is written `%XX` (uppercase hex), so the reference is one
shell word. The root must be valid UTF-8, absolute, without `.`, `..`, empty
components or a trailing `/`. On every use Stewart opens the root, reads its
store marker, verifies the store identifier and then finds the audit by its
identifier. The reference is never used as a path to records. A different store
at that path is `archive_replaced`; a missing path is `archive_unavailable`.

### 2.3 Handles

Handles are opaque strings with a readable prefix and a check suffix. The check
is the first 6 characters of the lowercase RFC 4648 base32 encoding (`a`–`z`,
`2`–`7`) of SHA-256 over
`stewart.handle/1\0<store>\0<audit>\0<kind>\0<object>\0<binding>`.
`<kind>` is the kind's name in the binding table below, `<object>` is the handle
without its final `.<check>` (`mp2`, `e3.v2`, `loss.answer-md`), and
`<binding>` is what that kind binds: its parts are joined with `\0`, digests
written as lowercase hex and integers in decimal. The check binds the handle to
its store, audit, purpose and exact object, so neither a manager nor an auditor
can construct a valid handle for an object it has not been given. The suffix
prevents accidental construction; it is not an authentication mechanism.

| Kind | Pattern | Example | Holder |
| --- | --- | --- | --- |
| Manager preparation | `mp<n>.<check>` | `mp2.k4q7xa` | manager |
| Entry version | `<id>.v<version>.<check>` | `e3.v2.k7q4m2` | auditor |
| Auditor preparation | `ap<n>.<check>` | `ap4.x6h2kq` | auditor |
| Prepared view | `<auditor preparation>/rendering` or `/selection` | `ap4.x6h2kq/rendering` | auditor |
| Seal | `seal.<check>` | `seal.r2m6vd` | both |
| Confirmation | `cf<n>.<check>` | `cf1.h3d7ws` | manager |
| Loss | `loss.<member token>.<check>` | `loss.answer-md.p6w2ze` | manager |
| List, search and page cursors | `ls.<position>.<check>`, `sc.<position>.<check>`, `pg.<position>.<check>` | `pg.64.m3qz7a` | auditor |

An entry's `id` is the string `e<n>`, numbering entries from 1 in order of
creation. A loss's member token is the entry ID of an unproduced entry, or a
member file name with `.` replaced by `-` (`answer.md` gives `answer-md`). A
cursor's `<position>` is opaque to callers. In a confirmation `cf<n>`, `n` is the
delivery attempt.

| `<kind>` | Binds |
| --- | --- |
| `mp` | SHA-256 of its `prepared` log record |
| `entry` | SHA-256 of its `entry` log record |
| `ap` | SHA-256 of `prepared/<n>/answer.json`, SHA-256 of `prepared/<n>/answer.md`, and the answer revision |
| `seal` | SHA-256 of the return manifest |
| `cf` | SHA-256 of the return manifest and of the attempt's `delivery_ended` record |
| `loss` | SHA-256 of the return manifest and of the failure record (8.4) |
| `sc` | SHA-256 of the search text; SHA-256 of the scope searched, its source names in search order, each followed by LF; and the position |
| `pg` | The bound answer revision and the position |
| `ls` | SHA-256 of the material index and the position |

A handle of the wrong kind, store or audit, or with a wrong check, is refused
as `handle_invalid` without revealing whether a similar object exists.

### 2.4 Names that are not handles

Material and question sources are names, not handles. The auditor and the
manager use the same names: `question` for the question body and
`materials/<public name>` for each material (`materials/src/a.py`). A name
reaches only captured material that is already in the auditor's world, so
constructing one grants nothing. Names are exact; a near miss is refused with
the closest existing names as hints, never normalized.

Receipt items are named `question-file`, `question-body`, `arrangement`,
`arrangement-readable` and `materials/<public name>`.

## 3. The submission folder

### 3.1 Layout

The folder has exactly two entries: `question.md` and `materials/`. If either is
missing, prepare refuses (`folder_incomplete`), naming it. Anything else at the
root is refused at prepare (`unexpected_root_entry`), naming the entry and
suggesting either moving it under `materials/` or out of the folder.

### 3.2 Front matter (`question/1`)

`question.md` starts with front matter, followed by the question body.

```
---
stewart: question/1
# Question family: open-inquiry, inquiry-framing or comparison.
# Run `stewart help forms` to read each family's instructions.
family: open-inquiry
# Provider model used for every run of this audit.
model: claude-opus-5-5
# Existing directory in which Stewart creates the return package.
destination: /home/ana/returns
# Cumulative limits across all runs, from the provider's usage reports.
limit-turns: 200
limit-input-tokens: 20000000
limit-output-tokens: 400000
---
Audit our app to make sure there are no bugs.
```

Grammar:

- The file may begin with one UTF-8 byte-order mark. The next bytes are `---`
  and a line ending.
- Line endings are LF or CRLF. The first line's ending sets the ending for the
  whole front matter; a different ending inside it is refused.
- Each following line until the closing `---` line is a field, a comment (first
  byte `#`) or empty.
- A field is `key: value`: the key, one colon, one space and a value running to
  the line ending. The value is non-empty and has no leading or trailing
  whitespace.
- The body is every byte after the closing `---` line's ending. The auditor
  receives exactly these bytes. A body with no non-whitespace character is
  refused (`question_empty`), because the provider cannot carry an empty or
  blank text block; the refusal is mechanical and says so.
- Missing or malformed `---` delimiters, mixed line endings, and a duplicate or
  unknown key are refused as `front_matter_invalid`, naming the line.

Fields:

| Key | Required | Value |
| --- | --- | --- |
| `stewart` | yes | Exactly `question/1` |
| `family` | yes | `open-inquiry`, `inquiry-framing` or `comparison` |
| `model` | yes | 1–128 characters from `A–Z a–z 0–9 . _ : -` |
| `destination` | yes | Absolute UTF-8 path, at most 1,024 bytes, no control characters |
| `limit-turns` | yes | Integer 1–10,000 |
| `limit-input-tokens` | yes | Integer 1–2,000,000,000 |
| `limit-output-tokens` | yes | Integer 1–200,000,000 |
| `inquiry` | no | Manager's label, 1–128 characters, no control characters |
| `varies` | no | A `stw1:` reference; recorded as the manager's attributed note |

Each key appears at most once. Unknown keys are refused (`front_matter_invalid`)
with the nearest known key. Prepare refuses a missing required key
(`setting_missing`), an invalid value (`setting_invalid`), a destination that
does not exist or is not a directory (`destination_invalid`), and a destination
that overlaps the folder or archive (`location_overlap`). The `varies` reference
is not resolved; it is the manager's note about its inquiry.

The scaffold created by `new` contains the front matter above with
`model: REPLACE-WITH-MODEL` and `destination: REPLACE-WITH-ABSOLUTE-DIRECTORY`,
a comment line `# Write your question below the closing --- line.`, an empty
body and an empty `materials/`. Prepare refuses the placeholders as invalid
values and the empty body as `question_empty`, naming what to edit.

### 3.3 Material scan

Prepare and commission scan through descriptors opened relative to the folder,
with `O_NOFOLLOW`. They classify entries with `fstatat(AT_SYMLINK_NOFOLLOW)` and
open regular files with `O_NONBLOCK`, rechecking the type on the open
descriptor. Bounds are enforced while scanning (CONTRACTS bounds table).

- Directories and regular files are admitted, including hidden names and empty
  ones. Symlinks, FIFOs, sockets and devices are refused unread
  (`unsupported_entry`).
- A directory whose device and inode equal the archive root's or the
  destination's is refused (`location_overlap`).
- A file that cannot be opened or read is refused (`source_unreadable`), naming
  the file and the error.
- Names are valid UTF-8 without control characters (U+0000–U+001F, U+007F–U+009F),
  at most 255 bytes per component, 32 components and 1,024 bytes per path. They
  are kept exactly.
- Content is valid UTF-8 with no NUL. A refusal names the file and the byte
  offset of the first invalid byte (`material_not_text`).
- Hard-linked files are admitted as separate names with separate captures.
- The index order is bytewise order of public names. Each material records size,
  SHA-256 and line count (number of LF bytes, plus one if the last byte is not LF
  and the file is non-empty).

Prepare also records the membership of files and directories and each file's
`mtime`. Commission checks against these records (5.4). No `ctime` is recorded
or compared anywhere, so a permission change alone never makes a selection
change (ACCEPTANCE C17).

## 4. The archive

### 4.1 Filesystem and permissions

The archive root is a directory on local ext4, xfs or btrfs, checked with
`statfs` at `new` and at every mutating operation. Others are refused
(`archive_filesystem_unsupported`), naming the observed type. Stewart creates
directories mode 0700 and files 0600. The root's path must have no symlink
components (`archive_path_symlink`). The archive, the preparation folder and the
destination never contain one another. This is checked by walking `..` from
each opened directory and comparing device and inode pairs, at `new`, at prepare
and at every delivery attempt (`location_overlap`).

### 4.2 Layout

```
<root>/
  STORE.json                    store marker
  audits/<audit-id>/
    REFERENCE.json              created by new
    active.lock                 empty; locked by intake, run or close (4.6)
    log/<n>.json                the audit log (4.4)
    stage/                      fully written records before publication; kept
    prep/<n>/                   manager preparation: manifest.json, arrangement.json, arrangement.md
    intake/<attempt>/           captured bytes: q.bin, m0001.bin, …; receipt.json
    payload/                    entry bytes: <id>.v<version>.bin, one exclusive file per version (7.4)
    prepared/<n>/               a preparation of the answer: answer.json, answer.md (7.6, 8.1)
    seal/manifest-<k>.json      return manifest written at seal (8.2)
    runs/<n>/                   per placement: requests, responses, attempts, calls, results (4.5)
    delivery/<attempt>.json     delivery plan (8.3)
    diag/                       diagnostics
```

Payload and capture file names are generated by Stewart. No manager or auditor
string becomes a path component.

### 4.3 Records

Every record is UTF-8 JSON with a header:

```json
{"record": "stewart.record/1", "kind": "accepted", "audit": "aqm3x7kd2hz5vw4ny",
 "writer": "3f1c…64 hex", "at": "2026-11-02T14:03:11.402Z", "body": {}}
```

`at` is UTC with milliseconds. It is an observation, never a deadline.

Records are never rewritten or removed. Two publication methods are used:

- **Exclusive file.** Open with `O_CREAT | O_EXCL | O_NOFOLLOW`, write, `fsync`,
  then `fsync` the directory. Used for payloads, captures, receipts, manifests,
  prepared files, raw exchanges and diagnostics, under the allocation rule below.
- **Linked record.** Write the complete record to a new file in `stage/`,
  `fsync` it, then `linkat` it to its final name and `fsync` the destination
  directory. `EEXIST` means the name is taken. The stage file stays as evidence.
  A record is visible under its final name only when complete, so readers never
  see a torn record. A stage file without a final name is reported as an
  interrupted publication, never as a record. Log records are staged in the
  audit's `stage/`; run records (4.5) in their run's `runs/<n>/stage/`.

A record ends with one LF. Payloads, raw captures (4.5), the answer files in
`prepared/<n>` (QUESTION-FORMS) and return manifests (8.2) are not
`stewart.record/1` records; each has its own layout.

Every numbered name outside `runs/` is claimed, never assumed free: `prep/<n>`,
`prepared/<n>`, `seal/manifest-<k>.json`, `intake/<attempt>`,
`delivery/<attempt>.json`, payload files (7.4) and the files in `diag/`. A file
is claimed with `O_EXCL` and a directory with `mkdirat`; on `EEXIST` the writer
advances to the next number. The log record that uses a claimed name names it.
Stage files are created with `O_EXCL` under random names. Names in `runs/`
follow 4.5.

A preparation directory, receipt, manifest, delivery plan or payload file that
no log record names is reported by status as an unpublished candidate, never as
a record. An auditor preparation is an inspection candidate by design: no log
record names it unless it is sealed, and status does not report it.

### 4.4 The audit log

The log is the order of everything that changes an audit's state. Its records
are `log/<n>.json` with `n` = 1, 2, 3, … written in decimal without padding.
Publishing a log record means claiming the next number with a linked record.
Each record's body carries `prev`, the SHA-256 of record `n-1`; `prev` is `null`
for record 1.

Readers list `log/`. The log is readable only if its names are exactly `1.json`
to `N.json`, every record decodes strictly (1.2) and the `prev` chain matches.
Otherwise the log is damaged. Every mutation then refuses with `log_damaged`;
close replies unfinished, naming the bad records, and never publishes `closed`
(5.8); status reports the damage (5.6). Stewart diagnoses the damage and never
repairs the log or restarts the audit.

To publish, a writer reads the log to its end, checks its preconditions against
that state, and links record `n+1`. On `EEXIST` it re-reads, re-checks and either
tries the next number or refuses with the state it found. This settles every
race with one rule: submit against close, edit against seal, commission against
close and run start against close each have exactly one order.

Log record kinds:

| Kind | Written by | Precondition (beyond writer and readable log) |
| --- | --- | --- |
| `reference` | new | Log empty |
| `prepared` | prepare | No `accepted`, no `close_requested` |
| `intake_planned` | commission | A matching `prepared`; no `accepted`, no `close_requested`; no live intake |
| `intake_ended` | commission; the next commission's or close's reconciliation | Its `intake_planned` has no outcome |
| `accepted` | commission | Its `intake_planned` has no outcome; no `accepted`, no `close_requested` |
| `run_started` | run | `accepted`; authoring not ended (5.7); no `close_requested`; every earlier `run_started` has its `run_ended` |
| `entry` | auditor tools | The invocation's placement is the latest `run_started` and has no `run_ended`; no `seal`, no `close_requested` |
| `seal` | submit, close | No earlier `seal`; for submit, the preparation's revision is current and no `close_requested`; for close, after its `close_requested` |
| `run_ended` | run; the next run's or close's reconciliation | Its `run_started` has no `run_ended` |
| `delivery_planned` | run, close | A `seal`; every earlier `delivery_planned` has its `delivery_ended` |
| `delivery_ended` | run; close, including its reconciliation | Its `delivery_planned` has no `delivery_ended` |
| `notice` | run | No earlier `notice` of the same type; its placement has no `run_ended` |
| `close_requested` | close | None earlier |
| `closed` | close | `close_requested`; none earlier; close's own conditions (5.8) |

`entry` covers add, replace and delete. The answer revision is the number of
`entry` records so far. The current selection at a log position is every entry
added and not since deleted, at its latest version, in order of first creation.

The launch point is the first `run_started`. Before it, close creates no answer.
After it, close seals the recorded selection if no seal exists. A crash between
`run_started` and the first provider request still counts as launched. Close then
seals an empty selection with manager attribution, which is an honest empty
return.

#### Record bodies

A body is a compact JSON object whose keys appear in the order listed, after
`prev`, which comes first in every body. A key described as "or null" is always
present. Names such as `log/9.json`, `runs/2` or `payload/e2.v2.bin` are relative
to the audit directory. The manager-foundation kinds:

| Kind | Body keys after `prev` |
| --- | --- |
| `reference` | `file`, `file_sha256`, `folder`, `writer` {`path`, `sha256`} |
| `prepared` | `prep`, `manifest`, `manifest_sha256`, `arrangement_sha256`, `readable_sha256`, `settings` {`family`, `model`, `destination`, `limits` {`turns`, `input_tokens`, `output_tokens`}, then `inquiry` and `varies` only when given}, `question` {`file_bytes`, `file_sha256`, `body_bytes`, `body_sha256`}, `materials` {`count`, `bytes`} |
| `intake_planned` | `attempt`, `prepared` (the handle), `prep`, `declaration` {`i_am_finished`}, `captures` [{`item`, `file`}], `observations` |
| `intake_ended` | `attempt`, `outcome`, `recorded_by` (`commission` or `close`), `message`, `cause` ({`operation`, `error`} or null), `changes` ({`added`, `removed`, `changed`} or null) |
| `accepted` | `attempt`, `prepared`, `prep`, `receipt` (`intake/<attempt>/receipt.json`), `receipt_sha256` |
| `close_requested` | `flags` {`confirm`, `surrender`, `destination`}: the options of the close call that published it, `null` or `[]` when absent; `observations` |

`observations` is {`pid`, `uid`, `host`, `boot_id`}: the process ID, the real
user ID, the host name and the kernel boot ID
(`/proc/sys/kernel/random/boot_id`), `host` and `boot_id` null when unavailable.
They record what Stewart observed about an invocation, never who the manager is.
`close_requested` has this body in every state; the selection close seals is
determined by its log position.

**`run_started`**

```json
{"prev": "…", "run": 2, "continuing": true, "dir": "runs/2", "arrangement_sha256": "…",
 "provider": {"base_url": "https://api.anthropic.com", "override": false, "proxy": null,
              "anthropic_version": "2026-10-21"},
 "observations": {"pid": 4182, "start_ticks": 912873, "uid": 1000, "host": "ana-laptop", "boot_id": "6c1f…"}}
```

`run` is the placement number and `continuing` is true when it is above 1.
`base_url` is the provider base in use, `override` whether
`STEWART_PROVIDER_URL` supplied it, and `proxy` the `HTTPS_PROXY` value in use
or null (6.1). `start_ticks` is field 22 of `/proc/self/stat`, the process start
time in clock ticks since boot.

**`run_ended`**

```json
{"prev": "…", "run": 2, "ending": "interrupted", "cause": "provider_unavailable", "recorded_by": "run",
 "provider": {"status": 529, "error_type": "overloaded_error", "request_id": "req_011…", "request": 6, "attempt": 4},
 "requests": 6, "attempts": 9,
 "usage": {"turns": {"reported": 5, "estimated": 0}, "input_tokens": {"reported": 412003, "estimated": 0},
           "output_tokens": {"reported": 18201, "estimated": 0}},
 "notices": [{"type": "near_limit", "record": "log/40.json", "sent": "not_sent"}],
 "seal": null, "message": "The provider was unavailable on 4 attempts of request 6."}
```

- `ending` and `cause` are from 6.5; `cause` is null for an ending without one.
- `recorded_by` is the operation that published the record, `run` or `close`,
  as for `intake_ended`. A placement whose process was gone is recorded by the
  next `run` or by `close` with cause `process_gone`.
- `provider` is the last attempt's facts when the cause is
  `provider_unavailable` or `provider_rejected`, else null. `status`,
  `error_type` (the error body's `error.type`) and `request_id` (the
  `request-id` header, else the error body's `request_id`) are null when not
  observed.
- `requests` counts the placement's complete request captures and `attempts` its
  attempt records (4.5). `usage` is the placement's charge, split as 6.4 states.
- `notices` lists each `notice` record published during the placement; `sent` is
  `sent`, `not_sent` or `unknown` (6.4).
- `seal` is the `seal` record published during the placement, or null.
  `message` is prose.

**`entry`**

```json
{"prev": "…", "action": "replace", "tool": "replace",
 "invocation": {"run": 2, "tool_use_id": "toolu_01A…", "call": 14},
 "target": {"id": "e2", "version": 1, "record": "log/9.json"},
 "id": "e2", "version": 2, "kind": "record_observation", "label": "restart duplicate",
 "payload": {"file": "payload/e2.v2.bin", "sha256": "…", "size": 132}, "encoding": null,
 "citations": [{"source": "materials/a.py", "start": 50, "end": 119,
                "stewart": {"name": "materials/a.py", "sha256": "…", "lines": [4, 6]}}],
 "revision": 8}
```

| Key | add | replace | delete |
| --- | --- | --- | --- |
| `action` | `add` | `replace` | `delete` |
| `tool` | the record tool | `replace` | `delete` |
| `invocation` | `run`, `tool_use_id` and `call`: the placement, the block's ID and its call number (4.5) | same | same |
| `target` | null | the replaced version: `id`, `version` and the `record` that created it | the removed version, likewise |
| `id`, `version` | the new ID, 1 | the target's ID, its version + 1 | null |
| `kind` | the tool name (`record_observation`, `record_artifact`) | the target's kind | null |
| `label` | as given; `""` when omitted | as given | null |
| `payload` | `file`, `sha256` and `size` of the stored bytes (7.4) | same | null |
| `encoding` | `utf-8` or `binary` for an artifact (7.4); null otherwise | same | null |
| `citations` | the recorded citations (7.3), `[]` when none; null for an artifact | same | null |
| `revision` | the resulting answer revision | same | same |

An entry version's handle binds the SHA-256 of the `entry` record that created
it (2.3), so no record contains its own handle.

**`seal`**

```json
{"prev": "…", "actor": "auditor", "prepared": 3, "answer_sha256": "…", "rendering_sha256": "…",
 "revision": 7, "manifest": "seal/manifest-1.json", "manifest_sha256": "…",
 "invocation": {"run": 2, "tool_use_id": "toolu_01B…", "call": 31}}
```

`actor` is `auditor` (submit) or `manager` (close). `prepared` names the sealed
`prepared/<n>` and the two digests are its files'; `rendering_sha256` is null
when the rendering is unproduced (8.1). `invocation` is null for a manager seal.

**`notice`**

```json
{"prev": "…", "type": "near_limit", "run": 2, "request": 9, "text": "Allowance notice: 40 turns, …",
 "remaining": {"turns": 40, "input_tokens": 3900000, "output_tokens": 79000}}
```

`type` is `reminder` or `near_limit`. `request` is the request of placement
`run` planned to carry the text, and `text` the exact text. `remaining` is null
for the reminder.

**`delivery_planned`**

```json
{"prev": "…", "attempt": 3, "plan": "delivery/3.json", "plan_sha256": "…", "by": "close",
 "destination": "/home/ana/returns2", "destination_source": "replacement",
 "package": "stewart-return-aqm3x7kd2hz5vw4ny-003", "replaces": 2}
```

`by` is `run` or `close`. `destination_source` is `commissioned`, or
`replacement` for a destination given with `--destination` or inherited from a
replacement attempt (5.8). `replaces` is as 8.3 states.

**`delivery_ended`**

```json
{"prev": "…", "attempt": 1, "outcome": "verified_with_losses", "recorded_by": "close", "cause": null,
 "manifest_sha256": "…", "package": "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001",
 "members": [{"name": "manifest.json", "role": "manifest", "written": true, "verified": true, "failure": null},
             {"name": "answer.json", "role": "answer", "written": true, "verified": true, "failure": null}],
 "losses": [{"member": "e3", "role": "entry", "failure": "damaged", "stage": "seal"},
            {"member": "answer.md", "role": "rendering", "failure": "not_rendered", "stage": "seal"}]}
```

- `recorded_by` is `run` or `close`. An attempt whose process was gone is
  recorded by close as `failed` with cause
  `{"operation": "deliver", "error": "process_gone"}`.
- `cause` is null unless the outcome is `failed`, `partial` or `name_taken`.
  `manifest_sha256` is the seal's. `package` is the package directory's
  absolute path, or null when none was created.
- `members` follows the plan (8.3); it and `losses` are null when membership is
  unknown. A member's `failure` is null, `source_missing`, `source_unreadable`,
  `source_damaged`, `write_failed`, `not_verified` or `not_attempted`.
- `losses` are the members the return owes but this attempt could not supply:
  each unproduced at seal (`stage: "seal"`, with the manifest's failure), and
  each the archive could not supply (`stage: "delivery"`, failure `missing`,
  `unreadable` or `damaged`). `member` is the entry ID of an unproduced entry,
  else a member name.

**`closed`**

Before launch the body is `before_launch` (true), `accepted` and `outcome`
(`closed_without_acceptance` or `closed_after_acceptance_before_launch`). After
launch:

```json
{"prev": "…", "before_launch": false, "accepted": true, "outcome": "closed_with_surrendered_losses",
 "seal": {"record": "log/22.json", "actor": "manager", "manifest_sha256": "…"},
 "delivery": {"attempt": 1, "record": "log/24.json", "outcome": "verified_with_losses",
              "package": "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001"},
 "placement": "confirmed", "confirmation": "cf1.h3d7ws",
 "surrendered": [{"loss": "loss.e3.p6w2ze", "member": "e3", "role": "entry", "failure": "damaged", "stage": "seal"},
                 {"loss": "loss.answer-md.t4n6qa", "member": "answer.md", "role": "rendering", "failure": "not_rendered", "stage": "seal"}],
 "runs": 2}
```

`outcome` is `closed_delivered` when nothing was surrendered, else
`closed_with_surrendered_losses`. `delivery` is the attempt whose placement was
confirmed. `placement` is `confirmed` (by `--confirm`) or
`delivered_before_close` (5.8); `confirmation` is the token given, or null.
`surrendered` lists each loss given up with `--surrender`; `runs` counts the
placements.

### 4.5 Run captures

Each placement `n` has the directory `runs/<n>`, created with `mkdirat` right
after its `run_started` is published. Only the holder of the active lock writes
there, so names in it are assigned in sequence rather than claimed: a name that
already exists, including `runs/<n>` itself, is an archive write failure (6.5),
never overwritten or skipped.

| Name | Form | Written |
| --- | --- | --- |
| `request-<k>.json` | Raw capture in the layout below | Before the first attempt of request `k` |
| `response-<k>-<a>.bin` | Raw: the body of attempt `a` as received | When attempt `a` received a status line, once its body ended or was cut off |
| `attempt-<k>-<a>.json` | Linked record, kind `provider_attempt` | When attempt `a` ends |
| `call-<c>.json` | Raw: the exact bytes of one `tool_use` block | Before the block is executed |
| `result-<c>.json` | Linked record, kind `tool_result` | After the block is executed, before the next block |
| `stage/` | Stage files of this placement's linked records | Created with the directory |

`k` numbers the placement's requests from 1, `a` the attempts of one request
from 1 (6.6), and `c` the `tool_use` blocks the placement executes, in execution
order, from 1. A raw capture is an exclusive file that a kill can leave cut off.
The record written after a response or call capture binds its size and SHA-256;
a request capture shows its own completeness by its layout. Raw captures are
decoded tolerantly, never as control records.

**Request capture.** One line of compact JSON, then an LF:

```
{"request":<k>,"max_tokens":<T>,"body_bytes":<B>,"body_sha256":"<hex>","appended":[<A_k>]}
```

`A_k` is the messages request `k` appends (6.2), exactly as they appear in its
body, joined by commas. The body of request `k` is exactly

```
{"model":<M>,"max_tokens":<T>,"system":<S>,"tools":<U><X>,"messages":[<A_1>,<A_2>,…,<A_k>]}
```

`M`, `S` and `U` are the bytes of the arrangement's `model`, `system` and `tools`
values; `X` is, for each member of its `request_extra` object, a comma followed
by that member's bytes (nothing in this release); and the `A_i` are joined by
commas. There is no other whitespace and no trailing LF. `B` and the digest let
a reader check the reconstruction. A request capture that does not end with
`]}` and an LF was cut off, and its request was never sent.

**Response capture.** The body as received, after removing chunked transfer
coding and nothing else, and at most 32 MiB of it. No byte is decoded before the
capture is written.

**Attempt record** (`provider_attempt`):

```json
{"request": 6, "attempt": 2, "started_at": "…", "ended_at": "…", "elapsed_ms": 812, "timeout_seconds": 600,
 "request_written": "complete", "outcome": "http_error", "status": 529,
 "headers": {"content-type": ["application/json"], "request-id": ["req_011…"], "retry-after": ["0"]},
 "response": {"file": "response-6-2.bin", "bytes": 105, "sha256": "…", "complete": true},
 "error": {"type": "overloaded_error", "message": "Overloaded", "request_id": "req_011…"},
 "stop_reason": null, "model": null, "usage": null,
 "charged": {"basis": "none", "turns": 0, "input_tokens": 0, "output_tokens": 0},
 "problem": null, "then": "retry", "delay_ms": 0}
```

- `request_written` is `none`, `partial` or `complete`: how much of the request
  reached the connection. `timeout_seconds` is the timeout in force.
- `outcome` is one of 6.6's. `status` is the HTTP status, or null without a
  status line.
- `headers` holds exactly `content-type`, `request-id` and `retry-after`,
  matched without regard to case: for each, the values received in order, `[]`
  when absent. Leading and trailing spaces and tabs are removed, and each byte
  outside 0x20–0x7E is written `%XX` in uppercase hex.
- `response` is null when no status line was received. Its `complete` is false
  when the body was cut off or exceeded 32 MiB.
- `error` holds the error body's `error.type`, `error.message` (cut to at most
  1,024 bytes on a character boundary) and `request_id`, each null when absent,
  when the body decodes as an error body (6.2); else null.
- `stop_reason`, `model` and `usage` come from a decoded message, `usage` as
  {`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`,
  `output_tokens`} with an absent or null cache count written 0; else null.
- `charged` is what the attempt added to the allowances (6.4), with `basis`
  `reported`, `estimated` or `none`.
- `problem` is prose saying why a response was undecodable, else null.
- `then` is the decision about this attempt: `use` (its response was decoded
  and acted on, even when the placement then ends because of its stop reason),
  `retry` (another attempt follows after `delay_ms` milliseconds) or `end` (no
  response is used and the placement ends). `delay_ms` is null unless `then` is
  `retry`.

**Call capture.** The bytes of the `tool_use` block in the response body, from
its `{` to its `}`.

**Result record** (`tool_result`):

```json
{"call": 14, "request": 6, "attempt": 2, "block": 3, "call_file": "call-14.json", "call_bytes": 412,
 "call_sha256": "…", "tool_use_id": "toolu_01A…", "tool": "replace", "input_sha256": "…",
 "replay_of": null, "outcome": "completed", "reason": null, "revision": 8, "log_record": "log/31.json",
 "is_error": false, "content": [{"type": "text", "text": "{\"schema\":\"stewart.reply/1\",…}"}]}
```

- `request`, `attempt` and `block` locate the block: element `block`, counted
  from 0, of the `content` of `response-<request>-<attempt>.bin`.
- `tool` is the block's `name` when it is a string, else null. `input_sha256` is
  the SHA-256 of the raw bytes of the block's `input` value, or null when it has
  none.
- `replay_of` is the call whose recorded result this one redelivers (6.3), or
  null.
- `outcome` and `reason` are the reply envelope's, `reason` null when completed.
  `revision` is the answer revision after the call. `log_record` is the `entry`
  or `seal` record the call published, or null.
- `is_error` and `content` are exactly what the `tool_result` block carries
  (7.1). The block sent is
  `{"type":"tool_result","tool_use_id":<ID>,"content":<content>,"is_error":<is_error>}`,
  where `<ID>` is `tool_use_id` written as in this record and `<content>` is the
  bytes of this record's `content` value.

**Access log.** The access log of ACCEPTANCE C6 is, over placements in order and
calls in order, every call capture whose block names `list`, `read` or
`search`, with its input and the `outcome` of its result record, or `unknown`
when that record is missing or unreadable. It includes refused calls and replays.

Re-entry's `receipts` come from `entry` records and its `latest_refusals` from
result records across placements (7.5). Status reports a file in a run's
`stage/` that no run record shares as an interrupted publication, never as a
record.

### 4.6 The active lock and liveness

`active.lock` is created by `new`. An intake or a run holds an open file
description lock (`F_OFD_SETLK`, write lock on the whole file) for its whole
life, including delivery. Close holds it for its seal and delivery work (5.8).
A second `run` that cannot take the lock refuses with `run_held`. Status, and
close before it takes the lock, test it with `F_OFD_GETLK`, which acquires
nothing. A held lock is current evidence of a live holder. A free lock together
with a `run_started` that has no `run_ended` is the evidence of an interrupted
placement. Elapsed time is never evidence. The kernel releases the lock when
the holder exits or is killed. The holder's process ID, start time
(`start_ticks`), host name, boot ID and invoking user ID are recorded in
`run_started` as observations (4.4).

### 4.7 The writer

`new` records the writer in `REFERENCE.json` as the SHA-256 of the running
executable, read through `/proc/self/exe`, and its resolved path. Every mutating
operation (prepare, commission, run, close and every auditor mutation) first
hashes its own executable. If the digest differs, the operation is refused with
`writer_mismatch`, naming the recorded path and digest. Receipt and status need
no particular writer and read any record whose schema they support.

### 4.8 Diagnostics

A failure is recorded in `diag/` before the reply is written. If the diagnostic
cannot be written, the reply carries both causes in `causes`, with `diagnostic`
set to `reported_only`. If the reply cannot be written either, the diagnostic
remains the account; later status reads it. Manager refusals are recorded the
same way. An auditor call's account is its result record (4.5); a failed
auditor call also writes a diagnostic, and a refused one does not.

### 4.9 Store marker

`STORE.json` holds the store identifier, the creation path, and the root's inode
and `statx` birth time at creation. It also records the `statfs` filesystem ID
and the device number as observations only; both can change across reboots, for
example on xfs, and neither is compared. On use, a different store identifier is
`archive_replaced`. A matching identifier with a different root inode or birth
time is reported as `archive_moved_or_copied`; status and receipt may read such
an archive, but mutating operations refuse it. A copy never acquires execution.

## 5. The manager CLI

### 5.1 Common rules

```
stewart new FOLDER [--archive ROOT] [--json]
stewart prepare REF [--json]
stewart commission REF HANDLE --i-am-finished [--json]
stewart receipt REF [--verify] [--json]
stewart receipt REF --read ITEM
stewart status REF [--json]
stewart status --archive ROOT [--json]
stewart run REF [--json]
stewart close REF [--confirm TOKEN] [--surrender LOSS]... [--destination DIR] [--json]
stewart help [commands | forms | limits | reader | close]
```

Arguments are exact; there are no abbreviations and no configuration files.
`STEWART_ARCHIVE` supplies the archive root for `new` only. Every other
command finds its archive through the reference. Paths given as arguments must
be absolute. Commands never select an audit by recency, current directory or
installation.

### 5.2 `new`

Creates a reference, and the archive or the scaffold when absent.

- The archive root comes from `--archive`, else `STEWART_ARCHIVE`, else the
  command is refused (`archive_unspecified`). An absent root is created, if its
  parent exists, with `STORE.json`. An existing empty directory is initialized.
  An existing store is used. Anything else is refused (`archive_not_a_store`).
- An absent folder is created with the scaffold (3.2). An existing folder is
  used without changing it; its shape is checked at prepare.
- The archive and folder must not overlap (4.1).
- If references in this archive already name this folder, the reply adds the
  notice `folder_already_referenced` listing them. A new reference is still
  created; another commission always needs its own reference.

```json
{"schema": "stewart.reply/1", "operation": "new", "outcome": "completed",
 "effects": {"reference": "created"},
 "next": [{"argv": ["/usr/local/bin/stewart", "prepare", "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/home/ana/stewart-archive"],
           "why": "Edit question.md and materials/, finish, then prepare."}],
 "data": {"reference": "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/home/ana/stewart-archive",
          "archive": "/home/ana/stewart-archive", "archive_created": false,
          "folder": "/home/ana/q/reminders", "scaffold_created": true,
          "writer": {"path": "/usr/local/bin/stewart", "sha256": "3f1c…"},
          "notices": []}}
```

### 5.3 `prepare`

Scans the folder, checks the mechanical intake rules, pins the arrangement and
returns a manager preparation handle. It accepts nothing and preserves no source
bytes. Its reply and records are the inspection: there is no preview command.

Precondition: no `accepted`, no `close_requested`. Records: `prep/<n>/manifest.json`,
`arrangement.json` (machine), `arrangement.md` (readable), then the `prepared`
log record binding their digests.

```json
{"schema": "stewart.reply/1", "operation": "prepare", "outcome": "completed",
 "effects": {"preparation": "recorded"},
 "next": [{"argv": ["/usr/local/bin/stewart", "commission", "stw1:…", "mp1.k4q7xa", "--i-am-finished"],
           "why": "Accept exactly this selection. Leave the folder unchanged until commission returns."}],
 "data": {"prepared": "mp1.k4q7xa",
          "question": {"file_bytes": 389, "file_sha256": "…", "body_bytes": 46, "body_sha256": "…"},
          "settings": {"family": "open-inquiry", "model": "claude-opus-5-5",
                       "destination": "/home/ana/returns",
                       "limits": {"turns": 200, "input_tokens": 20000000, "output_tokens": 400000}},
          "materials": {"count": 3, "bytes": 1428, "directories": ["materials"],
                        "files": [{"name": "materials/a.py", "size": 175, "sha256": "…", "lines": 8},
                                  {"name": "materials/requirements.txt", "size": 662, "sha256": "…", "lines": 9},
                                  {"name": "materials/supplied-report.txt", "size": 591, "sha256": "…", "lines": 6}]},
          "reader": {"id": "utf8-text/1", "transformations": "none"},
          "bounds": {"question_bytes": 262144, "files": 128, "file_bytes": 16777216, "total_bytes": 134217728,
                     "directories": 256, "path_bytes": 1024, "path_components": 32, "component_bytes": 255},
          "arrangement": {"sha256": "…", "readable": "/home/ana/stewart-archive/audits/aqm3…/prep/1/arrangement.md",
                          "machine": "/home/ana/stewart-archive/audits/aqm3…/prep/1/arrangement.json"}}}
```

Refusals: `folder_incomplete`, `front_matter_invalid`, `setting_missing`,
`setting_invalid`, `destination_invalid`, `question_empty`,
`unexpected_root_entry`, `unsupported_entry`, `location_overlap`,
`material_not_text`, `name_invalid`, `source_unreadable`, `bound_exceeded`
(naming the bound, the limit and the entry where it was exceeded),
`reference_already_accepted`, `reference_closed`, `log_damaged`. Effects:
`preparation`.

### 5.4 `commission`

`stewart commission REF HANDLE --i-am-finished` requests acceptance of the
prepared selection. Without `--i-am-finished` it is refused
(`affirmation_missing`) with no effects. The flag records the manager's
declaration that it has finished assembling the selection and will leave the
folder unchanged until commissioning returns. The declaration is recorded
separately from Stewart's observations.

Steps:

1. Find acceptance. If the log is damaged (4.4), refuse `log_damaged` with
   `acceptance: "unknown"`, naming the bad records. Stewart diagnoses the damage
   and never repairs the log or restarts the audit; the manager may restore its
   own storage or start a new reference. If `accepted` exists for this handle,
   return the recorded receipt with `data.already_accepted: true` and effects
   `acceptance: accepted`, `attempt: none` (this invocation made no attempt).
   This is the lost-reply case, and it holds even if the source has changed
   since. If
   `accepted` exists for another handle, refuse `reference_already_accepted`. A
   readable log without `accepted` is the evidence that acceptance is absent.
2. Take the active lock. If it cannot be taken, refuse `intake_in_progress`.
   Then reconcile: if an earlier `intake_planned` has no outcome, publish
   `intake_ended` with `outcome: "process_gone"` for it. Publish
   `intake_planned` naming the attempt, the handle, the declaration and the
   planned capture names.
3. Copy each file through descriptors into `intake/<attempt>/` as exclusive
   files. Before reading a source, check its size and `mtime` against prepare's.
   Check its device, inode, size and `mtime` on the open descriptor before and
   after reading it; they must not change. Compare each copy's SHA-256 with the
   prepared digest by reading the copy back.
4. Rescan the folder. Membership, and each file's device, inode, size and
   `mtime`, must equal those seen during the copy.
5. Write `intake/<attempt>/receipt.json` (exclusive) and publish `accepted`
   naming it and its digest. If `close_requested` took the slot, publish
   `intake_ended` with `outcome: "closed"` and refuse `reference_closed`.

A mismatch at steps 3–4 publishes `intake_ended` with `outcome: "selection_changed"`
and refuses with `selection_changed`, listing names added, removed and changed.
Correct the folder, prepare again and commission the new handle under the same
reference. The other endings are published the same way before the reply: a
source that cannot be opened or read refuses `source_unreadable`; a capture
that cannot be written or read back fails `capture_failed` or
`capture_unverified`; a receipt that cannot be written fails
`receipt_record_failed`. Captured files stay in every case. The `intake_ended`
outcomes are `selection_changed`, `source_unreadable`, `capture_failed`,
`capture_unverified`, `receipt_record_failed`, `closed` and `process_gone`.

```json
{"schema": "stewart.reply/1", "operation": "commission", "outcome": "completed",
 "effects": {"acceptance": "accepted", "attempt": "recorded"},
 "next": [{"argv": ["/usr/local/bin/stewart", "run", "stw1:…"], "why": "Start the audit; it needs what run_needs lists."},
          {"argv": ["/usr/local/bin/stewart", "close", "stw1:…"], "why": "End the commission without running it."}],
 "data": {"reference": "stw1:…", "accepted_at": "2026-11-02T14:05:40.118Z", "receipt_sha256": "…",
          "already_accepted": false,
          "checks": ["capture_digests_match_preparation", "source_identity_unchanged_during_copy",
                     "final_scan_matches_preparation"],
          "declaration": {"i_am_finished": true},
          "materials": {"count": 3, "bytes": 1428},
          "run_line": ["/usr/local/bin/stewart", "run", "stw1:…"],
          "run_needs": ["ANTHROPIC_API_KEY in the environment", "network access to the provider",
                        "runs in the foreground until the placement ends; callers with command timeouts should start it in the background"],
          "receipt_line": ["/usr/local/bin/stewart", "receipt", "stw1:…"]}}
```

```json
{"schema": "stewart.reply/1", "operation": "commission", "outcome": "refused",
 "reason": "selection_changed",
 "message": "materials/a.py changed after preparation, so this selection was not accepted.",
 "effects": {"acceptance": "absent", "attempt": "partial"},
 "retained": ["/home/ana/stewart-archive/audits/aqm3…/intake/1"],
 "next": [{"argv": ["/usr/local/bin/stewart", "prepare", "stw1:…"], "why": "Prepare the current folder, then commission the new handle."},
          {"argv": ["/usr/local/bin/stewart", "close", "stw1:…"], "why": "End this reference without commissioning."}],
 "data": {"added": [], "removed": [], "changed": ["materials/a.py"]}}
```

If publishing `accepted` itself fails, whether it was published cannot be
assumed:

```json
{"schema": "stewart.reply/1", "operation": "commission", "outcome": "failed",
 "reason": "acceptance_record_uncertain",
 "message": "Stewart could not confirm that the acceptance record was published.",
 "effects": {"acceptance": "unknown", "attempt": "recorded", "diagnostic": "durable"},
 "retained": ["/home/ana/stewart-archive/audits/aqm3…/intake/1",
              "/home/ana/stewart-archive/audits/aqm3…/diag/3.json"],
 "causes": [{"operation": "fsync log directory", "error": "EIO"}],
 "next": [{"argv": ["/usr/local/bin/stewart", "status", "stw1:…"], "why": "Status reports whether acceptance was recorded."},
          {"argv": ["/usr/local/bin/stewart", "commission", "stw1:…", "mp1.k4q7xa", "--i-am-finished"],
           "why": "Repeating with the same handle returns the recorded acceptance; it never captures twice."}]}
```

### 5.5 `receipt`

`stewart receipt REF` returns the fixed commission: reference, acceptance time
and handle, question sizes and digests, settings, material index and
directories, arrangement digest and readable location, the checks that matched,
the declaration, the run line, `run_needs` (as in the commission reply) and the
item list. Each item has an ID, size, SHA-256 and its readback argv. Before
acceptance it refuses `not_accepted`. Readback is local, read-only and allowed
while a run is active and after close. It never shows the live answer or
conversation.

By default the receipt reports recorded facts and says that the bytes were not
re-verified. `--verify` reads and hashes every item and reports each as
`verified`, `damaged`, `missing`, `unreadable` or `unsupported`, without
vouching for the whole commission from one member.

`stewart receipt REF --read ITEM` writes the item's captured bytes, exactly, to
stdout. It then writes one JSON line to stderr: the item, size, SHA-256 and
`verified: true`, or the diagnostic (`item_unknown`, `item_damaged`,
`item_missing`, `item_unreadable` or `item_unsupported`). Bytes that fail
verification are not written. Items: `question-file`, `question-body`,
`arrangement`, `arrangement-readable` and `materials/<name>`. The live source
and the currently installed forms are never consulted.

### 5.6 `status`

`stewart status REF` is read-only. It never launches, repairs, seals, copies or
closes anything. Here it reports an audit whose auditor sealed in its second run
and whose run delivered the return:

```json
{"schema": "stewart.reply/1", "operation": "status", "outcome": "completed",
 "effects": {},
 "next": [{"argv": ["/usr/local/bin/stewart", "close", "stw1:…"],
           "why": "Close the audit. An ordinary close confirms where the delivered copy is."}],
 "data": {"headline": {"accepted": "yes", "launched": "yes", "sealed": {"by": "auditor"},
                       "delivered": {"verified": true, "confirmed": false,
                                     "location": "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001"},
                       "closed": "no"},
          "condition": "delivered_open",
          "summary": "The auditor sealed its answer in run 2, and the return was delivered and verified. The audit is open.",
          "evidence": [{"fact": "sealed by the auditor", "evidence": "seal log/30.json"},
                       {"fact": "delivery 1 verified", "evidence": "delivery_ended log/32.json"}],
          "runs": {"count": 2, "held": false, "holder": null,
                   "last": {"number": 2, "started_at": "2026-11-02T15:01:12.204Z", "ending": "sealed", "cause": null,
                            "ended_at": "2026-11-02T15:20:09.551Z", "recorded_by": "run"}},
          "allowances": {"turns": {"used": 41, "reported": 40, "estimated": 1, "limit": 200},
                         "input_tokens": {"used": 1830211, "reported": 1801300, "estimated": 28911, "limit": 20000000},
                         "output_tokens": {"used": 59214, "reported": 51022, "estimated": 8192, "limit": 400000}},
          "answer": {"revision": 9, "entries": 6},
          "seal": {"handle": "seal.r2m6vd", "actor": "auditor", "sealed_at": "2026-11-02T15:20:04.118Z",
                   "revision": 9, "manifest_sha256": "…", "unproduced": []},
          "deliveries": [{"attempt": 1, "by": "run", "destination": "/home/ana/returns",
                          "destination_source": "commissioned", "package": "stewart-return-aqm3x7kd2hz5vw4ny-001",
                          "replaces": null, "outcome": "verified", "cause": null,
                          "verified_members": ["manifest.json", "answer.json", "answer.md"],
                          "unverified_members": [], "losses": [], "confirmation": null}],
          "closure": null, "diagnostics": [],
          "provider_url_override": null, "provider_proxy": null,
          "receipt_line": ["/usr/local/bin/stewart", "receipt", "stw1:…"]}}
```

Headline values: `accepted` is `yes`, `no` or `unknown`; `launched` is `yes`,
`no` or `unknown`; `sealed.by` is `auditor`, `manager`, `none` or `unknown`;
`delivered` has `verified`, `confirmed` and, once a delivery is `verified` or
`verified_with_losses`, `location`, the newest such attempt's package path.
`delivered.verified` is true only for a `verified` delivery. For
`verified_with_losses` it is false, and `delivered` adds `losses`, the list of
loss IDs (8.4). `delivered.confirmed` is true once `closed` records the
delivery's placement. `verified` and `confirmed` are the string `unknown` when
the log is damaged. `closed` is `no`, `unfinished`, `yes` or `unknown`.

The other members of `data`, in order after `evidence`:

- `runs`: `count`, the number of `run_started` records; `held`, whether a
  placement holds the active lock now; `holder`, that placement's
  `run_started` observations while it holds the lock, else null; and `last`,
  null before launch, else the latest placement's `number` and `started_at`
  with `ending`, `cause`, `ended_at` and `recorded_by` from its `run_ended`,
  those four null while it has none.
- `allowances`: null before acceptance. Each allowance gives `reported` (usage
  the provider reported), `estimated` (usage charged without a provider report,
  6.4), `used`, their sum, which is what the limit counts, and `limit`. The
  totals are the `run_ended` usage of every ended placement plus the `charged`
  amounts of the attempt records of a placement that has none.
- `answer`: null before launch; else `revision` and `entries`, the number of
  entries in the current selection. Status never shows answer content.
- `seal`: null, or the seal's `handle`, `actor`, `sealed_at` (the manifest's),
  `revision`, `manifest_sha256` and `unproduced`, the names of the manifest's
  unproduced members.
- `deliveries`: every delivery attempt in order, with `attempt`, `by`,
  `destination`, `destination_source`, `package` and `replaces` from its plan;
  `outcome` and `cause` from its `delivery_ended`, both null while it has none;
  `verified_members`, the names verified at the destination;
  `unverified_members`, each `{name, failure}` for a member written or
  attempted and not verified; `losses`, each
  `{loss, member, role, failure, stage}`, present only for a
  `verified_with_losses` attempt and otherwise `[]`; and `confirmation`, the
  attempt's token while it is outstanding (8.4), else null.
- `closure`: null without `close_requested`. Otherwise `requested_at`;
  `before_launch` (no `run_started` precedes `close_requested`); `accepted`;
  `unfinished_reason` while not closed, else null; and `closed_at`, `outcome`,
  `placement` and `surrendered` from `closed`, each null while not closed.
- `diagnostics`: as below.
- `provider_url_override` and `provider_proxy`: the override and the proxy that
  the latest `run_started` recorded, else null.
- `receipt_line`: the receipt argv once accepted, else null.

`evidence` lists the observations behind the condition, each `{fact, evidence}`.

Status derives a close's `unfinished_reason` the way close would report it
(5.8): with the lock held, `intake_still_running` when an intake has no
outcome, `run_still_held` when a placement has no `run_ended`, else
`close_in_progress`; with the lock free, `awaiting_confirmation` when the
newest verified attempt awaits confirmation (8.4), `delivery_incomplete` when a
seal exists and no verified attempt does, and otherwise null: the last close
stopped before recording more, and repeating close continues it.

Conditions, matching the CONTRACTS status table:

| `condition` | Established facts | Next calls |
| --- | --- | --- |
| `preparing` | Reference, maybe preparations; no intake | prepare, commission, close |
| `intake_in_progress` | Intake holds the lock | status, close |
| `intake_failed` | Last intake ended without acceptance | prepare, commission, close |
| `acceptance_uncertain` | Log damaged; no `accepted` among the readable records before the damage | status after the manager restores its storage; `new` for a new reference |
| `log_damaged` | Log damaged after a readable `accepted` | receipt; status after the manager restores its storage |
| `not_started` | Accepted; no `run_started` | run, close |
| `run_active` | A placement holds the lock | status, close |
| `interrupted` | The latest placement ended `interrupted`, or has no `run_ended` and the lock is free; authoring has not ended | run, close |
| `ended_unsubmitted` | The latest placement ended `ended_unsubmitted` | close |
| `limit_reached` | The latest placement ended `limit_reached` | close |
| `damaged` | The latest placement ended `damaged` | close |
| `sealed_undelivered` | Seal; no verified attempt | close, whose explanation offers `--destination DIR` after an incomplete attempt (8.3) |
| `delivered_open` | A verified attempt; no close request | close |
| `awaiting_confirmation` | Close requested; the newest verified attempt awaits confirmation; status shows its token and loss IDs | close with `--confirm` and, for each loss, `--surrender`; status |
| `close_unfinished` | Close requested; stop, seal or delivery incomplete | close (with its specific continuation), status |
| `closed_before_launch` | Closed with no `run_started`; states whether a commission had been accepted | none |
| `closed` | Closed after launch; names the delivery, or the surrendered losses | none |

A verified attempt is one that ended `verified` or `verified_with_losses`.

`condition` is the first of these that applies:

1. The log is damaged (4.4): `acceptance_uncertain` if no `accepted` is among
   the readable records before the damage, otherwise `log_damaged`.
2. `closed`.
3. `closed_before_launch`.
4. `close_unfinished` or `awaiting_confirmation`.
5. `run_active`.
6. `intake_in_progress`.
7. `sealed_undelivered` or `delivered_open`.
8. `damaged`.
9. `limit_reached`.
10. `ended_unsubmitted`.
11. `interrupted`.
12. `not_started`.
13. `intake_failed`.
14. `preparing`.

When a fact cannot be established, its value is `unknown` and `diagnostics`
names the record and the cause. A damaged record is never read as absent. When
the log is damaged, `diagnostics` names the bad records, and every headline
value that depends on the unreadable part is `unknown`. `diagnostics` also
lists interrupted publications (stage files no record shares, 4.3, 4.5),
unpublished candidates (4.3) and the diagnostics recorded in `diag/`.

`stewart status --archive ROOT` lists every reference in the archive in
creation order with its folder, `inquiry` label, `varies` note and headline. It
selects nothing.

### 5.7 `run`

`stewart run REF` places the auditor into the arrangement in the foreground and
exits when the placement ends (section 6). It needs `ANTHROPIC_API_KEY`;
`STEWART_PROVIDER_URL` and `HTTPS_PROXY` are optional (6.1).

Before it launches anything, `run` checks, in this order. A refusal changes
nothing; its effects state the recorded facts (1.4), with `answer: "unchanged"`.

1. The reference, archive and writer (`reference_invalid`,
   `reference_unknown`, `archive_*`, `writer_mismatch`) and the log
   (`log_damaged`).
2. The audit's state: `not_accepted`; `reference_closed` when `close_requested`
   exists; `authoring_ended` when authoring has ended, which a seal or a
   placement ending `ended_unsubmitted`, `limit_reached` or `damaged`
   establishes, with `data.ended_by` (`seal`, `ordinary_ending`, `limit` or
   `damage`) and `data.record`, the record that ended it.
3. The environment: `provider_key_missing` (unset or empty),
   `provider_key_invalid` (a byte outside 0x21–0x7E), `provider_url_invalid`
   and `provider_proxy_invalid` (6.1).
4. The lock: `run_held` when another process holds it, with `data.run` and
   `data.holder` (that placement's observations) when a placement holds it.
5. The commission: it reads the `accepted` record's receipt, the arrangement the
   receipt names and every capture through descriptors, checking each size and
   digest. Any failure refuses `commission_damaged`, with `data.items`, each
   `{item, problem}` using receipt item IDs (2.4).

It then reconciles a dead placement (6.7), publishes `run_started`, creates
`runs/<n>` and runs the loop (6.3). Once `run_started` is published, `run`
replies `completed` whenever it recorded the placement's ending, whatever the
ending, and `failed` when it could not: `record_failed`, or `log_damaged` when
it found the log damaged (6.5), with `effects.run` `started`. Exit status is 5
for an `interrupted` ending and 0 for any other recorded ending (1.6).

```json
{"schema": "stewart.reply/1", "operation": "run", "outcome": "completed",
 "effects": {"run": "ended", "answer": "changed", "seal": "recorded", "delivery": "verified"},
 "next": [{"argv": ["/usr/local/bin/stewart", "close", "stw1:…"],
           "why": "Close the audit. An ordinary close confirms where the delivered copy is."}],
 "data": {"run": 2, "continuing": true, "ending": "sealed", "cause": null, "provider": null,
          "usage": {"turns": {"reported": 12, "estimated": 0}, "input_tokens": {"reported": 640117, "estimated": 0},
                    "output_tokens": {"reported": 20410, "estimated": 0}},
          "allowances": {"turns": {…}, "input_tokens": {…}, "output_tokens": {…}},
          "answer": {"revision": 9, "entries": 6},
          "seal": {"handle": "seal.r2m6vd", "actor": "auditor", "sealed_at": "2026-11-02T15:20:04.118Z",
                   "revision": 9, "manifest_sha256": "…", "unproduced": []},
          "delivery": {"attempt": 1, "outcome": "verified",
                       "location": "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001",
                       "verified_members": ["manifest.json", "answer.json", "answer.md"],
                       "unverified_members": [], "losses": [], "cause": null},
          "notices": [{"type": "reminder", "sent": "sent"}]}}
```

`data` holds `run` and `continuing`; `ending`, `cause` and `provider` as in
`run_ended`; `usage`, this placement's charge; `allowances`, the cumulative
allowances as status gives them; `answer` and `seal` as in status; `delivery`,
the attempt this run made (`attempt`, `outcome`, `location`, the package path or
null, `verified_members`, `unverified_members`, `losses` and `cause`, as in
status), or null; and `notices`, as in `run_ended` without `record`.

| Ending | `next` |
| --- | --- |
| `interrupted` | `run` (continues under the same limits), `close` |
| `ended_unsubmitted`, `limit_reached`, `damaged` | `close` (seals the recorded selection with manager attribution) |
| `stopped_by_close` | `status`, `close` (continues the close another invocation requested) |
| `sealed` | `close`; after an incomplete delivery its explanation offers `--destination DIR` |

Refusals carry the next calls that fit: `close` (and `status`) for
`authoring_ended` and `reference_closed`; `status` and `close` for `run_held`;
`receipt REF --verify` and `close` for `commission_damaged`; for the
environment refusals, the same `run` once the environment is set.

### 5.8 `close`

`close` is available in every state. One algorithm serves every call; repeating
it resumes where the recorded state stands. An unfinished close is outcome
`completed` with `data.closure: "unfinished"` and `data.unfinished_reason`
naming what remains; it carries no top-level `reason`. A verified attempt is
one that ended `verified` or `verified_with_losses` (8.3); the newest verified
attempt of the seal is the one close presents and confirms.

`--surrender` is accepted only with `--confirm`, and `--destination` only
without it; anything else is a usage error (exit 2).

Close reconciles under a free lock: it records the end of work whose process is
gone. An `intake_planned` without an outcome gets `intake_ended` with
`outcome: "process_gone"`; a `run_started` without a `run_ended` gets
`run_ended` `interrupted` with cause `process_gone`, its usage computed as 6.4
states; a `delivery_planned` without an outcome gets `delivery_ended` `failed`
with cause `process_gone`. Each records `recorded_by: "close"`.

1. If the log is damaged (4.4), reply unfinished with
   `unfinished_reason: "log_damaged"`, naming the bad records. Close publishes
   nothing to a damaged log, so it never publishes `closed`.
2. If `closed` exists, return its recorded outcome with
   `data.already_closed: true`. Options are not evaluated.
3. Check the options against the records as they stand. A refusal here
   publishes nothing.
   - Before launch: `--confirm` or `--surrender` is refused
     (`confirmation_mismatch`) and `--destination` is refused
     (`destination_not_replaceable`): nothing is owed for delivery.
   - `--confirm TOKEN` must be the token of the newest verified attempt, which
     therefore ended before this call; otherwise it is refused
     (`confirmation_mismatch`). A pre-delivery request never supplies
     confirmation. Each `--surrender LOSS` must be a loss ID of that attempt
     (`handle_invalid` otherwise). When the attempt has losses, the given set
     must name every one of them (`surrender_required`, with `data.losses`).
   - `--destination DIR` is refused with `delivery_already_verified` when a
     verified attempt exists: close completes an owed delivery and is not a copy
     service. It is refused with `destination_not_replaceable` before any
     incomplete attempt of the seal (8.3), including before a seal exists:
     a replacement serves only a delivery that could not complete. It is
     refused with `destination_invalid` unless DIR is absolute, exists and is a
     directory.
4. If no `close_requested` exists, publish it, recording this call's options.
   From this log position authoring ends, no run may start and no intake may be
   accepted.
5. **Before launch** (no `run_started` before `close_requested`): wait up to 10
   seconds for an intake holding the lock to end. If it still holds the lock,
   reply unfinished with `unfinished_reason: "intake_still_running"`. Otherwise
   reconcile, then publish `closed` with `before_launch: true` and whether a
   commission had been accepted. No answer, seal or confirmation is created.
6. **After launch**, in order:
   - **Stop.** If the lock is held and a `run_started` has no `run_ended`, wait
     up to 30 seconds for the run to observe `close_requested` and exit (6.8). If
     it is still held, reply unfinished, `run_still_held`, with the holder
     observations. A seal alone never counts as stopped execution. If the lock
     is held and every `run_started` has its `run_ended`, another close holds
     it: reply unfinished, `close_in_progress`.
   - **Lock.** Take the active lock (4.6) and hold it for the seal and delivery
     work. If another close holds it, reply unfinished, `close_in_progress`.
     Otherwise reconcile.
   - **Seal.** An existing seal is kept, whoever made it. Otherwise close
     prepares the selection current at `close_requested` into a new
     `prepared/<n>` and seals it with `actor: "manager"` (8.1). An entry that
     cannot be read or verified becomes a named, unproduced member, and so does
     the rendering that depends on it.
   - **Deliver.** With an accepted `--confirm`, close presents the confirmed
     attempt. Otherwise, if a verified attempt exists, close presents the newest
     one; but when its losses include any with `stage: "delivery"`, close first
     re-reads those members in the archive, and if every one now verifies
     against the manifest it makes a new attempt to that attempt's destination,
     which `replaces` it, and presents that instead. If no verified attempt
     exists, close delivers (8.3) to `--destination DIR` if given, else to the
     newest attempt's destination, else to the commissioned destination. When
     no attempt verifies, reply unfinished, `delivery_incomplete`: `close`
     continues, and so does `close --destination DIR` after an incomplete
     attempt. When the manifest cannot be read, membership is unknown: attempts
     end `failed`, no loss IDs exist, and close stays unfinished.
   - **Complete.** Publish `closed` when every placement has its `run_ended`
     and either:
     - `--confirm` was accepted and still names the newest verified attempt
       (`placement: "confirmed"`, with the surrendered losses), or
     - no `--confirm` was given and the presented attempt ended `verified`
       before the first `close_requested` (`placement: "delivered_before_close"`):
       an ordinary close is then the manager's decision about that copy.

     Otherwise reply unfinished, `awaiting_confirmation`, presenting the attempt,
     its token and its loss IDs. Repeating close without the token only presents
     the same result again: a copy existing now does not turn a repeat into
     confirmation. Unknown membership offers no loss IDs.

Every delivery attempt uses a fresh package and keeps earlier attempts. Close
leaves the preparation folder and every archive byte alone.

`data` of a completed reply, by path:

- **Closed** (including `already_closed`): `closure: "complete"`,
  `already_closed`, `before_launch`, `accepted`, `closed_at` and `headline`.
  After launch it adds `outcome`, `runs`, `seal`, `delivery`, `placement` and
  `surrendered`, from the `closed` record and the records it names.
- **Unfinished**: `closure: "unfinished"`, `unfinished_reason` and `headline`.
  Before launch it adds `intake` (the number of the intake attempt still holding the lock, or null)
  for `intake_still_running` and `close_in_progress`. After launch it adds
  `runs`, `seal`, `delivery`, `confirmation` (the token, only for
  `awaiting_confirmation`, else null) and `holder` (the live placement's
  observations, only for `run_still_held`, else null).
- **Damaged log**: `closure: "unfinished"`, `unfinished_reason: "log_damaged"`,
  `bad_records` and `headline`.

`runs` is `{count, held, last_ending}`; `seal` is as in status, or null;
`delivery` is the presented or newest attempt as in the `run` reply, its losses
carrying loss IDs, or null.

| Path | `run` | `seal` | `delivery` | `closure` |
| --- | --- | --- | --- | --- |
| Before launch | `not_started` | `none` | `none` | `complete` or `unfinished` |
| `run_still_held` | `still_held` | `none` or `existing` | newest attempt's outcome, or `none` | `unfinished` |
| Other paths after launch | `ended` | `recorded` when this call sealed, else `existing` | presented or newest attempt's outcome, or `none` | `complete` or `unfinished` |
| Damaged log | `unknown` | `unknown` | `unknown` | `unfinished` if `close_requested` is readable, else `unknown` |

| `unfinished_reason` | `next` |
| --- | --- |
| `intake_still_running`, `run_still_held`, `close_in_progress` | `close`, `status` |
| `delivery_incomplete` | `close`, whose explanation offers `--destination DIR` after an incomplete attempt (8.3) |
| `awaiting_confirmation` | `close --confirm TOKEN`, with `--surrender LOSS` for each loss and an explanation naming what each surrender gives up; `status` |
| `log_damaged` | `status` |

A closed reply has no next calls; the receipt stays readable through status's
`receipt_line`. Refusals offer `close` without the refused option, and
`surrender_required` also offers the confirmation with every loss named.

```json
{"schema": "stewart.reply/1", "operation": "close", "outcome": "completed",
 "effects": {"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
 "next": [{"argv": ["/usr/local/bin/stewart", "close", "stw1:…", "--confirm", "cf1.h3d7ws"],
           "why": "Confirm that this delivered copy is where you want the return."},
          {"argv": ["/usr/local/bin/stewart", "status", "stw1:…"],
           "why": "Status keeps showing the delivery and its token until you confirm."}],
 "data": {"closure": "unfinished", "unfinished_reason": "awaiting_confirmation",
          "headline": {"accepted": "yes", "launched": "yes", "sealed": {"by": "manager"},
                       "delivered": {"verified": true, "confirmed": false,
                                     "location": "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001"},
                       "closed": "unfinished"},
          "runs": {"count": 1, "held": false, "last_ending": "ended_unsubmitted"},
          "seal": {"handle": "seal.r2m6vd", "actor": "manager", "sealed_at": "2026-11-02T15:31:40.020Z",
                   "revision": 7, "manifest_sha256": "…", "unproduced": []},
          "delivery": {"attempt": 1, "outcome": "verified",
                       "location": "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001",
                       "verified_members": ["manifest.json", "answer.json", "answer.md"],
                       "unverified_members": [], "losses": [], "cause": null},
          "confirmation": "cf1.h3d7ws", "holder": null}}
```

### 5.9 `help`

`stewart help` lists commands and the manager's path. Topics explain the
folder and the instruction to finish editing before prepare (`commands`), each
family's instructions and recording tools (`forms`), the limits and bounds
(`limits`), the reader (`reader`), and every close state with its continuation
(`close`). Help text ships with the binary and is printed exactly; it involves no
archive.

## 6. The run adapter

### 6.1 Provider

The first adapter speaks the Anthropic Messages API, non-streaming, pinned to API
version `2026-10-21`. Field names below follow that version's published
specification. Each attempt opens a new connection and sends one HTTP/1.1
request:

```
POST <path>/v1/messages HTTP/1.1
host: <host>[:<port>]
x-api-key: <ANTHROPIC_API_KEY>
anthropic-version: 2026-10-21
content-type: application/json
content-length: <body bytes>
connection: close
```

followed by the body (4.5, 6.2). No other header is sent; in particular there is
no `anthropic-beta` header. `host` carries the port only when the URL names one.
The response is read to its end by `content-length`, chunked transfer coding or
the connection closing. A `content-encoding` other than `identity` makes the
response undecodable.

The base is `https://api.anthropic.com` unless `STEWART_PROVIDER_URL` overrides
it. An override is `https://`, or `http://` for a loopback host only, then a
host (a DNS name, an IPv4 address or a bracketed IPv6 address), an optional
`:port` and an optional path without a trailing `/`, and no user information,
query or fragment. Loopback hosts are `localhost`, which is connected at
127.0.0.1 without consulting the resolver, addresses in 127.0.0.0/8 and
`[::1]`. Anything else is refused before any request (`provider_url_invalid`).
The override is recorded in `run_started` and shown by status.

If `HTTPS_PROXY` (or `https_proxy`) is set, the adapter reaches an `https://`
provider with a non-loopback host through that proxy: it sends
`CONNECT <host>:<port> HTTP/1.1` with the header `host: <host>:<port>`, and a
2xx reply opens the tunnel. Stewart resolves only the proxy's host; the proxy
resolves the provider's. TLS runs end to end inside the tunnel, so the proxy
never sees the key. The proxy value must be `http://host:port`, optionally with
one trailing `/`, without credentials; anything else is refused before any
request (`provider_proxy_invalid`). `NO_PROXY` is not consulted, and loopback
provider URLs never use the proxy. The proxy in use is recorded in
`run_started` and shown by status.

TLS verifies the provider against the web PKI roots built into the release and
sends the host as SNI unless it is an IP address. A test build can add roots
(Appendix C).

### 6.2 Requests and responses

`arrangement.json` pins, as exact bytes where noted:

| Member | Content |
| --- | --- |
| `model` | From front matter |
| `anthropic_version` | `2026-10-21`, pinned by the release |
| `max_tokens_per_request` | 16,000, pinned by the release, so a non-streaming response fits the request timeout |
| `system` | Exact JSON array: orientation block, family instruction block (QUESTION-FORMS) |
| `tools` | Exact JSON array of tool definitions for the family (section 7) |
| `request_extra` | Exact JSON object of further top-level request parameters, limited to the release's allowlist. This release's allowlist is empty, so it is `{}`. |
| `texts` | Reminder, near-limit template and continuation notice |
| `limits`, `near_limit_percent` | From front matter; 20 |
| `retry`, `request_timeout_seconds` | 6.6 policy; 600 |
| `reader`, `renderer`, `family` | `utf8-text/1`, `stewart.render/1`, family ID and version |
| `bindings` | SHA-256 of the question body and of the material index |

The run loads the arrangement through the `accepted` record, the receipt it
names and the receipt's `arrangement` member, checking each digest (5.7). Each
request body is assembled by splicing pinned bytes, never by re-serializing a
parsed structure, exactly as 4.5 states. No provider feature may be enabled that
puts model-visible content outside the arrangement, such as server tools,
fallback to another model, provider-side context management or budget
countdowns; with `request_extra` empty, none is.

Messages are append-only within a placement, each a compact object with keys
`role` and `content`:

- The first user message holds one text block with the question body exactly.
  In a continuing placement a second text block holds the continuation notice.
- Each assistant message is `{"role":"assistant","content":` followed by the
  bytes of the response's `content` value, copied byte for byte from the
  response capture, and `}`. It carries every block the provider returned,
  including `thinking` blocks with their signatures, the progress notes models
  return between tool calls as `thinking` blocks, and blocks of unknown types.
- Each following user message holds first one `tool_result` block per
  `tool_use` block of the preceding assistant message, in order (7.1), then the
  reminder text block when the reminder is sent (6.4), then the near-limit
  notice text block when it is pending.
- A text block is `{"type":"text","text":<text>}`, the string escaped as in
  `stewart.answer/1` (QUESTION-FORMS).

Each response body is captured raw before decoding (4.5). It is decoded
tolerantly: unknown members and block types are kept in the capture and echoed
in history, never interpreted. Stewart interprets only these members, each of
which must appear exactly once in its object:

- in a message: `content`, an array; `stop_reason`, a string; and `usage`, with
  integer `input_tokens` and `output_tokens` and with
  `cache_creation_input_tokens` and `cache_read_input_tokens` each an integer,
  null or absent. `model` is recorded when it is a string. An HTTP 200 body
  that is not a JSON object, or in which one of these is missing, of another
  type or repeated, is undecodable.
- in each `content` element: `type`. An element that is not an object, or whose
  `type` is missing, repeated or not a string, is a block of unknown type.
- in a `tool_use` block: `id`, `name` and `input`. A missing, repeated or
  non-string `id`, or one containing U+0000, makes the block unanswerable
  (6.3). A missing, repeated or non-string `name`, or one containing U+0000, is
  refused `tool_unknown`, and a missing or repeated `input` `input_invalid`. The `input` value is decoded strictly from its raw bytes
  (1.2) when the call runs.
- in an error body `{"type":"error","error":{"type":…,"message":…},"request_id":…}`:
  `error.type`, `error.message` and `request_id`, recorded when they are
  strings.

Records hold only strings that strict decoding accepts (1.2). A `model`,
`error.type`, `error.message` or `request_id` containing U+0000 is recorded as
null, and a `stop_reason` containing it is an unknown stop reason; the raw
capture keeps the bytes.

`stop_details` and every other member stay in the raw capture. Stewart does not
summarize or trim history. When the model's context window is exhausted the
placement is interrupted (6.5), and continuation starts a fresh conversation.

### 6.3 The loop and invocation identity

```
before each request: if close_requested → end stopped_by_close
                     if a limit is exhausted (6.4) → end limit_reached
capture the request, send it with retries (6.6), account usage (6.4)
no response to use → end as 6.5 states
execute every tool_use block of the response in order (section 7)
if the log holds a seal recorded during this response → deliver (8.3), then end sealed
stop_reason tool_use   → send results, continue
            end_turn, stop_sequence → if a limit is exhausted, end limit_reached;
                                      else send the reminder if unused (6.4); else end ended_unsubmitted
            max_tokens → if the response has a tool_use block, send results and continue;
                         else end interrupted (max_tokens)
            model_context_window_exceeded → end interrupted (context_exhausted)
            refusal    → end interrupted (provider_refusal)
            other, including pause_turn → end interrupted (protocol_anomaly)
```

Whether a seal was recorded is read from the log after the blocks run, not
from the calls' replies: a submit that replied `seal_uncertain` while its seal
was in fact linked still leads to delivery and the ending `sealed`. Once the log
holds a seal, the placement sends no further request and no reminder.

A response's `tool_use` blocks are executed whatever its stop reason, so every
call the model made is recorded even when the placement then ends; results that
are not sent stay in their result records. A `tool_use` block without a string
`id` cannot be answered: it is captured, no later block is executed, and the
placement ends `interrupted` (`protocol_anomaly`). So does `stop_reason`
`tool_use` with no `tool_use` block.

Execution of a response's blocks stops early when a call fails with
`record_failed` (7.1), when a read or prepare finds damaged answer bytes (7.2,
7.6) or when the stop path applies (6.8). Later blocks of that response are
neither captured nor executed; they remain in the response capture.

Once a seal is recorded, the run completes its delivery, or records the
delivery's failure, before publishing `run_ended` `sealed`, even if
`close_requested` appears meanwhile (6.8).

A tool invocation's identity is the placement number plus the `tool_use` ID.
Before executing, the raw block is captured (`call-<c>.json`). After executing,
its result is recorded (`result-<c>.json`). A later block in the same placement
with an executed ID, the same `name` and identical raw `input` bytes is a
replay: it receives the recorded result's `content` and `is_error` without
another execution, and its result record names the original in `replay_of`.
With a different `name` or `input` it is refused (`invocation_id_reused`).
Retries resend recorded results, so a retried request is byte-identical. A new
call with matching arguments is a new invocation.

### 6.4 Limits, reminder and notice

Each attempt record states its charge (4.5):

| Attempt outcome | Charge |
| --- | --- |
| `response` | Reported: one turn; `input_tokens` + `cache_creation_input_tokens` + `cache_read_input_tokens` input tokens; `output_tokens` output tokens |
| `response_undecodable`, `connection_lost`; `timeout`, `aborted_by_close` and `aborted_by_signal` once any request byte was written | Estimated: one turn, the request's `max_tokens` output tokens and ceil(body bytes / 3) input tokens |
| `http_error`, `connection_failed`; the others when no request byte was written | None |

A placement without `run_ended` is accounted from its run directory: the
charges of its attempt records, plus one estimated attempt for each complete
request capture whose latest attempt has no record. Reconciliation records
exactly that in `run_ended`. Reported and estimated usage are kept separately
for turns, input and output, in `run_ended`, in status allowances (5.6) and in
re-entry (7.5); a limit counts their sum. Totals are cumulative across
placements.

Each request's `max_tokens` is the lesser of `max_tokens_per_request` and the
remaining output allowance, fixed when the request is captured; every attempt of
a request sends the same body. A limit is exhausted, and no request or retry is
sent, when any of the following holds:

- no turn remains;
- the input allowance is used up;
- fewer than 1,024 output tokens remain.

Reported output tokens therefore never exceed their limit. Estimates for lost
responses can take the counted output past it, and the run then stops at the
next check. Input tokens can exceed their limit, since a request's input size is
known only from its response. Pending `tool_use` blocks of the last response are
executed before the placement ends `limit_reached`.

The reminder is the CONTRACTS text, sent at most once per audit. After an
`end_turn` or `stop_sequence` without a seal, if any limit is exhausted the
placement ends `limit_reached` and no reminder is planned. Otherwise, if the
reminder is unused, a `notice` record with `type: "reminder"` is published, then
the next request carries it: the tool results of that response if any, the
reminder block, and the near-limit notice block if that notice is pending. If
the reminder is already used, the placement ends `ended_unsubmitted`.

The near-limit notice is sent at most once per audit. With remaining =
max(0, limit − used), it is triggered when, after an attempt is accounted,
remaining × 100 ≤ `near_limit_percent` × limit for any limit. Its template
values are the remaining amounts. Its `notice` record is published when it is
triggered, naming the next request, which carries it. If the placement ends
first, the record stands and the notice is not sent.

`run_ended` reports each notice record of its placement as `sent` when an
attempt record of the planned request has `request_written` other than `none`,
`not_sent` when that request was never captured, and `unknown` otherwise. Both
allowances are audit-wide: a continuing placement neither resets nor resends
them.

### 6.5 Endings

| Event | Recorded ending | `run` may continue |
| --- | --- | --- |
| Auditor confirmed submit | `sealed` | no |
| `end_turn` or `stop_sequence` with the reminder already used | `ended_unsubmitted` | no |
| Limit reached | `limit_reached` | no |
| `close_requested` observed | `stopped_by_close` | no |
| Damaged answer bytes found by a read or prepare (7.2, 7.6) | `damaged` | no |
| SIGTERM, SIGINT, SIGHUP before a seal | `interrupted`, cause `signal` | yes |
| A retryable attempt outcome on the last attempt, or a `retry-after` over 60 seconds (6.6) | `interrupted`, cause `provider_unavailable` | yes |
| Any other HTTP error, including 400, 401 and 413 `request_too_large` | `interrupted`, cause `provider_rejected`; `run_ended.provider` holds the status and `error.type` | yes |
| `stop_reason` `model_context_window_exceeded` | `interrupted`, cause `context_exhausted` | yes |
| `stop_reason` `refusal` | `interrupted`, cause `provider_refusal` | yes |
| `max_tokens` with no `tool_use` | `interrupted`, cause `max_tokens` | yes |
| `pause_turn`, an unknown stop reason, an undecodable response, an unanswerable `tool_use` block | `interrupted`, cause `protocol_anomaly` | yes |
| Archive write failure | `interrupted`, cause `archive_write_failed` | yes |
| The log is found damaged (4.4) | none: the run publishes nothing, sends no further request, releases the lock and exits 4; status reports the damage | no |
| Process killed or crashed | no `run_ended`; the next `run` or `close` records `interrupted`, cause `process_gone` | yes |

`run` may continue only while authoring has not ended. A placement that sealed
and then died is reconciled as `interrupted` (`process_gone`), and `run` still
refuses because the seal ended authoring. The reminder is used only for an
ordinary `end_turn` or `stop_sequence`. `run_ended` records the ending, its
cause, the provider facts, the placement's usage split into reported and
estimated, and its notices (4.4).

### 6.6 Provider retry

| Attempt outcome | Meaning | Retried |
| --- | --- | --- |
| `response` | HTTP 200 with a decodable message | — |
| `response_undecodable` | HTTP 200 whose complete body is not a decodable message (6.2), or whose body exceeds 32 MiB | no |
| `http_error` | Any other status, its body captured | for 408, 429, 500, 502, 503, 504 and 529 |
| `timeout` | No complete response within the request timeout, counted from the start of the connection | yes |
| `connection_failed` | Resolution, connection, proxy `CONNECT` or TLS failed before any request byte was written | yes |
| `connection_lost` | The connection failed after request bytes were written and before the response was complete, including an HTTP 200 body cut off by the connection ending or being reset; another status that arrived is `http_error` even if its body was cut off | yes |
| `aborted_by_close`, `aborted_by_signal` | The stop path shut the connection down (6.8) | no |

Each request is attempted at most 4 times. The delays before attempts 2, 3 and 4
are 2, 8 and 30 seconds, or the `retry-after` value when one is given: the
header's first value, used when it is a decimal integer of seconds and ignored
otherwise. A `retry-after` over 60 seconds is not waited for: the request is not
retried, and the placement ends `interrupted` with cause `provider_unavailable`.
A `close_requested` or a signal seen while waiting ends the placement; after
waiting, the limits are checked again (6.4). Each attempt is captured.

### 6.7 Continuation

`run` on an interrupted audit first records `run_ended` (`process_gone`,
`recorded_by: "run"`) for a dead placement, with its usage
accounted as 6.4 states, then publishes `run_started` for placement `n+1`. The
new conversation uses the same pinned arrangement bytes. The question is in the
first message and the continuation notice follows it (QUESTION-FORMS). The
ledger, limits and notice allowances carry over unchanged. No prior
conversation is replayed.

### 6.8 Stopping

A watcher thread checks every 250 milliseconds whether the log's next record is
a `close_requested`. Its stop path applies only while no seal exists; once a
seal is recorded, the run finishes its delivery first (6.3). When the stop path
applies, the adapter aborts any in-flight provider request by shutting down its
socket (`aborted_by_close`), stops executing tool calls, publishes `run_ended`
(`stopped_by_close`), releases the lock and exits 0. An in-progress mutation
fails to claim its log slot and is reported to the model as `authoring_ended`.

On SIGTERM, SIGINT or SIGHUP before a seal the adapter takes the same path
(`aborted_by_signal`), records `interrupted` with cause `signal` and exits 5.
After a seal a signal ends the delivery attempt `failed` with cause `signal`,
and the placement ends `sealed`. The `run_needs` of the commission and receipt
replies says that the run is in the foreground until the placement ends, and
that callers with command timeouts should start it in the background.

## 7. The auditor's tools

### 7.1 Conventions

- Every `tool_result` block is
  `{"type":"tool_result","tool_use_id":<ID>,"content":[…],"is_error":<bool>}`
  (4.5). Its content begins with a text block holding the `stewart.reply/1`
  envelope, whose `operation` is the tool name. Text reads add a second text
  block holding the exact text read. Like every text block, it is a JSON string
  on the wire, as CONTRACTS requires. When the page has no non-whitespace
  character, including an empty page, there is no second block, because the
  provider refuses blank text blocks; the exact text is then in the envelope's
  `data.text`. Base64 pages are always in `data.base64`. `is_error` is true when
  the outcome is not `completed`.
- Inputs are decoded strictly (1.2) and are at most 4 MiB per call
  (`input_too_large`). A block naming no tool of the arrangement is refused
  (`tool_unknown`), naming the tools; an `input` that is not an object is
  refused (`input_invalid`).
- Replies never include host or archive paths, front matter, provider details
  or manager identifiers: the reference string, archive path, store ID, inquiry
  label, varies note and family. The audit ID is visible to the auditor. A
  refusal may repeat the auditor's own input verbatim, such as an unknown
  source name, since that reveals nothing the auditor did not send.
- Every tool definition is `{"name", "description", "input_schema"}`. The input
  schema is `{"type": "object", "properties": {…}, "required": […],
  "additionalProperties": false}`, with the properties and descriptions given in
  QUESTION-FORMS.
- After a seal or close, mutations refuse `authoring_ended`, naming what ended
  authoring and, if a seal exists, who sealed. Reads continue to work until the
  placement ends.
- When an archive write fails during a call (its payload, its log record or its
  result record), the call fails with `record_failed`. Its `effects` state what
  is known, with `unknown` where the write's outcome cannot be established. No
  later block of that response is captured or executed, no further request is
  sent, and the placement ends `interrupted` with cause `archive_write_failed`
  (6.5).
- A call's account is its result record. A failed call also writes a
  diagnostic (4.8), and its effects add `diagnostic`.

| Tool | Input | Completed `data` |
| --- | --- | --- |
| `list` | `cursor?` | `materials[{source,size,lines}]`, `directories[]`, `returned`, `total`, `complete`; while incomplete, `next` is a `list` call with an `ls.` cursor. A page holds at most 128 materials. |
| `read` | `source`, `start?` | 7.2 |
| `search` | `text`, `sources?`, `cursor?` | 7.2 |
| `record_<kind>` | `text`, `citations?`, `label?` | `entry`, `id`, `version`, `revision`, `citations`, `notices` |
| `record_artifact` | `label`, exactly one of `text` / `base64` | `entry`, `id`, `version`, `revision`, `encoding`, `size`, `notices` |
| `replace` | `entry` and every field of its kind | as the kind's record tool |
| `delete` | `entry` | `removed{id,version}`, `revision`, `already_removed` |
| `what_am_i_working_with` | `page?` | 7.5 |
| `prepare` | none | 7.6 |
| `submit` | `prepared`, `confirm?` | 7.6 |

### 7.2 Reading and searching

`read(source, start = 0)` reads `question`, `materials/<name>`, a current entry
handle, or a prepared view (`ap<n>.<check>/rendering` or `/selection`).

- `start` must be at most the size and on a UTF-8 boundary. Otherwise the call
  is refused (`range_invalid`), giving the nearest boundaries.
- A page ends at the source's end if that is within 65,536 bytes. Otherwise it
  ends just after the last LF in the window, or, when the window has no LF, at
  the last UTF-8 boundary within it.
- `data`: `source`; `kind` (`question`, `material`, `entry` or `view`); `size`;
  `range` [start, end); `lines` [first, last] (1-based lines of the first and
  last byte, `null` when empty); `complete`; `cite`, a ready citation
  `{source, start, end}` for the page, `null` for entry and view reads and for
  an empty page, which no citation can name (7.3); and
  `text` or `base64` when the page is carried in the envelope (7.1). While the
  read is incomplete, the envelope's `next` is a ready `read` call for the rest.
- Entry reads add `entry`, `id`, `version`, `entry_kind` (the recording tool,
  such as `record_account` or `record_artifact`), `label` and `citations`, and
  for an artifact `artifact_encoding` (`utf-8` or `binary`, 7.4). `kind` stays
  `entry`. A replaced entry handle is refused (`stale_entry`) with the current
  handle. A deleted one is refused (`entry_deleted`). An artifact recorded from
  `base64` (`artifact_encoding: "binary"`) is returned as base64 pages of 49,152
  bytes in `data.base64`.
- Reading an entry first checks its payload's size and digest. Damaged bytes of
  a current entry refuse the call (`answer_damaged`) with an empty `next`, and
  the placement ends `damaged` (6.5): the auditor stops.
- A prepared view remains readable after a later edit. It is its fixed
  selection, never a newer rendering.

`search(text, sources = all, cursor)` is literal, case-sensitive search.

- `text` is 1–1,024 bytes.
- `sources` names up to 128 sources from `question` and `materials/…`. The
  default is the question, then every material in index order. The reply
  states the scope searched.
- Every occurrence is reported, including overlapping ones, in source order and
  then by position.
- The completed `data` is `{text, scope, hits, returned, complete}`: the search
  text, the sources searched in order, this page's hits, their number and
  whether the whole scope was scanned.
- A hit is `{source, start, end, line, context, cite}`. `context` is
  `{text, truncated_before, truncated_after}`: the hit's line, clipped to 240
  bytes around the hit on character boundaries, and whether bytes were clipped
  before and after it. `cite` is a ready citation `{source, start, end}`.
- A page holds at most 128 hits and 32 KiB of context text. `complete: true`
  means the whole scope was scanned. Otherwise the envelope's `next` is a ready
  `search` call whose `sc.` cursor is bound to the text, the scope and the
  position.
- An incomplete search never reports absence.

The run checks every capture against the receipt before it places the auditor
(5.7) and serves reads and searches from those captures through descriptors it
holds for the placement.

### 7.3 Citations

A citation is one of:

- `{source, start, end, quote?}`: a range from a read or search reply. `start`
  is less than `end`, both are UTF-8 boundaries within the source, and an
  explicit `quote` must equal those bytes exactly.
- `{source, quote}`: Stewart finds the quote's exact occurrences in the source.
  Exactly one occurrence is recorded, its range in `stewart.range`. None is
  refused (`quote_not_found`). More than one is refused (`quote_ambiguous`) with up to 8
  occurrences, each a ready citation.

`source` is `question` or `materials/<name>`. Entries are not citable. An entry
takes at most 64 citations. Matching is exact: no normalization, no fuzzy match,
no moving a range to where its quote appears. A defective citation refuses the
whole call (`citation_invalid`, naming the citation's index and defect). The
refusal creates no entry, and the raw call stays captured.

In a recorded citation the top level holds only the auditor's operands:
`source`, and `start`, `end` and `quote` as supplied. Stewart's attributed
additions go under `stewart`: `name`, `sha256`, `range` (only when Stewart
located the citation from a quote) and `lines`. Keys appear in the order
`source`, `start`, `end`, `quote`, `stewart` {`name`, `sha256`, `range`,
`lines`}, with absent keys omitted:
`{"source": "materials/src/a.py", "quote": "retry()", "stewart": {"name": "materials/src/a.py", "sha256": "…", "range": [1210, 1217], "lines": [42, 42]}}`.
Matching references establish no support for any claim.

To cite a span, take `start` from the read or search result at its beginning and
`end` from the one at its end.

### 7.4 Recording and editing

- `record_<kind>(text, citations = [], label = "")` appends one entry and
  returns its exact handle. `text` may be empty. `label` is at most 200
  characters with no control characters. A label equal to another current
  entry's label adds the notice `label_duplicate` to `data.notices`; it is not
  refused. Repeating a call creates another entry.
- `record_artifact(label, text | base64)` appends a free-form artifact. `label`
  is required, 1–200 characters with no control characters. `base64` is
  canonical RFC 4648 with padding and no whitespace. The artifact's `encoding`
  follows the input field: `text` gives `utf-8` and `base64` gives `binary`,
  even when the decoded bytes happen to be UTF-8. Artifacts satisfy no family
  section.
- `replace(entry, …)` replaces exactly that version and returns the new handle.
  The replacement keeps the entry's position and kind. Every field of the kind
  is required: `text`, `citations` and `label` (0–200 characters) for a recorded
  entry; `label` (1–200 characters) and one of `text` or `base64` for an
  artifact. An omitted field is an invalid call (`fields_invalid`).
- `delete(entry)` removes exactly that version from current membership.
  Repeating the delete of the same handle returns the recorded removal with
  `already_removed: true` and changes nothing.
- A replaced target is refused (`stale_entry`). The reply carries `current`
  (the current handle) and next calls to `read` and `replace` it, and it makes
  no claim that the earlier replacement failed. A stale target never deletes
  or overwrites a newer version.
- Order is the order of first creation. Delete removes an entry from the order.
- Bounds: 256 current entries, 64 MiB per entry and 256 MiB in the current
  selection. Once retained superseded and deleted payloads reach 1 GiB, edits
  larger than 1 MiB are refused (`retained_payload_cap`) and smaller ones draw
  on a 64 MiB reserve (`retained_payload_reserve_exhausted` when it runs out).
  Delete, prepare and submit never refuse on that cap. Through the model
  adapter one call carries at most 4 MiB (7.1), so an entry recorded by a model
  is bounded by that; the 64 MiB per-entry bound applies to the core.

Each add and replace stores its bytes in a new payload file before its `entry`
record is published: the UTF-8 bytes of `text`, or the decoded bytes of
`base64`, for a recorded entry and an artifact alike. An empty text gives an
empty file. The file is `payload/<id>.v<version>.bin` (`payload/e2.v2.bin`),
created with `O_EXCL`; when that name is taken by a payload an interrupted edit
left behind, the first free name among `payload/<id>.v<version>-2.bin`, `-3`, …
is used. The `entry` record binds the file's name, size and SHA-256 (4.4).
Labels and citations live in the record, not the payload. A delete writes no
payload, and no payload is ever rewritten or removed.

### 7.5 Re-entry: `what_am_i_working_with(page?)`

The first page's `data`:

```json
{"audit": "aqm3x7kd2hz5vw4ny", "condition": "open", "sealed_by": null, "revision": 7,
 "run": {"number": 2, "continuing": true},
 "allowances": {"turns": {"used": 41, "reported": 40, "estimated": 1, "limit": 200},
                "input_tokens": {"used": 1830211, "reported": 1801300, "estimated": 28911, "limit": 20000000},
                "output_tokens": {"used": 59214, "reported": 51022, "estimated": 8192, "limit": 400000}},
 "notices_used": {"reminder": false, "near_limit": false},
 "question": {"source": "question", "size": 46, "lines": 1},
 "materials": {"count": 3, "bytes": 1428},
 "entries": [{"id": "e1", "entry": "e1.v2.k7q4m2", "kind": "record_account", "label": "", "encoding": null,
              "size": 132, "preview": "The supplied excerpts support one restart…", "preview_complete": false,
              "problem": null}],
 "receipts": [{"run": 1, "tool_use_id": "toolu_01A…", "tool": "replace", "action": "replace",
               "target": "e1.v1.x2p7aa", "entry": "e1.v2.k7q4m2", "revision": 7}],
 "latest_refusals": [{"run": 1, "tool_use_id": "toolu_01C…", "tool": "record_observation",
                      "outcome": "refused", "reason": "citation_invalid", "revision": 6}],
 "gaps": [],
 "page": {"bound_revision": 7, "returned": 1, "total": 1, "complete": true}}
```

The envelope's `next` offers `list` for the materials and, while `complete` is
false, a `what_am_i_working_with` call with the `pg.` cursor for the next page.

- `condition` is `open`, `sealed` (with `sealed_by` `auditor` or `manager`) or
  `closed` (close was requested before any seal). `sealed_by` is null otherwise.
- `entries` lists the current selection in order. A preview is the first 200
  bytes on a character boundary and is marked as a preview; it is null for a
  `binary` artifact. `problem` is `missing` or `unreadable` when the payload
  could not be read for the preview, else null; digests are checked by `read`
  and `prepare`.
- `receipts` lists the 16 most recent `entry` records across placements, newest
  first: `run` and `tool_use_id` from its invocation, `tool`, `action`,
  `target` (the replaced or removed version's handle, null for an add), `entry`
  (the resulting handle, null for a delete) and `revision`.
- `latest_refusals` lists, newest first, for each tool of the arrangement, the
  latest result record across placements whose outcome is `refused` or
  `failed`, other than a replay: `run`, `tool_use_id`, `tool`, `outcome`,
  `reason` and `revision`.
- `gaps` lists each result record that could not be read, as `{run, call,
  problem}`: recorded data Stewart could not read, distinct from lost context.
- `allowances` split usage into reported and estimated as status does (5.6).
- A page holds up to 64 entries; later pages carry only `entries` and `page`.
  A page cursor is bound to its revision. After an intervening edit it is
  refused (`stale_view`), with a next call to start again.
- Re-entry is not a gate: no mutation requires it. It reports recorded facts,
  not what the auditor has read or concluded.

### 7.6 Prepare and submit

`prepare()` re-verifies the size and digest of each payload in the current
selection, claims `prepared/<n>` (4.3) and writes `answer.json` and `answer.md`
(QUESTION-FORMS) in it as exclusive files. No log record names an auditor
preparation unless it is sealed. It returns:

```json
{"prepared": "ap3.x6h2kq", "revision": 7, "entry_count": 5,
 "counts": {"record_account": 1, "record_observation": 3, "record_limit": 0, "record_artifact": 1},
 "notices": [{"reason": "section_unfilled", "tool": "record_limit",
              "message": "No record_limit entries are recorded."}],
 "rendering": {"source": "ap3.x6h2kq/rendering", "size": 2210},
 "selection": {"source": "ap3.x6h2kq/selection", "size": 3904}}
```

`counts` has one key per recording tool of the family, then `record_artifact`,
in tools order. `notices` has one `section_unfilled` per expected section with
no entry, in tools order. Missing sections and an empty answer never refuse. An
empty selection gives the single notice `answer_empty` ("No answer entries are
recorded.") and the rendering `No answer entries recorded.` Damaged selected
bytes refuse (`answer_damaged`). The run then ends `damaged`, and the reply's
`next` is empty: the auditor stops.

`submit(prepared, confirm = false)`:

| Case | Outcome and `data` |
| --- | --- |
| Dry run, current handle | completed: `dry_run: true`, `revision`, `entry_count`, `rendering` |
| Revision changed since prepare | refused `stale_preparation`: `revision_now`, next `prepare` |
| `confirm: true`, current, slot won | completed: `seal`, `sealer: "auditor"`, `sealed_at`, `revision`, `manifest_sha256` |
| Repeat of an accepted confirmed submit | completed: the same `seal`, `already_sealed: true` |
| Manager close won the order | refused `authoring_ended`: `{"ended_by": "close", "close_requested_at": …, "seal": <handle or null>, "sealer": <"auditor", "manager" or null>}` |
| Seal publication uncertain | failed `seal_uncertain`, `effects.seal: "unknown"`; next: the same submit, which returns the recorded seal or seals |

Neither reply claims delivery, a stopped process or close. After a confirmed
submit the run delivers and ends (6.3), so its reply is recorded but not sent.

## 8. Seal, return and delivery

### 8.1 Seal

A seal binds one preparation. The auditor seals the preparation of its handle.
Close prepares the selection current at its `close_requested` the same way, into
a new `prepared/<n>`, and seals that. To seal, Stewart:

1. re-verifies the preparation's files against their digests, and each selected
   payload's size and digest;
2. writes `seal/manifest-<k>.json` (8.2) as an exclusive file, claiming `k`;
3. publishes the `seal` record naming the preparation, the manifest and its
   digest (4.4).

If the slot is taken by an edit, the auditor's submit is stale. If it is taken by
`close_requested`, authoring has ended. If it is taken by another `seal`, that
seal stands. The prepared bytes never change. The seal handle `seal.<check>`
binds the manifest's SHA-256 (2.3).

When close cannot read or verify a selected entry's payload, it still seals. The
manager seal binds the recorded identities and digests of the whole selection:
the preparation's `answer.json` writes that entry in its unproduced form
(QUESTION-FORMS), no `answer.md` is written, and the manifest's `unproduced`
lists the entry (role `entry`, named by its ID) and `answer.md` (role
`rendering`), each with its failure. The renderer is not run when any entry is
unproduced.

### 8.2 The return package

A package is a new directory `stewart-return-<audit-id>-<nnn>` inside the
destination, where `nnn` is the delivery attempt number, zero-padded to at least
three digits (attempt 1 is `001`). It is created with mode 0700 and its files
with 0600. It contains only:

| Member | Role | Content |
| --- | --- | --- |
| `manifest.json` | `manifest`, in delivery records only | The seal manifest, byte for byte |
| `answer.json` | `answer` | The structured answer (`stewart.answer/1`, QUESTION-FORMS) |
| `answer.md` | `rendering` | The prepared rendering |
| `artifact-<id>.bin` | `artifact` | Each selected artifact's exact bytes (`artifact-e4.bin`); a text artifact's are UTF-8 |

The manifest (`stewart.return/1`) is one line of compact JSON followed by an LF,
with keys in the order shown and strings escaped as in `stewart.answer/1`:

```
{"schema":"stewart.return/1","audit":"aqm3x7kd2hz5vw4ny","store":"s7tq2bk6xm3ra4pfe","family":"open-inquiry/1","renderer":"stewart.render/1","writer":"3f1c…","seal":{"actor":"auditor","sealed_at":"2026-11-02T15:20:04.118Z"},"revision":9,"members":[{"name":"answer.json","role":"answer","size":3904,"sha256":"…"},{"name":"answer.md","role":"rendering","size":2210,"sha256":"…"},{"name":"artifact-e4.bin","role":"artifact","size":120,"sha256":"…"}],"unproduced":[]}
```

- `audit` and `store` are the identifiers; `family` is the family ID and
  version; `renderer` the renderer version; `writer` the SHA-256 of the sealing
  executable (4.7).
- `seal.actor` is `auditor` or `manager`. `sealed_at` is when Stewart wrote the
  manifest, immediately before publishing the seal (UTC, milliseconds).
- `revision` is the sealed selection's answer revision.
- `members` lists `answer.json`, then `answer.md` unless it is unproduced, then
  each artifact of a produced entry in selection order, each with `name`,
  `role`, `size` and `sha256`. Digests are lowercase hex.
- `unproduced` lists, in selection order, each unproduced entry as
  `{"name":"e3","role":"entry","failure":"damaged","dependency":null}`, with
  failure `missing`, `unreadable` or `damaged`; then an unproduced rendering as
  `{"name":"answer.md","role":"rendering","failure":"not_rendered","dependency":["e3"]}`,
  naming the unproduced entries. An unproduced artifact entry covers its
  `artifact-<id>.bin`. It is `[]` when everything was produced.

The manifest does not contain the seal handle; the handle binds the manifest
(2.3). It verifies the package without the archive. The question, receipt,
arrangement, access log, run summaries and conversations are never members.

### 8.3 Delivery

1. Claim `delivery/<attempt>.json` (4.3) and write the attempt's plan in it, a
   record of kind `delivery_plan`:

   ```json
   {"attempt": 3, "seal": "log/22.json", "manifest": "seal/manifest-1.json", "manifest_sha256": "…",
    "destination": {"path": "/home/ana/returns2", "source": "replacement", "device": 64769, "inode": 1835011},
    "package": "stewart-return-aqm3x7kd2hz5vw4ny-003", "replaces": 2, "by": "close",
    "members": [{"name": "manifest.json", "role": "manifest", "size": 611, "sha256": "…", "source": "seal/manifest-1.json"},
                {"name": "answer.json", "role": "answer", "size": 3904, "sha256": "…", "source": "prepared/3/answer.json"},
                {"name": "answer.md", "role": "rendering", "size": 2210, "sha256": "…", "source": "prepared/3/answer.md"},
                {"name": "artifact-e4.bin", "role": "artifact", "size": 120, "sha256": "…", "source": "payload/e4.v1.bin"}]}
   ```

   `members` is `manifest.json`, then the manifest's members in order, each with
   its archive source; it is null when the manifest cannot be read and checked
   against the seal's digest (membership unknown). `device` and `inode` are null
   when the destination cannot be opened. `replaces` is the newest earlier
   attempt of the seal that ended `partial`, `failed` or `name_taken`, or the
   `verified_with_losses` attempt whose delivery-stage losses this attempt
   retries (5.8), else null.
2. Publish `delivery_planned` (4.4).
3. If membership is unknown or the destination cannot be opened, end `failed`.
   Otherwise check location overlap (4.1; `failed`, cause `location_overlap`)
   and create the package with `mkdirat`. If the name is taken, publish
   `delivery_ended` `name_taken` and plan a new attempt from step 1; one
   invocation plans at most 16 attempts, then reports the delivery incomplete.
   An existing path is never adopted, emptied or overwritten.
4. Write `manifest.json` first, then each member in plan order, as exclusive
   files, each synced. Each member's source is read through descriptors and
   checked for size and digest before it is written. A source that is missing,
   unreadable or damaged is not written (`source_missing`, `source_unreadable`,
   `source_damaged`), and the next member follows; for `manifest.json` this
   makes membership unknown. A write failure stops the attempt, and later
   members are `not_attempted`. Then sync the package and the destination.
5. Reopen each written member by name through descriptors and verify its size
   and digest (`not_verified` on a mismatch).
6. Publish `delivery_ended` with one outcome:

| Outcome | Meaning | Confirmation token | Loss IDs |
| --- | --- | --- | --- |
| `verified` | Every member written and verified; nothing unproduced | yes | none |
| `verified_with_losses` | Every member the archive supplied was written and verified; some members were unproduced at seal or could not be supplied from the archive | yes | one per loss |
| `partial` | The package and manifest were written, but a member the archive supplied was not written or not verified | no | none |
| `failed` | Membership unknown, the destination unusable, the package not created or the manifest not written; with its cause | no | none |
| `name_taken` | The package name existed (step 3) | no | none |

A `failed` attempt's `cause.error` is an errno name, `manifest_unavailable`,
`location_overlap`, `signal` or `process_gone`. An attempt that ended `partial`,
`failed` or `name_taken` is incomplete; the delivery continues through `close`
or `close --destination DIR` (5.8).

A run delivers after an auditor seal, before exiting. Close delivers any other
owed copy. Continuation after a lost reply reads these records rather than
copying again. Stewart never removes anything at a destination.

### 8.4 Confirmation and loss

The confirmation token for delivery attempt `n` is `cf<n>.<check>`, issued for a
`verified` or `verified_with_losses` attempt. Its check binds the manifest digest
and the attempt's `delivery_ended` record (2.3). The token is outstanding while
the attempt is the newest verified one, `closed` is not published and
confirmation is required: the attempt ended after the first `close_requested`,
or it has losses. Status shows the token while it is outstanding.

A loss ID is issued for each loss of a `verified_with_losses` attempt, and only
then. Its member token (2.3) is the entry ID of an unproduced entry, or the
member name with `.` replaced by `-` (`loss.answer-md.p6w2ze`,
`loss.artifact-e4-bin.k2d7xq`). Its failure record is that attempt's
`delivery_ended`: it names the member, its failure and stage, the seal and the
verified members delivered. Status lists loss IDs only for known members;
unknown membership has none.

## 9. Failure traces

Each trace is a literal acceptance fixture. The driver reproduces it against the
release binary, using controlled synchronization or kills at the named points,
and compares the result with an independent witness. `→` shows the reply;
`[log n: kind]` shows the log record published.

**T1. Lost commission reply.**
`prepare` → `mp1` `[log 2: prepared]`. `commission REF mp1 --i-am-finished`
publishes `[log 3: intake_planned]` `[log 4: accepted]`, then is killed before
writing stdout. The manager edits `materials/a.py`. `commission REF mp1
--i-am-finished` → completed, `already_accepted: true`, the same `receipt_sha256`.
No new intake is planned.

**T2. Changed selection.** After `prepare` → `mp1`, a file is edited. `commission`
→ refused `selection_changed`, `effects: {acceptance: absent, attempt: partial}`,
`changed: ["materials/a.py"]` `[log 4: intake_ended selection_changed]`. Then
`prepare` → `mp2`, `commission REF mp2 --i-am-finished` → completed.

**T3. Intake killed mid-copy.** Kill after the second capture file. `status` →
`condition: "intake_failed"`, and `data.evidence` holds
`{"fact": "intake 1 ended without acceptance", "evidence": "intake_planned without outcome; lock free"}`.
The next `commission` publishes `[intake_ended process_gone]`, then plans
attempt 2 with fresh capture names. Attempt 1's files remain.

**T4. Uncertain acceptance.** An injected failure in syncing the log directory
after linking `accepted` → failed `acceptance_record_uncertain`,
`acceptance: unknown`. `status` reads the log. If `accepted` is present,
`accepted: "yes"`. If the log is damaged before any readable `accepted`,
`acceptance_uncertain`, naming the bad records; `commission` refuses
`log_damaged` and close stays unfinished. A fresh capture is never offered by
default.

**T5. Stale entry target.** `replace(e2.v1…)` → `e2.v2`. A second
`replace(e2.v1…)` → refused `stale_entry`, `current: "e2.v2…"`, next
`read`/`replace` of `e2.v2…`. `delete(e2.v1…)` → refused `stale_entry`; `e2.v2`
remains.

**T6. Submit races close.** The auditor holds `ap3` for revision 7. The driver
pauses the run just before its seal `linkat`, runs `close REF` to
`[log 20: close_requested]`, then releases the run. `submit(ap3, confirm: true)`
→ refused `authoring_ended` with `ended_by: "close"` and `close_requested_at`;
its `seal` and `sealer` are null unless close has already sealed. Close seals
revision 7 as manager, and the driver checks the manager seal through status.
The reverse ordering → the auditor seal stands and close keeps it. Across
repeated runs each outcome names its actual actor.

**T7. Kill after an entry, before its result.** The driver kills the run after
`[log 12: entry add e5]` is linked and before its `result-<c>.json`
(`entry.after_link=kill`). `status` →
`interrupted`. `run REF` → `[run_ended process_gone]`, `[run_started 2]`, first
message with question and continuation notice. The reacting fake calls
`what_am_i_working_with`, finds `e5` in `entries` and `receipts`, and does not add
it again. The sealed return contains each goal entry once.

**T8. Ordinary ending.** The fake ends a turn without submitting → reminder
`[notice reminder]`. It ends again → `[run_ended ended_unsubmitted]`, exit 0.
`run REF` → refused `authoring_ended` ("ordinary ending without submission"),
next `close`. `close REF` → manager seal, delivery, closure `unfinished`,
`unfinished_reason: "awaiting_confirmation"`, `confirmation: "cf1…"`.
`close REF --confirm cf1…` → completed, `closure: complete`,
`placement: "confirmed"`.

**T9. Delivery to an unavailable destination.** The destination is removed after
commission. Auditor seal → run delivery attempt 1 `[delivery_ended failed]`,
then `[run_ended sealed]`. `close REF` → delivery attempt 2 at the commissioned
destination, `[delivery_planned replaces: 1]` `[delivery_ended failed]`;
completed, closure `unfinished`, `unfinished_reason: "delivery_incomplete"`, no
token, next `close`, whose explanation offers `--destination DIR`. `close REF --destination
/home/ana/returns2` → attempt 3, `[delivery_planned replaces: 2]`, verified in
`stewart-return-<audit-id>-003`, token `cf3…`. `close REF --confirm cf3…` →
closed. All three attempts stay recorded.

**T10. Damaged element at close.** A payload file is corrupted in the archive
after it is recorded. `close REF` → manager seal whose `answer.json` writes `e3`
in its unproduced form and whose manifest lists as `unproduced` `e3` (role
`entry`) and `answer.md` (role `rendering`); the renderer is not run. Delivery
`verified_with_losses`, token `cf1…`, loss IDs `loss.e3…` and `loss.answer-md…`.
`close REF --confirm cf1…` → refused `surrender_required`, naming the loss IDs.
`close REF --confirm cf1… --surrender loss.e3… --surrender loss.answer-md…` →
closed with the losses recorded. Status shows `delivered.verified: false` with
the `losses` list and never calls this delivery complete.

**T11. Diagnostic write also fails.** With `diag/` made unwritable, a refused
commission replies with `causes` [original, diagnostic write] and
`diagnostic: "reported_only"`.

**T12. Empty answer and missing sections.** `prepare()` with no entries →
completed, notice `answer_empty`, rendering `No answer entries recorded.`;
`submit(ap1, confirm: true)` → sealed. A separate audit with only an account
entry → notices for each other section, and submit succeeds without
acknowledgment.

**T13. Run held elsewhere.** Run A holds the lock. `run REF` in another process
→ refused `run_held` with holder observations. `close REF` → `[close_requested]`;
run A stops within the wait and records `stopped_by_close`; close proceeds. If
run A is stopped with SIGSTOP, close replies unfinished,
`unfinished_reason: "run_still_held"`, and a later `close REF` resumes after the
lock is released.

**T14. Lost close replies.** After an ordinary ending, `close REF` with
`delivery.after_ended=kill` publishes `[close_requested]`, `[seal]`,
`[delivery_planned]` and `[delivery_ended verified]`, then dies without a reply.
`status` → `awaiting_confirmation`, `deliveries[0].confirmation: "cf1…"`.
`close REF` from another directory → the same attempt and token, closure
`unfinished`, no new attempt. `close REF --confirm cf1…` with
`close.after_closed_link=kill` → `[closed]`, no reply. `status` → `closed`;
`close REF` → `already_closed: true` with the recorded outcome.

**T15. Context window exhausted.** The fake answers with `stop_reason`
`model_context_window_exceeded` and one `record_observation` call. Stewart
executes it (`[entry add]`), sends no further request, records
`[run_ended interrupted context_exhausted]` and exits 5; the call's result stays
in its result record. `run REF` → `[run_started 2]`, whose first message holds
the question and the continuation notice.

**T16. Provider unavailable.** The fake answers request 1 with HTTP 529,
`retry-after: 0` and an `overloaded_error` body, four times. The run records
four attempt records with `then: "retry"` three times and `"end"` once, charges
nothing, records `[run_ended interrupted provider_unavailable]` with
`provider.status: 529` and `error_type: "overloaded_error"`, and exits 5. A
`retry-after: 61` on the first attempt ends the placement the same way after one
attempt. A 413 `request_too_large` ends it after one attempt with cause
`provider_rejected`.

## Appendix A. Reasons

Manager:

| Reason | Meaning |
| --- | --- |
| `archive_unspecified` | `new` has neither `--archive` nor `STEWART_ARCHIVE` |
| `archive_not_a_store` | Root exists, is not empty and has no store marker |
| `archive_unavailable` | Reference root cannot be opened |
| `archive_replaced` | Root holds a different store |
| `archive_moved_or_copied` | Store marker matches but the root's inode or birth time differs; read-only |
| `archive_filesystem_unsupported` | Archive is not on ext4, xfs or btrfs |
| `archive_path_symlink` | The archive root's path has a symlink component (4.1) |
| `reference_invalid` | Not a well-formed `stw1:` reference |
| `reference_unknown` | No such audit in this store |
| `writer_mismatch` | Mutating binary is not the recorded writer |
| `log_damaged` | The log is not readable (4.4); every mutation refuses |
| `location_overlap` | Archive, folder or destination overlap, by device and inode (3.2, 3.3, 4.1, 8.3) |
| `folder_incomplete` | `question.md` or `materials/` is missing (3.1) |
| `unexpected_root_entry`, `unsupported_entry`, `name_invalid`, `material_not_text`, `bound_exceeded` | Intake mechanical rules (3.1–3.3) |
| `source_unreadable` | A source file could not be opened or read during prepare or commission |
| `front_matter_invalid` | Missing or malformed `---` delimiters, mixed line endings, or a duplicate or unknown key (3.2) |
| `setting_missing`, `setting_invalid`, `question_empty` | Front matter and body (3.2) |
| `destination_invalid` | The front matter's destination (3.2), or `close --destination DIR` (5.8), is not an existing absolute directory |
| `affirmation_missing` | `commission` without `--i-am-finished` |
| `handle_invalid` | Handle of wrong kind, store, audit or check, including a loss ID that is not one of the confirmed attempt's |
| `selection_changed` | Source differs from the prepared selection |
| `intake_in_progress` | Commission could not take the active lock |
| `acceptance_uncertain` | Status condition: acceptance cannot be established, because the log is damaged before any readable `accepted` (5.6); commission then refuses `log_damaged` |
| `acceptance_record_uncertain` | Publishing acceptance failed partway |
| `capture_failed`, `capture_unverified` | Writing or verifying a capture failed |
| `receipt_record_failed` | Writing the acceptance receipt failed |
| `reference_already_accepted` | This reference already has an accepted commission (prepare; commission with a different handle) |
| `reference_closed` | Close was requested |
| `not_accepted` | Receipt or run before acceptance |
| `run_held` | Another process holds the active lock |
| `authoring_ended` | Run after a seal, an ordinary ending, a limit stop or damage (named in `data.ended_by`) |
| `commission_damaged` | Run found the accepted receipt, arrangement or a capture missing, unreadable or not matching its digest (5.7) |
| `provider_key_missing`, `provider_key_invalid`, `provider_url_invalid`, `provider_proxy_invalid` | Run environment (5.7, 6.1) |
| `record_failed` | An archive write failed; effects state what is known |
| `intake_still_running`, `run_still_held`, `close_in_progress`, `delivery_incomplete`, `awaiting_confirmation` | Close unfinished, as `data.unfinished_reason` (continue with `close`) |
| `log_damaged` as `data.unfinished_reason` | Close unfinished on a damaged log; close publishes nothing |
| `confirmation_mismatch` | A token that is not the newest verified attempt's, or a confirmation before launch |
| `surrender_required` | The confirmed attempt has losses the call did not name |
| `delivery_already_verified` | `--destination` after a verified attempt |
| `destination_not_replaceable` | `--destination` before any incomplete attempt of the seal |
| `item_unknown`, `item_damaged`, `item_missing`, `item_unreadable`, `item_unsupported` | Receipt readback |

Auditor: `input_invalid` (with JSON pointer), `input_too_large`,
`tool_unknown`, `source_unknown` (with hints), `source_unreadable` (a
verified capture could not be read during the placement), `range_invalid`,
`citation_invalid`, `quote_not_found`, `quote_ambiguous`, `stale_entry`,
`entry_deleted`, `fields_invalid`, `stale_view`, `stale_preparation`,
`answer_damaged`, `retained_payload_cap`, `retained_payload_reserve_exhausted`,
`entry_limit`, `selection_limit`, `authoring_ended` (seal or close, named),
`invocation_id_reused`, `handle_invalid`, `seal_uncertain`, `record_failed` (an
archive write failed; effects state what is known). Notices:
`section_unfilled`, `answer_empty`, `label_duplicate`,
`folder_already_referenced`.

Recorded values:

| Field | Values |
| --- | --- |
| `intake_ended.outcome` | `selection_changed`, `source_unreadable`, `capture_failed`, `capture_unverified`, `receipt_record_failed`, `closed`, `process_gone` |
| `run_ended.ending` | `sealed`, `ended_unsubmitted`, `limit_reached`, `stopped_by_close`, `damaged`, `interrupted` |
| `run_ended.cause` | for `interrupted`: `signal`, `provider_unavailable`, `provider_rejected`, `context_exhausted`, `provider_refusal`, `max_tokens`, `protocol_anomaly`, `archive_write_failed`, `process_gone`; otherwise null |
| `provider_attempt.outcome` | `response`, `response_undecodable`, `http_error`, `timeout`, `connection_failed`, `connection_lost`, `aborted_by_close`, `aborted_by_signal` |
| `delivery_ended.outcome` | `verified`, `verified_with_losses`, `partial`, `failed`, `name_taken` |
| Delivery member `failure` | `source_missing`, `source_unreadable`, `source_damaged`, `write_failed`, `not_verified`, `not_attempted` |
| Loss and unproduced `failure` | `missing`, `unreadable`, `damaged`; `not_rendered` for the rendering |
| `closed.outcome` | `closed_without_acceptance`, `closed_after_acceptance_before_launch`, `closed_delivered`, `closed_with_surrendered_losses` |

## Appendix B. Bounds and constants

| Item | Value |
| --- | --- |
| Intake bounds | CONTRACTS bounds table |
| Auditor tool input | 4 MiB per call |
| Read page | 65,536 bytes of text; 49,152 bytes of binary, as base64 |
| Search text; hits per page; context per page | 1,024 bytes; 128; 32 KiB |
| Context per hit | 240 bytes |
| Citations per entry; ambiguous occurrences listed | 64; 8 |
| Label | 200 characters |
| List page | 128 materials |
| Re-entry entries per page; receipts; preview | 64; 16; 200 bytes |
| Answer | 256 entries; 64 MiB per entry; 256 MiB selection; 1 GiB retained cap; 64 MiB reserve |
| Close waits | 10 s for intake, 30 s for a run |
| Watcher interval | 250 ms |
| API version; `max_tokens` per request | `2026-10-21`; 16,000 |
| Provider attempts; delays; retry-after ceiling; request timeout | 4; 2, 8, 30 s; 60 s; 600 s |
| Response body captured and decoded | 32 MiB |
| Recorded response headers | `content-type`, `request-id`, `retry-after` |
| Recorded error message | 1,024 bytes |
| Minimum output allowance for a request | 1,024 tokens |
| Near-limit threshold | 20% remaining |
| Delivery attempts planned by one invocation | 16 |
| Front matter limits | turns 1–10,000; input 1–2×10⁹; output 1–2×10⁸ |
| Scaffold defaults | 200 turns; 20,000,000 input; 400,000 output |

## Appendix C. Test builds

Acceptance needs deterministic failure points and sabotage controls (ACCEPTANCE,
"Rules every check follows"). They exist only in a test build, compiled with
the cargo features `fault-injection` and `sabotage` and named `stewart-test`.
The release binary is built without them and contains neither the code nor the
environment variable names below; the suite checks this against the test build
as its firing control. The names are `STEWART_TEST_FAULT`,
`STEWART_TEST_FAULT_DIR`, `STEWART_TEST_SABOTAGE`, `STEWART_TEST_TLS_ROOT`,
`STEWART_TEST_PROVIDER_TIMEOUT` and `STEWART_TEST_RETRY_DELAYS`; the last three
are compiled with `fault-injection`.

### C.1 Fault points

`STEWART_TEST_FAULT` holds comma-separated `point=action` items. A point may take
one argument after a colon; an item without an argument matches every argument
of its point. Actions:

| Action | Effect at the point |
| --- | --- |
| `kill` | The process sends itself SIGKILL |
| `eio`, `enospc`, `epipe` | The operation at the point fails with that error |
| `corrupt` | The bytes just written are altered by one bit after writing and before verification |
| `pause` | The process creates `$STEWART_TEST_FAULT_DIR/<point>.paused` exclusively, then waits until `<point>.go` exists there (polling every 10 ms; after 60 s it aborts). A point pauses once per process. |

Manager foundation:

| Point | Where |
| --- | --- |
| `prepare.before_prepared_link` | After prepare's records are written, before `prepared` is linked |
| `commission.after_capture:<k>` | After the k-th capture file (1-based) is written and synced |
| `commission.source_read:<name>` | Reading the source file with that public name |
| `commission.capture_write` | Writing any capture file |
| `commission.capture_corrupt` | After writing a capture file (use with `corrupt`) |
| `commission.receipt_write` | Writing the attempt's receipt |
| `commission.before_accepted_link` | Before `accepted` is linked |
| `commission.accepted_dirsync` | Syncing the log directory after linking `accepted` |
| `commission.after_accepted_link` | After `accepted` is published, before the reply |
| `log.publish:<kind>` | Immediately before linking a log record of that kind |
| `close.before_closed_link` | Before `closed` is linked |
| `diag.write` | Writing any diagnostic record |
| `reply.write` | Writing the reply to stdout |

Records, the answer protocol and the run:

| Point | Where |
| --- | --- |
| `stage.torn:<kind>` | Writing the stage file of a linked record of that kind (a log kind, `provider_attempt` or `tool_result`): the first half of its bytes is written and synced, then the action runs. With `kill` it leaves a torn stage file. |
| `log.dirsync:<kind>` | Syncing the log directory after linking a record of that kind; for `accepted`, `commission.accepted_dirsync` names the same point. With `eio` on `seal` it gives `seal_uncertain`. |
| `runs.publish:<kind>` | Immediately before linking a `provider_attempt` or `tool_result` record |
| `run.after_started` | After `run_started` is published and `runs/<n>` created, before the first request |
| `provider.request_capture` | Writing a request capture |
| `provider.sent:<k>` | After request k's body is written to the connection, before its response is read |
| `provider.response_capture` | Writing a response capture |
| `run.between_turns:<k>` | After every block of response k is executed and recorded, before request k+1 is captured |
| `tool.before:<tool>` | After a call to that tool is captured, before it runs |
| `entry.payload_write` | Writing an entry payload |
| `entry.payload_corrupt` | After writing an entry payload (use with `corrupt`); the entry records the intended digest |
| `entry.after_link` | After an `entry` record is linked, before the call's result record |
| `prepared.write` | Writing a file under `prepared/<n>`, for the auditor or close |
| `seal.manifest_write` | Writing the seal manifest |
| `seal.after_link` | After a `seal` is published, before the reply or delivery |

Delivery and close:

| Point | Where |
| --- | --- |
| `delivery.source_read:<member>` | Reading that member's archive source |
| `delivery.member_write:<member>` | Writing that member at the destination |
| `delivery.member_corrupt:<member>` | After writing that member (use with `corrupt`) |
| `delivery.after_member:<k>` | After the k-th planned member (1 is `manifest.json`) is written and synced |
| `delivery.after_ended` | After `delivery_ended` is published, before the run or close continues |
| `close.after_requested` | After `close_requested` is published |
| `close.after_seal` | After close's seal is published, before delivery |
| `close.after_closed_link` | After `closed` is published, before the reply |

The ACCEPTANCE kill points map to these: during a provider request,
`provider.sent:<k>`; while a tool reply is being written,
`stage.torn:tool_result`; between turns, `run.between_turns:<k>`; while a record
is being appended, `stage.torn:<kind>`; after an entry is linked and before its
result, `entry.after_link`; just before the seal `linkat`, `log.publish:seal`
(with `pause` for the races of T6); kill before and after sealing,
`log.publish:seal` and `seal.after_link`; during delivery after the k-th member,
`delivery.after_member:<k>`; after copying and before close's reply,
`delivery.after_ended`; after confirmation and before its reply,
`close.after_closed_link`.

Provider and transport, for the fake provider:

| Variable | Effect |
| --- | --- |
| `STEWART_TEST_TLS_ROOT` | Absolute path of a PEM file, at most 1 MiB, holding one or more certificates. They are added to the trust roots for the provider connection, directly or through `HTTPS_PROXY`. A missing, unreadable or certificate-free file refuses `run` before any request (`test_tls_root_invalid`). |
| `STEWART_TEST_PROVIDER_TIMEOUT` | Request timeout in seconds, 1–600, in place of the pinned 600; attempt records state the value used. Any other value refuses `run` before any request (`test_variable_invalid`). |
| `STEWART_TEST_RETRY_DELAYS` | Three comma-separated delays in milliseconds, each 0–30,000, in place of 2, 8 and 30 seconds; a `retry-after` value still applies. Any other value refuses `run` before any request (`test_variable_invalid`). |

### C.2 Sabotage controls

`STEWART_TEST_SABOTAGE` names one control. Each breaks exactly one property, so
the check for that property must fail. The claims are ACCEPTANCE's.

| Name | Broken property |
| --- | --- |
| `accept_without_affirmation` | Commission accepts without `--i-am-finished` (C11) |
| `accept_changed_source` | Commission skips the digest comparison and final rescan (C11, C17) |
| `skip_hidden_entries` | The scan omits names beginning with `.` (C19) |
| `normalize_newlines` | Captures convert CRLF to LF (C2, C19) |
| `follow_symlinks` | The scan follows symlinks instead of refusing them (C19) |
| `readback_live_source` | `receipt --read` reads the preparation folder instead of the capture (C15) |
| `regenerate_arrangement` | `receipt --read arrangement` regenerates the arrangement instead of returning the pinned bytes (C15, C19) |
| `rewrite_record_in_place` | Publishing a log record overwrites an existing name (C6) |
| `remove_partial_on_retry` | A new intake attempt removes the previous attempt's captures (C6, C17) |
| `unknown_as_absent` | An unreadable log is treated as acceptance absent (C17) |
| `select_newer_store` | A store identifier mismatch is ignored (C18) |
| `accept_unknown_field` | Unknown front matter keys are ignored (C20) |
| `omit_effects_on_refusal` | Refusals, manager and auditor, omit `effects` (C9, C20) |
| `whole_from_one_member` | `receipt --verify` reports the whole commission verified after one member verifies (C15) |
| `extra_tool` | Requests carry one tool definition beyond the arrangement's (C1) |
| `arrangement_mismatch` | Requests carry an orientation block differing by one word from the pinned one, which stays recorded unchanged (C1) |
| `read_live_source` | `read` serves the preparation folder's current file instead of the capture (C2) |
| `normalize_read` | `read` returns CRLF as LF (C2, C19) |
| `paraphrase_question` | The first message carries the question body with leading and trailing whitespace removed (C2, C7) |
| `read_truncate_silently` | A `read` page that ends before the source's end reports `complete: true` with no next call (C19) |
| `search_omit_last_page` | The page before a search's last page reports `complete: true` (C19, C20) |
| `torn_as_entry` | An unlinked `entry` stage file counts as a recorded entry (C3) |
| `merge_equal_adds` | An add equal in kind, label, text and citations to a current entry returns that entry and records nothing (C3) |
| `replay_reexecutes` | A repeated `tool_use` ID with the same input is executed again (C3) |
| `stale_target_overwrites` | `replace` and `delete` of a superseded version act on the current version (C3, C20) |
| `manager_seal_as_auditor` | Close's seal records `actor: "auditor"` (C3, C5) |
| `reentry_omit_entry` | Re-entry omits the last current entry (C4) |
| `reentry_truncate_page` | A re-entry page stops after 32 entries and reports `complete: true` (C4) |
| `reentry_omit_last_page` | The re-entry page before the last reports `complete: true` (C4, C20) |
| `reentry_mix_revisions` | A page cursor bound to an earlier revision serves the current revision instead of `stale_view` (C4, C20) |
| `reentry_placement_allowances` | Re-entry reports the current placement's usage instead of the cumulative usage (C4) |
| `drop_last_entry` | Preparation's selection and rendering omit the last current entry (C5) |
| `skip_delivery_verification` | Delivery records its outcome without reading members back (C5) |
| `deliver_conversation` | Delivery adds `conversation.json`, the run's request captures, to the package (C5) |
| `regenerate_rendering` | Delivery writes a fresh rendering with a changed first line in place of the sealed `answer.md` (C5) |
| `render_conclusion` | The renderer appends a line `No issues found.` to every rendering (C5, C7) |
| `remove_superseded_payload` | `replace` removes the superseded payload file (C6, C18) |
| `remove_partial_package` | A new delivery attempt removes the previous attempt's package (C5, C6, C8) |
| `skip_search_capture` | `search` calls get no call capture or result record (C6) |
| `framing_task_elsewhere` | Open inquiry and comparison arrangements pin the inquiry-framing instructions (C7) |
| `grade_support` | Recorded citations gain `"supports":true` under `stewart` (C7, C14) |
| `block_incomplete` | Auditor `prepare` refuses when a section is unfilled (C7) |
| `reset_notice_allowance` | A continuing placement treats the reminder and the near-limit notice as unused (C7, C13) |
| `skip_confirmation` | Close publishes `closed` right after a delivery it made (C8) |
| `seal_as_stopped` | With a seal recorded, close does not wait for a held run and reports `run: "ended"` (C8) |
| `empty_return_before_launch` | Close before launch seals an empty selection as manager and delivers it (C8) |
| `slow_list` | `list` sleeps 500 ms before replying (C9) |
| `relative_run_line` | The commission reply and receipt give the run line with the writer path relative to the commissioning directory (C12) |
| `commission_over_network` | Commission refuses without `ANTHROPIC_API_KEY` and connects to the provider before accepting (C12) |
| `reset_limits_on_continuation` | A continuing placement counts usage from zero (C13) |
| `fresh_ledger_on_continuation` | A continuing placement ignores entries recorded before its `run_started` (C13) |
| `drop_refused_capture` | A refused `record_<kind>` call gets no call capture or result record (C14) |
| `manifest_verdict` | The return manifest gains `"verdict":"complete"` (C14) |
| `ended_as_submitted` | Status reports `sealed.by: "auditor"` after an ordinary ending or a limit stop without a seal (C16) |
| `seal_as_delivered` | Status reports `delivered.verified: true` whenever a seal exists (C16, C20) |
| `unknown_membership_empty` | With the manifest unreadable, delivery writes an empty return and records it `verified` (C5, C16) |
| `stale_preparation_retargets` | `submit` with a stale auditor preparation handle seals the current selection (C20) |
| `prepare_claims_seal` | Auditor `prepare` replies add `"sealer":"auditor"` (C20) |
| `leak_custody_path` | Auditor `read` replies add the archive path as `data.archive` (C20) |
| `accept_unknown_tool_field` | Auditor tool inputs ignore unknown keys (C20) |
| `seal_uncertain_as_none` | A seal whose publication is uncertain is reported with `effects.seal: "none"` (C20) |
| `submit_claims_delivery` | A confirmed `submit` reply adds `"delivered":true` to its data (C20) |

Sabotage items in ACCEPTANCE that are not build flags:

| Item | Disposition |
| --- | --- |
| C7, "requires a module for open inquiry" | Not applicable in this release: no module mechanism exists, so no build can require one. The C7 open-inquiry pass case stands with its differing and invariance cases. |
| C19, "auto-expand an archive" | Not applicable: no expansion code exists to enable. Archive-format materials are raw text cases under C19. |
| C5, "a payload corrupted in Stewart's storage before delivery" | A deliberately broken input (an "Also" case): the driver alters a payload file, or uses `entry.payload_corrupt` or `delivery.source_read`. |
