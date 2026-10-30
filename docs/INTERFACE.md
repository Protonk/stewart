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
| `retained` | manager refused or failed | Archive locations holding attempts, partials and diagnostics. |
| `causes` | failed, or `effects.diagnostic` is `reported_only` | The original cause first, then any reporting failure. |
| `next` | always | Supported next calls, each with an explanation (1.5). May be empty. |
| `data` | completed; refused when useful | Operation data, such as the current entry handle on a stale target. |

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
| 0 | Completed. For `run`: the placement ended and its ending is recorded, other than interrupted. |
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
| `sc` | SHA-256 of the search text, the scope searched, and the position |
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
    payload/                    answer entry bytes, one exclusive file per version
    prepared/<n>/               auditor preparation: answer.json, answer.md
    seal/manifest-<k>.json      return manifest written at seal
    runs/<n>/                   per placement: provider exchanges, tool calls, observations
    delivery/<attempt>.json     delivery attempt detail
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
  interrupted publication, never as a record.

Every numbered name is claimed, never assumed free: `prep/<n>`, `prepared/<n>`,
`seal/manifest-<k>.json`, `intake/<attempt>`, `delivery/<attempt>.json`,
`runs/<n>` and the files in `runs/<n>/` and `diag/`. A file is claimed with
`O_EXCL` and a directory with `mkdirat`; on `EEXIST` the writer advances to the
next number. The log record that uses a claimed name names it. Stage files are
created with `O_EXCL` under random names.

A file that no log record names, such as a receipt, a manifest or prepared
files, is reported by status as an unpublished candidate, never as a record.

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
| `run_started` | run | `accepted`; not ended (6.5); no `close_requested` |
| `entry` | auditor tools | A live placement; no seal, no `close_requested` |
| `seal` | submit, close | No earlier `seal`; for submit, no `close_requested`; for close, after its `close_requested` |
| `run_ended` | run; the next run's or close's reconciliation | Its `run_started` has no `run_ended` |
| `delivery_planned` | run, close | A `seal`; no `delivery_planned` without an outcome |
| `delivery_ended` | run; close, including its reconciliation | Its `delivery_planned` has no outcome |
| `notice` | run | No earlier notice of the same type (6.4) |
| `close_requested` | close | None earlier |
| `closed` | close | `close_requested`; none earlier; close's own conditions (5.8) |

`entry` covers add, replace and delete. Its body names the action, the
invocation (run number and `tool_use` ID), the target and resulting version,
the payload file and digest, and the resulting answer revision. The answer
revision is the number of `entry` records so far.

The launch point is the first `run_started`. Before it, close creates no answer.
After it, close seals the recorded selection if no seal exists. A crash between
`run_started` and the first provider request still counts as launched. Close then
seals an empty selection with manager attribution, which is an honest empty
return.

### 4.5 Unordered streams

Raw provider requests and responses, tool calls and their results, observations
and diagnostics are exclusive files under `runs/<n>/` and `diag/`, numbered
within their directory. Only the holder of the active lock writes in a run's
directory. Each request is captured as `runs/<n>/request-<k>.json`, holding its
`max_tokens`, the messages appended since the previous request and the SHA-256
of the full body; the full body is reconstructible from the arrangement and the
earlier captures. Each response is captured whole, one file per attempt. Each
tool call's raw `tool_use` block is captured as
`runs/<n>/call-<k>.json` before it is decoded. Its result is captured as
`runs/<n>/result-<k>.json`. The access log of C6 is the sequence of `list`,
`read` and `search` calls in these files. The run summary is the `run_ended`
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
the holder exits or is killed. The holder's process ID, start time, host name,
boot ID and invoking user ID are recorded in `run_started` as observations.

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
remains the account; later status reads it.

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
   return the recorded receipt with `data.already_accepted: true`. This is the
   lost-reply case, and it holds even if the source has changed since. If
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
closes anything. It reports:

```json
{"schema": "stewart.reply/1", "operation": "status", "outcome": "completed",
 "effects": {},
 "next": [{"argv": ["/usr/local/bin/stewart", "run", "stw1:…"], "why": "Continue the audit under the same limits."},
          {"argv": ["/usr/local/bin/stewart", "close", "stw1:…"], "why": "End authoring; the manager seals the recorded answer."}],
 "data": {"headline": {"accepted": "yes", "launched": "yes", "sealed": {"by": "none"},
                       "delivered": {"verified": false, "confirmed": false}, "closed": "no"},
          "condition": "interrupted",
          "summary": "Run 2 was interrupted before submission. The answer is not sealed.",
          "evidence": [{"fact": "run 2 interrupted", "evidence": "run_started without run_ended; lock free"}],
          "runs": {"count": 2, "held": false, "last": {"number": 2, "ending": "interrupted"}},
          "allowances": {"turns": {"used": 41, "reported": 40, "estimated": 1, "limit": 200},
                         "input_tokens": {"used": 1830211, "reported": 1801300, "estimated": 28911, "limit": 20000000},
                         "output_tokens": {"used": 59214, "reported": 51022, "estimated": 8192, "limit": 400000}},
          "answer": {"revision": 7, "entries": 5},
          "seal": null, "deliveries": [], "closure": null, "diagnostics": [],
          "provider_url_override": null,
          "receipt_line": ["/usr/local/bin/stewart", "receipt", "stw1:…"]}}
```

