# Manager preparation protocol

Run `stewart manager-mcp` as an MCP stdio server to discover question
families, explain their roles, assess a prospective submission and assemble a
candidate submission folder. Discovery, explanation and assessment take all
their inputs in the call; an assessment can be repeated after any edit.
Assembly proposes a candidate's exact files and, on request, creates them in
the workspace the launcher designates with `--workspace DIR`. CLI `prepare`
checks the actual submission directory, and `commission` accepts an exact
prepared selection. Nothing here prepares, accepts or runs an audit.

The server is a separate entry point of the same binary. It shares no session,
audit handle or tool surface with the auditor's tools, and it cannot waive a CLI
rule: an exception a future contract permits must be explicit and captured.
Choosing a family grants no execution, access or budget.

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
| `problem` | null, or `{reason,pointer,message,remedy}` with a JSON pointer in arguments or null. |
| `data` | Tool-specific result below, or null when unavailable. |
| `writes` | `{state,created,incomplete}`. State is `none`, `complete`, `partial` or `unknown`. The two arrays identify known created entries (including directories) and incomplete files by workspace-relative path. Both arrays are empty for a read-only call. |
| `explanation` | An array of explanatory strings, empty for brief. Facts, defects, permissions, uncertainty, planned files and writes are identical at either detail. |

## Tools

