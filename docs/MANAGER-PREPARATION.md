# Manager preparation protocol

This is the specified preparation server for the [manager interface](INTERFACE.md#511-manager-preparation-mcp).
It awaits implementation. Its product is an ordinary submission directory.
The CLI's `prepare` scans that directory and `commission` accepts an exact
prepared selection, regardless of how the directory was made.

## Transport

Use the MCP `2025-11-25` [stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
and [initialization handshake](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle).
The server reads LF-delimited UTF-8 JSON-RPC 2.0 from stdin and writes one
compact line per reply on stdout. No listener, outbound requests, prompts,
resources or sampling. The initialize result has
`protocolVersion:"2025-11-25"`, `capabilities:{"tools":{}}` and
`serverInfo:{"name":"stewart-manager","version":"1"}`. It offers only that
version. The client sends `notifications/initialized` before listing or
calling tools. `ping` returns `{}`. EOF ends the process. Requests execute
serially. Notifications never dispatch a tool or receive a reply. Transport
initialization is the only prerequisite session state for a tool call.

`tools/list` returns one page, in [interface order](INTERFACE.md#511-manager-preparation-mcp).
Each tool has `name`, `description` and `inputSchema` describing the closed
argument object below. `tools/call` takes `name` and `arguments` under the
[MCP tools protocol](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).
Honor standard protocol metadata as metadata only. Application arguments
follow INTERFACE 1.2. Every tool accepts optional `detail`, either `brief`
(default) or `full`. It selects explanation for that call only.

Limit each input line to 4 MiB excluding LF, checked while reading. Discard
the remainder of an overlong line through LF without executing it. Malformed
JSON returns `-32700` with null ID, an invalid request `-32600`, an unknown
method `-32601`, and invalid method parameters, including an unknown tool,
`-32602`. An overlong line returns `-32600` with null ID. Before initialization,
refuse tool requests with `-32600`. A valid call with invalid tool arguments
returns a tool refusal with reason `input_invalid` and its JSON pointer.
Clients use a fresh string or integer ID for each request in a session. A
reply echoes the ID. Reusing a call's content or reconnecting supplies no
access to an earlier proposal or result.

Each tool result has `isError`, `structuredContent` and one `content` text
block whose text is the same object encoded as compact JSON. That object has
the following required keys:

| Key | Value |
| --- | --- |
| `schema`, `registry`, `question_schema` | `stewart.manager-preparation/1`, `stewart.family-registry/1`, `question/2`. |
| `tool`, `outcome` | Tool name and `completed`, `refused` or `failed`. `isError` is true for the last two. |
| `problem` | null, or `{reason,pointer,message,remedy}`; pointer is a JSON pointer in arguments or null. |
| `data` | Tool-specific result below, or null when unavailable. |
| `writes` | `{state,created,incomplete}`. State is `none`, `complete`, `partial` or `unknown`; paths relative to the workspace identify every known created entry, including directories, and incomplete files. Both arrays are empty for a read-only call. |
| `explanation` | Empty array for brief; for full, an array of explanatory strings. Facts, defects, permissions, uncertainty, planned files and writes are identical at either detail. |

## Tools

**Discover** takes only `detail`. Its data is `{families:[{family,available,purpose}]}`
in [registry order](QUESTION-FORMS.md#manager-family-registry). Each family ID
here and in `explain` is versioned. Only the three available families appear.

**Explain** requires `family`. Return `{descriptor,example}`. The descriptor
is the registry object. The example is a `material-roles` array using the
corresponding worked packet. Full detail explains the inadequate-evidence
variant. An unknown or unavailable ID refuses `family_unknown`, naming the
available values. Both tools work entirely from compiled data.

**Assess** requires `question_file` (the complete prospective file as a
string), `guidance` (string or null), `directories` (array of names) and
`files` (array of `{name,size}`, size an unsigned integer). Decoded strings
supply their UTF-8 bytes. Names use the CLI material index conventions:
`materials` itself occurs in directories, each ancestor occurs once, files
start with `materials/`, no duplicate or file/directory collisions. Order in
these arrays has no meaning. Check directory/file counts, name, question,
guidance, per-file and total bounds as at intake, including the root in the
directory count. Missing `materials` or an implied parent gives
`folder_incomplete`; malformed names, duplicate names and file/directory
collisions give `name_invalid`. Exceeded limits give `bound_exceeded`
and identify the bound in the message. A selected but missing guidance file
gives `folder_incomplete`; an unselected supplied one gives `unexpected_root_entry`.
For inventory diagnostics `source` names the affected entry, `pointer` indexes
the supplied argument (for example `/files/1/name`), and line and key are null.
The caller supplies an inventory, so assessment makes no filesystem reads.

Data is `{valid,defects,unchecked}`. Valid means no error in the supplied
snapshot. Use exactly the CLI [commissioning diagnostics](INTERFACE.md#commissioning-diagnostics).
A mechanically invalid candidate is a *completed assessment* with
`valid:false`. A tool argument of the wrong JSON type is a tool refusal.
For example, assessing a well-formed question declaring an unselected B gives
`role_source_unknown` even though the assessment operation succeeded.
`unchecked` lists, in order, `material_bytes`, `filesystem`, `source_stability`,
`runtime_profile` (only for a profile selection), `acceptance`. This identifies
asserted file sizes and membership, host/destination/archive conditions and
checks which only later CLI operations can establish. A destination or profile
string in question text is never opened by a tool.

**Assemble** requires `fields`, `body`, `guidance`, `directories`, `files`
and `destination`. The optional boolean `create` defaults to false.

- `fields` is an object with the selected build's question keys other than
  `stewart`. Values are strings as written in the front matter except
  `material-roles`, which is its JSON array. Require the same fields and
  validate the same values as CLI intake. Reject CR/LF in field strings;
  a string cannot insert a line or end front matter. `body` is the manager's
  exact question string. `guidance` and `directories` have their assess forms.
- Each file is `{name,from}`: `name` is its public material name and `from`
  names a regular source relative to the workspace's `sources/` directory.
  Sources are supplied by the caller ahead of time. Copy exact text bytes.
  The output `destination` is a single new directory name under the workspace,
  distinct from `sources`. It names the candidate folder. The front matter
  `destination` names the future answer destination.
- Generate UTF-8 front matter with LF, starting with `---\nstewart: question/2\n`.
  Write present fields in bytewise key order, one `key: value\n` each.
  Encode role arrays compactly in declaration order and object-key order from
  INTERFACE 3.2. Append `---\n` and the exact body bytes. Do not insert
  examples, instructions, a missing criterion, question wording or a body
  newline. Keep selected guidance bytes separate.
- On success data is `{question_file,directories,files,assessment}`.
  `directories` lists all proposed directories relative to the candidate,
  including `materials`; `files` lists `{name,size,sha256}` for every proposed
  file including the question and selected guidance. Both arrays sort by
  UTF-8 name bytes. `assessment` is assess data for the generated snapshot,
  omitting `material_bytes` from `unchecked` once all supplied bytes have
  actually been checked. No output includes supplied material bodies. Dry-run
  returns the exact proposed question and inventory with `writes.state:"none"`.
  With candidate errors return `candidate_invalid`, the assessment in
  `data.assessment` and no writes. Preflight need not acquire further sources
  once a refusal is established.

For example, to propose an empty open inquiry:

```json
{"name":"assemble","arguments":{"fields":{"family":"open-inquiry","model":"example-model","destination":"/home/ana/returns","limit-turns":"4","limit-input-tokens":"32000","limit-output-tokens":"8000"},"body":"What can these materials establish?","guidance":null,"directories":["materials"],"files":[],"destination":"first-inquiry"}}
```

It proposes `question.md` and an empty `materials/`. The missing subject
mapping is a suggestion. A separate call with the same arguments and
`create:true` requests creation. Both calls do their own validation.

## Filesystem authority and interruption

The launcher may designate one existing absolute, candidate-only workspace.
Relative roots and tool-supplied workspace overrides are invalid. Without a
workspace, discovery, explanation, assessment and a dry-run without source
files work; a call needing filesystem access refuses `workspace_required`.
The launcher chooses a workspace separate from its archives and delivery
locations. The server opens only named input files under `sources/` and
creates at most one explicitly named fresh child and its proposed entries per
call. It never resolves a Stewart reference, opens credentials or profiles,
enumerates audits, invokes the CLI or starts a provider.

Apply the CLI UTF-8 component/path limits to relative names. Reject absolute
paths, empty components, `.`, `..` and audit-reference operands. Acquire
directories through descriptors, verify exact name spelling, exclude symlinks,
special entries, mount crossings below the workspace, and source files with
more than one hard link. Check opened identities and sizes; stop on changes
or ambiguity. Check the workspace and input ancestry for a Stewart store marker
or delivery package before admitting it (metadata only: `STORE.json` or the
reserved `stewart-return-` directory prefix). Reject reserved candidate
destination names and collisions under the host's actual name rules. In
particular, a case alias cannot turn exclusive creation into editing an
existing candidate. These checks fence the supplied workspace; they cannot
identify the origin of detached, renamed copies or certify arbitrary host
directories as safe. The ordinary CLI still admits distinct hard-link names
in a manager's literal submission.

Read only the listed sources, checking the UTF-8 text and all intake limits
while acquiring them. Compute the proposed bytes before any creation. Reject
known overlap between the candidate and the named answer destination.
Neither dry-run nor assessment probes the answer destination or makes an
archive, temp file, lock, reference or directory. Dry-run can identify an
existing candidate by name when a workspace is present. Report
`destination_exists` on a known collision. Successful preflight makes no
promise that a later exclusive create will succeed.

On explicit creation claim the new child directory exclusively, create
directories through retained descriptors, and publish each file exclusively
with its proposed, verified bytes. Use 0700 directories and 0600 files.
Independent calls racing for the same destination have at most one winner.
Refuse an existing destination, including an incomplete earlier candidate.
A path-policy violation refuses `candidate_path_invalid`; source access or
change fails `candidate_source_failed`; a write or verification failure
fails `candidate_write_failed`. Name known partials, stop further writes and
leave them for inspection. A lost reply leaves the caller uncertain.
Inspect the named directory using ordinary file tools before repeating;
never adopt it as proof of completion, resume into it or remove it automatically.