Headline values: `accepted` is `yes`, `no` or `unknown`; `launched` is `yes`,
`no` or `unknown`; `sealed.by` is `auditor`, `manager`, `none` or `unknown`;
`delivered` has `verified`, `confirmed` and, once a delivery is `verified` or
`verified_with_losses`, `location`. `delivered.verified` is true only for a
`verified` delivery. For `verified_with_losses` it is false, and `delivered`
adds `losses`, the list of loss IDs (8.4). `closed` is `no`, `unfinished`, `yes`
or `unknown`.

Each allowance gives `reported` (usage the provider reported), `estimated`
(usage charged without a provider report, 6.4) and `used`, their sum, which is
what the limit counts. `evidence` lists the observations behind the condition,
each `{fact, evidence}`.

Conditions, matching the CONTRACTS status table:

| `condition` | Established facts | Next calls |
| --- | --- | --- |
| `preparing` | Reference, maybe preparations; no intake | prepare, commission, close |
| `intake_in_progress` | Intake holds the lock | status, close |
| `intake_failed` | Last intake ended without acceptance | prepare, commission, close |
| `acceptance_uncertain` | Log damaged; no `accepted` among the readable records before the damage | status after the manager restores its storage; `new` for a new reference |
| `log_damaged` | Log damaged after a readable `accepted` | receipt; status after the manager restores its storage |
| `not_started` | Accepted; no `run_started` | run, close |
| `run_active` | Run holds the lock | close |
| `interrupted` | Placement ended interrupted, or `run_started` without `run_ended` and the lock free | run, close |
| `ended_unsubmitted` | Ordinary ending without submission | close |
| `limit_reached` | Cumulative limit exhausted | close |
| `damaged` | Run stopped on unrepairable damage | close |
| `sealed_undelivered` | Seal; no verified delivery | close, or close with a new destination after a partial or failed attempt |
| `delivered_open` | Verified delivery before any close request | close |
| `awaiting_confirmation` | Close produced the verified delivery | close with the token; status shows the token |
| `close_unfinished` | Close requested; stop, seal or delivery incomplete | close (with its specific continuation) |
| `closed_before_launch` | Closed with no `run_started`; states whether a commission had been accepted | none |
| `closed` | Closed after launch; names the delivery, or the surrendered losses | none |

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
value that depends on the unreadable part is `unknown`.

`stewart status --archive ROOT` lists every reference in the archive in
creation order with its folder, `inquiry` label, `varies` note and headline. It
selects nothing.

### 5.7 `run`

`stewart run REF` places the auditor into the arrangement in the foreground and
exits when the placement ends (section 6). It needs `ANTHROPIC_API_KEY`.
`STEWART_PROVIDER_URL` optionally overrides the provider base URL. It must be
`https://`, or `http://` to a loopback address. The override is recorded and
shown by status. Missing key or a bad URL is refused before any request
(`provider_key_missing`, `provider_url_invalid`,
`provider_proxy_invalid`).

Refusals: `not_accepted`, `run_held`, `authoring_ended` (naming the ending:
sealed, ordinary ending, limit, damage or close), `reference_closed`,
`writer_mismatch`, `log_damaged`. Once a placement has started, `run` replies
`completed` whenever it recorded the placement's ending, whatever the ending:
`interrupted` (exit 5), `damaged`, or `sealed` with a failed delivery, which the
data reports. It replies `failed` when it could not record an ending. The reply
data names the run number, the ending, the allowances, and the seal and delivery
if any; the envelope's `next` gives the next calls.

### 5.8 `close`

`close` is available in every state. One algorithm serves every call; repeating
it resumes where the recorded state stands. An unfinished close is outcome
`completed` with `data.closure: "unfinished"` and `data.unfinished_reason`
naming what remains; it carries no top-level `reason`. Here a verified delivery
is one that ended `verified` or `verified_with_losses` (8.3).

Close reconciles under a free lock: it records the end of work whose process is
gone. An `intake_planned` without an outcome gets `intake_ended` with
`outcome: "process_gone"`; a `run_started` without a `run_ended` gets
`run_ended` `interrupted` with cause `process_gone`; a `delivery_planned`
without an outcome gets `delivery_ended` `failed` with cause `process_gone`.

1. If the log is damaged (4.4), reply unfinished with
   `unfinished_reason: "log_damaged"`, naming the bad records. Close publishes
   nothing to a damaged log, so it never publishes `closed`.