**Discover** takes only `detail`. Its data is `{families:[{family,available,purpose}]}`
in [registry order](QUESTION-FORMS.md#manager-family-registry). Each family ID
here and in `explain` is versioned. Only the three available families appear.

**Explain** requires the versioned `family` ID from discovery, for example
`comparison/1`. In `question.md` write `family: comparison`.
Return `{descriptor,example}`. The descriptor
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
`folder_incomplete`. Malformed names, duplicate names and file/directory
collisions give `name_invalid`. Exceeded limits give `bound_exceeded`
and identify the bound in the message. A selected but missing guidance file
gives `folder_incomplete`. An unselected supplied one gives `unexpected_root_entry`.
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

- `fields` is a closed object of the selected build's question keys other
  than `stewart`; another key refuses `input_invalid` at `/fields/<key>`.
  Values are strings as written in the front matter except `material-roles`,
  which is its JSON array. A missing required field is not an argument error:
  the assessment reports it as CLI intake does, and validates the same values.
  A field string containing CR or LF refuses `input_invalid` at that field's
  pointer, for example `/fields/model`, so that no value can insert a line or
  end the front matter. `body` is the manager's exact question string.
  `guidance` and `directories` have their assess forms.
- Each file is `{name,from}`: `name` is its public material name and `from`
  names a regular source relative to the workspace's `sources/` directory.
  Sources are supplied by the caller ahead of time. Copy exact text bytes.
  The output `destination` is a single new directory name under the workspace,
  distinct from `sources`. It names the candidate folder. The front matter
  `destination` names the future answer destination.
- Generate UTF-8 front matter with LF, starting with `---\nstewart: question/2\n`.
  Write present fields in bytewise key order, one `key: value\n` each.
  Encode role arrays compactly in declaration order and object-key order from
  INTERFACE 3.2: each entry as given, with `role`, `source` and `label` first
  in that order and any other members after them in supplied order, so the
  shared parser reports a malformed declaration in the assessment. Strings
  escape only `"`, `\` and U+0001–U+001F: `\b`, `\f`, `\n`, `\r` and `\t`
  where they apply, otherwise `\u` with four lowercase hex digits; every other
  character is literal UTF-8. Append `---\n` and the exact body bytes. Do not insert
  examples, instructions, a missing criterion, question wording or a body
  newline. Keep selected guidance bytes separate.
- On success data is `{question_file,directories,files,assessment}`.
  `directories` lists all proposed directories relative to the candidate,
  including `materials`. The `files` array lists `{name,size,sha256}` for every proposed
  file including the question and selected guidance. Both arrays sort by
  UTF-8 name bytes. `assessment` is the data `assess` gives for the generated
  question, the guidance and the actual sizes, with the same pointers (the
  index in `files` names a file). It omits `material_bytes` from `unchecked`
  once all supplied bytes, possibly none, have actually been checked. No output includes supplied material bodies. Dry-run
  returns the exact proposed question and inventory with `writes.state:"none"`.
  With candidate errors return `candidate_invalid`, data `{assessment}` and no
  writes. A source whose bytes break an intake text rule or bound is such an
  error, reported with the CLI diagnostic whose `source` is its public name and
  whose `pointer`, `line` and `key` are null. Other refusals have null data. A
  failed creation has outcome `failed` and the data of a successful one.
- Refusals are checked in this order, and the first established is reported:
  argument errors (`input_invalid`); the candidate name
  (`candidate_path_invalid`); a missing workspace (`workspace_required`, at
  `/create` for a creation, otherwise at `/files`); a front matter destination
  overlapping the candidate; errors in the generated question, guidance and
  inventory names (`candidate_invalid`); a workspace that no longer satisfies
  the launch checks or is no longer the launched directory; an existing
  candidate (`destination_exists`); each source in `files` order (path policy, then
  access, then its bytes); the assessment with actual sizes; then creation.
  Preflight acquires no further sources once a refusal is established. An
  assessment made before any source is read counts each file's size as zero
  and keeps `material_bytes` in `unchecked`. A refusal for the candidate name
  or an existing candidate points at `/destination`, a source refusal at
  `/files/<i>/from`, and a failed creation has a null pointer.

For example, to propose an empty open inquiry:

```json
{"name":"assemble","arguments":{"fields":{"family":"open-inquiry","model":"example-model","destination":"/home/ana/returns","limit-turns":"4","limit-input-tokens":"32000","limit-output-tokens":"8000"},"body":"What can these materials establish?","guidance":null,"directories":["materials"],"files":[],"destination":"first-inquiry"}}
```

It proposes `question.md` and an empty `materials/`. The missing subject
mapping is a suggestion. A separate call with the same arguments and
`create:true` requests creation. Both calls do their own validation.

## Filesystem authority and interruption

The launcher may designate one existing absolute, candidate-only workspace
with `stewart manager-mcp --workspace DIR`. DIR follows the CLI's other
absolute path arguments, and symlinks in it are followed. Tool-supplied
workspace overrides are invalid. A relative, missing or non-directory DIR, or
one inside a Stewart store or delivery package (below), is a usage error: the
process writes the reason to stderr and exits 2 before reading stdin, with
nothing on stdout. Without a workspace, discovery, explanation, assessment and
a dry-run without source files work. A call needing filesystem access,
including every creation, refuses `workspace_required`.
The launcher chooses a workspace separate from its archives and delivery
locations. The server opens only named input files under `sources/` and
creates at most one explicitly named fresh child and its proposed entries per
call. It never resolves a Stewart reference, opens credentials or profiles,
enumerates audits, invokes the CLI or starts a provider.

Apply the CLI UTF-8 component/path limits to relative names. Reject absolute
paths, empty components, `.`, `..` and audit-reference operands. Acquire
directories through descriptors and verify exact name spelling: a source
component whose exact name is not an entry of its directory is absent
(`candidate_source_failed`) whatever the host's name rules. Exclude symlinks,
special entries, mount crossings below the workspace, and source files with
more than one hard link. Check opened identities and sizes and stop on changes
or ambiguity. Check the workspace and input ancestry for a Stewart store marker
or delivery package before admitting it (metadata only: `STORE.json` or the
reserved `stewart-return-` directory prefix). At launch the store check walks
the workspace's actual parent chain and the package check its path components
as given. Each `assemble` call with a workspace checks it again: a workspace
that no longer satisfies these checks, or a DIR that now names another
directory, refuses `candidate_path_invalid` with a null pointer. Reject reserved candidate
destination names and collisions under the host's actual name rules. In
particular, a case alias cannot turn exclusive creation into editing an
existing candidate. These checks cover the supplied workspace only. The origin
of detached, renamed copies and the safety of arbitrary host directories remain
unknown. The ordinary CLI still admits distinct hard-link names in a manager's
literal submission.

The candidate `destination` is one name under the CLI component rules. An
empty or otherwise invalid name, `sources`, `STORE.json` or a name beginning
`stewart-return-` refuses `candidate_path_invalid`, as does a `from` or `destination`
beginning `stw1:`. With a workspace, a front matter `destination` that names
the candidate, a path inside it or a directory containing it refuses
`candidate_path_invalid` at `/fields/destination`. The comparison uses path
components after dropping empty and `.` ones, without resolving `..`, and
opens nothing at the answer destination; a destination that is not a valid
absolute path is left to the assessment.

Read only the listed sources, checking the UTF-8 text and all intake limits
while acquiring them. Compute the proposed bytes before any creation.
Neither dry-run nor assessment probes the answer destination or makes an
archive, temp file, lock, reference or directory. Dry-run can identify an
existing candidate by name when a workspace is present. Report
`destination_exists` on a known collision, an existing entry of that name
under the host's name rules, in a dry run as at creation. Successful preflight
makes no promise that a later exclusive create will succeed.

On explicit creation claim the new child directory exclusively, create
directories through retained descriptors, and publish each file exclusively
with its proposed, verified bytes. Use 0700 directories and 0600 files.
Independent calls racing for the same destination have at most one winner.
Refuse an existing destination, including an incomplete earlier candidate.
A path-policy violation refuses `candidate_path_invalid`. A source that cannot
be opened or read, or changes identity or size while read, gives
`candidate_source_failed`. A failed write or verification gives
`candidate_write_failed`. Name known partials, stop further writes and leave
them for inspection.

Creation order is the candidate directory, then `data.directories` in order,
then `data.files` in order, so `question.md` is written last. Paths in
`writes` are workspace-relative and begin with the candidate name.
`writes.created` lists, in that order, the directories created and the files
whose bytes were written and verified. `writes.incomplete` lists a file whose
exclusive create succeeded, or failed other than because the name existed,
but whose bytes were not verified; it appears only there. The state is `none`
when both lists are empty and no effect is uncertain, `complete` when every
proposed entry was created and verified, `partial` when creation stopped after
creating some, and `unknown` when a failed operation leaves an entry's
existence unobservable, for example a failed candidate directory creation after
which the name exists but cannot be shown to be this call's.

A lost reply leaves the caller uncertain. Inspect the named directory using
ordinary file tools before repeating. Its presence alone cannot establish
completion. Preserve it for the caller and require a fresh destination on
retry.