2. If `closed` exists, return its recorded outcome with `data.already_closed: true`.
3. If no `close_requested` exists, publish it. From this log position, authoring
   ends, no run may start and no intake may be accepted. Its body records the
   flags given.
4. **Before launch** (no `run_started` before `close_requested`): wait up to 10
   seconds for an intake holding the lock to end. If it still holds the lock,
   reply unfinished with `unfinished_reason: "intake_still_running"`. Otherwise
   reconcile, then publish `closed` with `before_launch: true` and whether a
   commission had been accepted. No answer, seal or confirmation is created.
5. **After launch**, in order:
   - **Stop.** If the lock is held and a `run_started` has no `run_ended`, wait
     up to 30 seconds for the run to observe `close_requested` and exit (6.8). If
     it is still held, reply unfinished, `run_still_held`, with the holder
     observations. If the lock is held and every `run_started` has its
     `run_ended`, another close holds it: reply unfinished, `close_in_progress`.
   - **Lock.** Take the active lock (4.6) and hold it for the seal and delivery
     work. If another close holds it, reply unfinished, `close_in_progress`.
     Otherwise reconcile.
   - **Seal.** An existing auditor seal is kept. Otherwise close prepares the
     selection current at `close_requested` and seals it with
     `actor: "manager"` (8.1). An entry that cannot be read or verified
     becomes a named, unproduced member, and so does the rendering that
     depends on it.
   - **Deliver.** If a verified delivery of the seal exists, close presents it.
     It needs no confirmation if it was verified before the first
     `close_requested`: ordinary close is the manager's placement decision, and
     close publishes `closed`. Otherwise close presents its confirmation token.
     Only when none exists does close deliver (8.3), to `--destination DIR` if
     given, else to the commissioned destination. A verified delivery is
     presented with its package and confirmation token, and closure stays
     unfinished. A `partial` or `failed` delivery has no token: closure stays
     unfinished with `delivery_incomplete`, continued by `close` or
     `close --destination DIR`.
   - **Confirm.** `close REF --confirm TOKEN` with the token for the newest
     verified delivery publishes `closed`. A token for another seal or delivery is
     refused (`confirmation_mismatch`). Repeating close without the token only
     presents the same result again.
   - **Surrender.** If that delivery is `verified_with_losses`, confirmation
     also needs `--surrender LOSS` for each unproduced member; without them it is
     refused (`surrender_required`), naming the loss IDs. Each loss ID names one
     unproduced member (8.4). `closed` then records the surrendered members.
     Unknown membership offers no loss IDs, and close stays unfinished.

`--destination DIR` is accepted only after a `partial` or `failed` attempt of the
seal and while no verified delivery of it exists. With a verified delivery it is
refused (`delivery_already_verified`): close completes an owed delivery and is
not a copy service. Before any partial or failed attempt it is refused
(`destination_not_replaceable`): a replacement serves only a delivery that could
not complete at the commissioned destination. Every delivery attempt uses a
fresh package and keeps earlier attempts.

```json
{"schema": "stewart.reply/1", "operation": "close", "outcome": "completed",
 "effects": {"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
 "next": [{"argv": ["/usr/local/bin/stewart", "close", "stw1:…", "--confirm", "cf1.h3d7ws"],
           "why": "Confirm that this delivered copy is where you want the return."}],
 "data": {"closure": "unfinished", "awaiting": "confirmation",
          "headline": {"accepted": "yes", "launched": "yes", "sealed": {"by": "manager"},
                       "delivered": {"verified": true, "confirmed": false,
                                     "location": "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001"},
                       "closed": "unfinished"},
          "seal": "seal.r2m6vd", "manifest_sha256": "…", "run": "ended",
          "confirmation": "cf1.h3d7ws"}}
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

The first adapter speaks the Anthropic Messages API: non-streaming
`POST <base>/v1/messages` with `x-api-key`, the pinned `anthropic-version` and
`content-type: application/json`. The base is `https://api.anthropic.com` unless
overridden (5.7). Field names below follow that API. They are verified against
the provider's current published specification when the adapter is built, and
any difference is corrected here before implementation.

If `HTTPS_PROXY` (or `https_proxy`) is set, the adapter reaches an `https://`
provider through that proxy with HTTP `CONNECT`. TLS runs end to end inside the
tunnel, so the proxy never sees the key. The proxy value must be
`http://host:port`, without credentials; anything else is refused before any
request (`provider_proxy_invalid`). `NO_PROXY` is not consulted, and loopback
provider URLs never use the proxy. The proxy in use is recorded in `run_started`
and shown by status.

### 6.2 Requests and responses

`arrangement.json` pins, as exact bytes where noted:

| Member | Content |
| --- | --- |
| `model` | From front matter |
| `anthropic_version` | Pinned by the release |
| `max_tokens_per_request` | Pinned by the release |
| `system` | Exact JSON array: orientation block, family instruction block (QUESTION-FORMS) |
| `tools` | Exact JSON array of tool definitions for the family (section 7) |
| `request_extra` | Exact JSON object of further top-level request parameters, limited to the release's allowlist |
| `texts` | Reminder, near-limit template and continuation notice |
| `limits`, `near_limit_percent` | From front matter; 20 |
| `retry`, `request_timeout_seconds` | 6.6 policy; 600 |
| `reader`, `renderer`, `family` | `utf8-text/1`, `stewart.render/1`, family ID and version |
| `bindings` | SHA-256 of the question body and of the material index |

Each request body is assembled by splicing pinned bytes, never by re-serializing
a parsed structure: `model`, `max_tokens` (6.4), `system`, `tools`, the
`request_extra` members and `messages`. No provider feature may be enabled that
puts model-visible content outside the arrangement, such as server tools,
fallback to another model or budget countdowns.

Messages are append-only within a placement:

- The first user message is one text block holding the question body exactly.
  In a continuing placement a second text block holds the continuation notice.
- Each assistant message is the `content` array copied byte for byte from the
  captured response.
- Each following user message holds one `tool_result` block per `tool_use` block,
  in order. A pending near-limit notice follows them as a text block.
- The reminder (6.4) is a user message holding the reminder text block and, if
  the near-limit notice is pending, that notice's text block after it.

Each response is captured raw before decoding. The envelope is decoded
tolerantly: unknown fields and block types are kept in the capture and echoed in
history, never interpreted. Stewart does not summarize or trim history.
Provider-side context management applies only if the arrangement enables it.
Otherwise context exhaustion interrupts the placement (6.5), and continuation
starts a fresh conversation.

### 6.3 The loop and invocation identity

```
before each request: if close_requested → end stopped_by_close
                     if a limit is exhausted → end limit_reached
send (6.6); account usage (6.4)
execute every tool_use block in order
if a seal was recorded during this response → deliver (8.3), then end sealed
stop_reason tool_use   → send results, continue
            end_turn, stop_sequence → if a limit is exhausted, end limit_reached;
                                      else reminder if unused; else end ended_unsubmitted
            max_tokens → if any tool_use was executed, send results and continue; else end interrupted
            refusal    → end interrupted
            other      → end interrupted (protocol_anomaly)
```

Once a seal is recorded, the run completes its delivery, or records the
delivery's failure, before publishing `run_ended` `sealed`, even if
`close_requested` appears meanwhile (6.8).

A tool invocation's identity is the placement number plus the `tool_use` ID. Before
executing, the raw block is captured (`call-<k>.json`). After executing, the
result is captured (`result-<k>.json`). A second block in the same placement with
an executed ID and the same input digest receives the recorded result without
another execution. With a different input it is refused
(`invocation_id_reused`). Retries resend recorded results, so a retried request
is byte-identical. A new call with matching arguments is a new invocation.

### 6.4 Limits, reminder and notice

After each response: turns +1; input tokens + `input_tokens` +
`cache_creation_input_tokens` + `cache_read_input_tokens`; output tokens +
`output_tokens`. An attempt that was sent and got no response is charged one
estimated turn, `max_tokens` estimated output tokens and ceil(request body bytes
/ 3) estimated input tokens. An HTTP error response is charged nothing. Reported
and estimated usage are recorded separately for turns, input and output, in
`run_ended`, in status allowances (5.6) and in re-entry (7.5); a limit counts
their sum. Totals are cumulative across placements.

Each request's `max_tokens` is the lesser of `max_tokens_per_request` and the
remaining output allowance. A limit is exhausted, and no request is sent, when
any of the following holds:

- no turn remains;
- the input allowance is used up;
- fewer than 1,024 output tokens remain.

Output tokens therefore never exceed their limit. Input tokens can exceed theirs
by at most one request, since a request's input size is known only from its
response. Pending `tool_use` blocks of the last response are executed before the
placement ends `limit_reached`.

The reminder is the CONTRACTS text, sent at most once per audit. After an
`end_turn` without a seal, if any limit is exhausted the placement ends
`limit_reached` and no reminder is planned. Otherwise, if the reminder is
unused, a `notice` log record with `type: "reminder"` is published, then the
reminder message is sent: the reminder block, followed by the near-limit notice
block if that notice is pending. If the reminder is already used, the placement
ends `ended_unsubmitted`.

The near-limit notice is sent at most once per audit. With remaining =
max(0, limit − used), it is triggered when, after accounting, remaining × 100 ≤
`near_limit_percent` × limit for any limit. Its template values are the
remaining amounts. Its `notice` record is published before the message that
carries it. If the placement ends first, the record stands, and `run_ended`
reports the notice as not delivered. Both allowances are audit-wide and survive
continuation.

### 6.5 Endings

| Event | Recorded ending | `run` may continue |
| --- | --- | --- |
| Auditor confirmed submit | `sealed` | no |
| `end_turn` with the reminder already used | `ended_unsubmitted` | no |
| Limit reached | `limit_reached` | no |
| `close_requested` observed | `stopped_by_close` | no |
| Unrepairable damage to recorded answer bytes | `damaged` | no |
| SIGTERM, SIGINT, SIGHUP | `interrupted`, cause `signal` | yes |
| Connection failure, timeout, or HTTP 408, 429, 500, 502, 503, 504 or 529, after retries or with a `retry-after` over 60 seconds (6.6) | `interrupted`, cause `provider_unavailable` | yes |
| Any other HTTP error, including context too long and bad key | `interrupted`, cause `provider_rejected` with status and error type | yes |
| `stop_reason` `refusal` | `interrupted`, cause `provider_refusal` | yes |
| `max_tokens` with no `tool_use` | `interrupted`, cause `max_tokens` | yes |
| `pause_turn`, unknown stop reason, undecodable response | `interrupted`, cause `protocol_anomaly` | yes |
| Archive write failure | `interrupted`, cause `archive_write_failed` | yes |
| The log is found damaged (4.4) | none: the run publishes nothing, sends no further request, releases the lock and exits 4; status reports the damage | no |
| Process killed or crashed | no `run_ended`; the next `run` or `close` records `interrupted`, cause `process_gone` | yes |

`run_ended` records the ending, cause, the placement's turns, input and output
usage, each split into reported and estimated (6.4), and whether a planned
notice was delivered. The reminder is used only for an ordinary `end_turn`.

### 6.6 Provider retry

Each request is attempted at most 4 times. A retry follows a connection failure
before a response, a timeout, or HTTP 408, 429, 500, 502, 503, 504 or 529. The
delays are 2, 8 and 30 seconds, or the `retry-after` value when one is given. A
`retry-after` over 60 seconds is not waited for: the request is not retried, and
the placement ends `interrupted` with cause `provider_unavailable`. Each attempt
is captured. A `close_requested` seen while waiting ends the placement.

### 6.7 Continuation

`run` on an interrupted audit first records `run_ended` (`process_gone`) for a
dead placement, then publishes `run_started` for placement `n+1`. The new
conversation uses the same pinned arrangement bytes. The question is in the
first message and the continuation notice follows it (QUESTION-FORMS). The
ledger, limits and notice allowances carry over unchanged. No prior
conversation is replayed.

### 6.8 Stopping

A watcher thread checks every 250 milliseconds whether the log's next record is
a `close_requested`. Its stop path applies only while no seal exists; once a
seal is recorded, the run finishes its delivery first (6.3). When the stop path
applies, the adapter aborts any in-flight provider request by shutting down its
socket, stops executing tool calls, publishes `run_ended` (`stopped_by_close`),
releases the lock and exits 0. An in-progress
mutation fails to claim its log slot and is reported to the model as
`authoring_ended`. On SIGTERM, SIGINT or SIGHUP the adapter takes the same path,
records `interrupted` with cause `signal` and exits 5. The `run_needs` of the
commission and receipt replies says that the run is in the foreground until the
placement ends, and that callers with command timeouts should start it in the
background.

## 7. The auditor's tools

### 7.1 Conventions

- Every `tool_result` begins with a text block holding the `stewart.reply/1`
  envelope, whose `operation` is the tool name. Text reads add a second text
  block holding the exact text read. Like every text block, it is a JSON string
  on the wire, as CONTRACTS requires. When the page has no non-whitespace
  character, including an empty page, there is no second block, because the
  provider refuses blank text blocks; the exact text is then in the envelope's
  `data.text`. Base64 pages are always in `data.base64`. `is_error` is true when
  the outcome is not `completed`.
- Inputs are decoded strictly (1.2) and are at most 4 MiB per call
  (`input_too_large`).
- Replies never include host or archive paths, front matter, provider details
  or manager identifiers: the reference string, archive path, store ID, inquiry
  label, varies note and family. The audit ID is visible to the auditor.
- Every tool definition is `{"name", "description", "input_schema"}`. The input
  schema is `{"type": "object", "properties": {…}, "required": […],
  "additionalProperties": false}`, with the properties and descriptions given in
  QUESTION-FORMS.
- After a seal or close, mutations refuse `authoring_ended`, naming what ended
  authoring and, if a seal exists, who sealed. Reads continue to work until the
  placement ends.
- When an archive write fails during a call, the call fails with
  `record_failed`. Its `effects` state what is known, with `unknown` where the
  write's outcome cannot be established. Any remaining `tool_use` blocks of
  that response receive the same failure without executing, no further request
  is sent, and the placement ends `interrupted` with cause
  `archive_write_failed` (6.5).

| Tool | Input | Completed `data` |
| --- | --- | --- |
| `list` | `cursor?` | `materials[{source,size,lines}]`, `directories[]`, `returned`, `total`, `complete`; while incomplete, `next` is a `list` call with an `ls.` cursor. A page holds at most 128 materials. |
| `read` | `source`, `start?` | 7.2 |
| `search` | `text`, `sources?`, `cursor?` | 7.2 |
| `record_<kind>` | `text`, `citations?`, `label?` | `entry`, `id`, `version`, `revision`, `citations` |
| `record_artifact` | `label`, exactly one of `text` / `base64` | `entry`, `id`, `version`, `revision` |
| `replace` | `entry` and every field of its kind | `entry`, `id`, `version`, `revision`, `citations` |
| `delete` | `entry` | `removed{id,version}`, `revision` |
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
  `{source, start, end}` for the page, `null` for entry and view reads; and
  `text` or `base64` when the page is carried in the envelope (7.1). While the
  read is incomplete, the envelope's `next` is a ready `read` call for the rest.
- Entry reads add `entry`, `id`, `version`, the record kind, `label` and
  `citations`. A replaced entry handle is refused (`stale_entry`) with the
  current handle. A deleted one is refused (`entry_deleted`). An artifact
  recorded from `base64` (`encoding: "binary"`) is returned as base64 pages of
  49,152 bytes in `data.base64`, marked `encoding: "base64"`.
- A prepared view remains readable after a later edit. It is its fixed
  selection, never a newer rendering.

`search(text, sources = all, cursor)` is literal, case-sensitive search.

- `text` is 1–1,024 bytes.
- `sources` names up to 128 sources from `question` and `materials/…`. The
  default is the question, then every material in index order. The reply
  states the scope searched.
- Every occurrence is reported, including overlapping ones, in source order and
  then by position.
- A hit is `{source, start, end, line, context, cite}`. `context` is the hit's
  line, clipped to 240 bytes around the hit on character boundaries, with
  `truncated` flags. `cite` is a ready citation `{source, start, end}`.
- A page holds at most 128 hits and 32 KiB of context text. `complete: true`
  means the whole scope was scanned. Otherwise the envelope's `next` is a ready
  `search` call whose `sc.` cursor is bound to the text, the scope and the
  position.
- An incomplete search never reports absence.

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
  entry's label adds the notice `label_duplicate`; it is not refused.
  Repeating a call creates another entry.
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

### 7.5 Re-entry: `what_am_i_working_with(page?)`

The first page's `data`:

```json
{"audit": "aqm3x7kd2hz5vw4ny", "condition": "open", "revision": 7,
 "run": {"number": 2, "continuing": true},
 "allowances": {"turns": {"used": 41, "reported": 40, "estimated": 1, "limit": 200},
                "input_tokens": {"used": 1830211, "reported": 1801300, "estimated": 28911, "limit": 20000000},
                "output_tokens": {"used": 59214, "reported": 51022, "estimated": 8192, "limit": 400000}},
 "notices_used": {"reminder": false, "near_limit": false},
 "question": {"source": "question", "size": 46, "lines": 1},
 "materials": {"count": 3, "bytes": 1428},
 "entries": [{"id": "e1", "entry": "e1.v2.k7q4m2", "kind": "record_account", "label": "",
              "size": 132, "preview": "The supplied excerpts support one restart…", "preview_complete": false}],
 "receipts": [{"run": 1, "tool": "replace", "target": "e1.v1.x2p7aa", "entry": "e1.v2.k7q4m2", "revision": 7}],
 "latest_refusals": [{"tool": "record_observation", "reason": "citation_invalid", "revision": 6, "run": 1}],
 "page": {"bound_revision": 7, "returned": 5, "total": 5, "complete": true}}
```

The envelope's `next` offers `list` for the materials and, while `complete` is
false, a `what_am_i_working_with` call with the `pg.` cursor for the next page.

- `condition` is `open`, `sealed` (with `sealed_by`) or `closed`.
- Previews are the first 200 bytes on a character boundary and are marked as
  previews.
- `receipts` lists the 16 most recent completed mutations across placements.
  `latest_refusals` lists the most recent refusal for each tool.
- `allowances` split usage into reported and estimated as status does (5.6).
- A page holds up to 64 entries; later pages carry only `entries` and `page`.
  A page cursor is bound to its revision. After an intervening edit it is
  refused (`stale_view`), with a next call to start again.
- Re-entry is not a gate: no mutation requires it. It reports recorded facts,
  not what the auditor has read or concluded.

### 7.6 Prepare and submit

`prepare()` re-verifies the current selection's payload digests and writes
`prepared/<n>/answer.json` and `answer.md` (QUESTION-FORMS) as exclusive files.
It returns:

```json
{"prepared": "ap3.x6h2kq", "revision": 7, "entry_count": 5,
 "counts": {"record_account": 1, "record_observation": 3, "record_limit": 0, "record_artifact": 1},
 "notices": [{"reason": "section_unfilled", "tool": "record_limit",
              "message": "No record_limit entries are recorded."}],
 "rendering": {"source": "ap3.x6h2kq/rendering", "size": 2210},
 "selection": {"source": "ap3.x6h2kq/selection", "size": 3904}}
```

Missing sections and an empty answer never refuse. An empty selection gives the
notice `answer_empty` ("No answer entries are recorded.") and the rendering
`No answer entries recorded.` Damaged selected bytes refuse (`answer_damaged`).
The run then ends `damaged`, and the reply's `next` is empty: the auditor stops.

`submit(prepared, confirm = false)`:

| Case | Outcome and `data` |
| --- | --- |
| Dry run, current handle | completed: `dry_run: true`, `revision`, `entry_count`, `rendering` |
| Revision changed since prepare | refused `stale_preparation`: `revision_now`, next `prepare` |
| `confirm: true`, current, slot won | completed: `seal`, `sealer: "auditor"`, `revision`, `manifest_sha256` |
| Repeat of an accepted confirmed submit | completed: the same `seal`, `already_sealed: true` |
| Manager close won the order | refused `authoring_ended`: `{"ended_by": "close", "close_requested_at": …, "seal": <handle or null>, "sealer": <"auditor", "manager" or null>}` |
| Seal publication uncertain | failed `seal_uncertain`, `effects.seal: "unknown"`; next: the same submit, which returns the recorded seal or seals |

Neither reply claims delivery, a stopped process or close.

## 8. Seal, return and delivery

### 8.1 Seal

A seal binds one prepared selection. The auditor seals the selection of its
prepared handle. Close first runs the same preparation over the selection
current at `close_requested`. To seal, Stewart:

1. re-verifies each selected payload's digest;
2. writes `seal/manifest-<k>.json` as an exclusive file;
3. publishes the `seal` log record naming the manifest and its digest.

If the slot is taken by an edit, the auditor's submit is stale. If it is taken by
`close_requested`, authoring has ended. If it is taken by another `seal`, that
seal stands. The prepared bytes never change.

When close cannot read or verify a selected entry's payload, it still seals. The
manager seal binds the recorded identities and digests of the whole selection:
`answer.json` writes that entry in its unproduced form (QUESTION-FORMS), and the
manifest's `unproduced` lists the entry (role `entry`, named by its ID) and
`answer.md` (role `rendering`), each with its failure. The renderer is not run
when any entry is unproduced.

### 8.2 The return package

A package is a new directory `stewart-return-<audit-id>-<nnn>` inside the
destination, where `nnn` is the delivery attempt number, zero-padded to at least
three digits (attempt 1 is `001`). It contains only:

| Member | Content |
| --- | --- |
| `manifest.json` | The seal manifest, byte for byte |
| `answer.json` | The structured answer (`stewart.answer/1`, QUESTION-FORMS) |
| `answer.md` | The prepared rendering |
| `artifact-<id>.bin` | Each selected artifact's exact bytes (`artifact-e4.bin`) |

The manifest (`stewart.return/1`) holds:

- the audit and store identifiers;
- the family ID and version, and the renderer version;
- the writer digest;
- the seal: actor and time;
- the answer revision;
- the ordered members, each with name, role, size and SHA-256;
- the `unproduced` members, each with its name, role, failure and dependency.

The manifest does not contain the seal handle; the handle binds the manifest
(2.3).

It verifies the package without the archive. The question, receipt,
arrangement, access log, run summaries and conversations are never members.

### 8.3 Delivery

1. Publish `delivery_planned`, naming the attempt, the destination (path,
   device and inode), the package name and `replaces`: the latest earlier
   attempt of this seal, which ended `partial`, `failed` or `name_taken`, or
   `null` for the first attempt.
2. Check location overlap (`location_overlap`). Create the package with
   `mkdirat`. If the name is taken, publish `delivery_ended` `name_taken` for
   this attempt and plan a new attempt from step 1. An existing path is never
   adopted, emptied or overwritten.
3. Write `manifest.json` first, then each member, as exclusive files, each
   synced. Then sync the package and the destination.
4. Reopen each member by name through descriptors and verify its size and
   digest.
5. Publish `delivery_ended` with one outcome:

| Outcome | Meaning | Confirmation token | Loss IDs |
| --- | --- | --- | --- |
| `verified` | Every member verified; nothing unproduced | yes | none |
| `verified_with_losses` | Every produced member verified; the unproduced members listed | yes | one per unproduced member |
| `partial` | A produced member failed, or did not verify at the destination | no | none |
| `failed` | The attempt failed, with its cause | no | none |
| `name_taken` | The package name existed (step 2) | no | none |

A `partial` or `failed` attempt continues through `close` or
`close --destination DIR` (5.8).

A run delivers after an auditor seal, before exiting. Close delivers any other
owed copy. Continuation after a lost reply reads these records rather than
copying again.

### 8.4 Confirmation and loss

The confirmation token for delivery attempt `n` is `cf<n>.<check>`, issued for a
`verified` or `verified_with_losses` attempt. Its check binds the manifest digest
and the attempt's `delivery_ended` record (2.3). Status shows the token while it
is outstanding.

A loss ID is issued for each unproduced member of a `verified_with_losses`
attempt, and only then. Its record, the failure record, is that attempt's
`delivery_ended`: it names the member, its failure, the seal and the verified
members delivered. Status lists loss IDs only for known members; unknown
membership has none.

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
`[log 12: entry add e5]` is linked and before `result-<k>.json`. `status` →
`interrupted`. `run REF` → `[run_ended process_gone]`, `[run_started 2]`, first
message with question and continuation notice. The reacting fake calls
`what_am_i_working_with`, finds `e5` in `entries` and `receipts`, and does not add
it again. The sealed return contains each goal entry once.

**T8. Ordinary ending.** The fake ends a turn without submitting → reminder
`[notice reminder]`. It ends again → `[run_ended ended_unsubmitted]`, exit 0.
`run REF` → refused `authoring_ended` ("ordinary ending without submission"),
next `close`. `close REF` → manager seal, delivery, `awaiting: "confirmation"`,
`cf1…`. `close REF --confirm cf1…` → completed, `closure: complete`.

**T9. Delivery to an unavailable destination.** The destination is removed after
commission. Auditor seal → run delivery attempt 1 `[delivery_ended failed]`,
then `[run_ended sealed]`. `close REF` → delivery attempt 2 at the commissioned
destination, `[delivery_planned replaces: 1]` `[delivery_ended failed]`;
completed, closure `unfinished`, `unfinished_reason: "delivery_incomplete"`, no
token, next `close` and `close --destination DIR`. `close REF --destination
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
| `setting_missing`, `setting_invalid`, `destination_invalid`, `question_empty` | Front matter and body (3.2) |
| `affirmation_missing` | `commission` without `--i-am-finished` |
| `handle_invalid` | Handle of wrong kind, store, audit or check |
| `selection_changed` | Source differs from the prepared selection |
| `intake_in_progress` | Commission could not take the active lock |
| `acceptance_uncertain` | Status condition: acceptance cannot be established, because the log is damaged before any readable `accepted` (5.6); commission then refuses `log_damaged` |
| `acceptance_record_uncertain` | Publishing acceptance failed partway |
| `capture_failed`, `capture_unverified` | Writing or verifying a capture failed |
| `receipt_record_failed` | Writing the acceptance receipt failed |
| `reference_already_accepted` | This reference already has an accepted commission (prepare; commission with a different handle) |
| `reference_closed` | Close was requested |
| `not_accepted` | Receipt or run before acceptance |
| `run_held` | Another run holds the lock |
| `authoring_ended` | Sealed, ordinary ending, limit, damage or close (named) |
| `provider_key_missing`, `provider_url_invalid`, `provider_proxy_invalid` | Run environment |
| `intake_still_running`, `run_still_held`, `close_in_progress`, `delivery_incomplete` | Close unfinished, as `data.unfinished_reason` (continue with `close`) |
| `log_damaged` as `data.unfinished_reason` | Close unfinished on a damaged log; close publishes nothing |
| `confirmation_mismatch` | Token for another seal or delivery |
| `surrender_required` | Unproduced members; name each loss |
| `delivery_already_verified` | `--destination` after verified delivery |
| `destination_not_replaceable` | `--destination` before any partial or failed attempt of the seal |
| `item_unknown`, `item_damaged`, `item_missing`, `item_unreadable`, `item_unsupported` | Receipt readback |

Auditor: `input_invalid` (with JSON pointer), `input_too_large`,
`source_unknown` (with hints), `range_invalid`, `citation_invalid`,
`quote_not_found`, `quote_ambiguous`, `stale_entry`, `entry_deleted`,
`fields_invalid`, `stale_view`, `stale_preparation`, `answer_damaged`,
`retained_payload_cap`, `retained_payload_reserve_exhausted`,
`entry_limit`, `selection_limit`, `authoring_ended`, `invocation_id_reused`,
`handle_invalid`, `seal_uncertain`, `record_failed` (an archive write failed;
effects state what is known). Notices: `section_unfilled`, `answer_empty`,
`label_duplicate`, `folder_already_referenced`.

`intake_ended` outcomes: `selection_changed`, `source_unreadable`,
`capture_failed`, `capture_unverified`, `receipt_record_failed`, `closed`,
`process_gone`. `delivery_ended` outcomes: `verified`, `verified_with_losses`,
`partial`, `failed`, `name_taken`.

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
| Provider attempts; delays; retry-after ceiling; request timeout | 4; 2, 8, 30 s; 60 s; 600 s |
| Minimum output allowance for a request | 1,024 tokens |
| Near-limit threshold | 20% remaining |
| Front matter limits | turns 1–10,000; input 1–2×10⁹; output 1–2×10⁸ |
| Scaffold defaults | 200 turns; 20,000,000 input; 400,000 output |
