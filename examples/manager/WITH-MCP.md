# Assembling the submission with the preparation MCP

This walkthrough reaches the same commission as [files only](FILE-ONLY.md),
but Ana, or an agent working for her, prepares the submission folder through
`stewart manager-mcp`. The server explains the question families, checks a
proposal with the CLI's own rules and writes the candidate folder. It cannot
prepare, accept, run or close an audit. The [README](README.md) explains the
paths and placeholders.

## 1. Supply the sources and start the server

The server reads only files under its workspace's `sources/` directory and
creates candidate folders only in the workspace. Ana puts the three material
files there and creates her return destination:

```text
$ mkdir -p /home/ana/candidates/sources/reminders /home/ana/returns
$ cp examples/questions/open/submission/materials/* /home/ana/candidates/sources/reminders/
$ stewart manager-mcp --workspace /home/ana/candidates
```

The server speaks MCP on standard input and output, one JSON-RPC message per
line. Without `--workspace` it can still discover, explain, assess and propose
a candidate without source files; it cannot read sources or create anything.

## 2. Initialize

The client sends:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"clientInfo":{"name":"example-client","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

The reply to the first line is:

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"stewart-manager","version":"1"}}}
```

Each tool call below is a `tools/call` request, for example
`{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"discover","arguments":{}}}`.
Its result carries the same object twice: as `structuredContent` and as JSON
text. The blocks below show the arguments sent and members of
`structuredContent`.

## 3. Discover and explain

`discover` with no arguments returns:

```json
{"outcome": "completed",
 "data": {"families": [
   {"family": "open-inquiry/1", "available": true, "purpose": "Investigate the question as written."},
   {"family": "inquiry-framing/1", "available": true, "purpose": "Formulate and investigate a working question from the concern."},
   {"family": "comparison/1", "available": true, "purpose": "Relate the named alternatives to a criterion."}]},
 "writes": {"state": "none", "created": [], "incomplete": []}}
```

`explain` with `{"family": "open-inquiry/1"}` returns the family's material
roles. For open inquiry one is recommended and none is required:

```json
{"outcome": "completed",
 "data": {"descriptor": {"family": "open-inquiry/1", "roles": [
   {"id": "subject", "meaning": "What you want the auditor to examine.", "minimum_recommended": 1, "severity": "suggestion"},
   {"id": "context", "meaning": "Background such as requirements, circumstances or assumptions.", "minimum_recommended": 0, "severity": null},
   {"id": "report", "meaning": "Another author's observations or reported results.", "minimum_recommended": 0, "severity": null}]}}}
```

## 4. Propose a candidate

`assemble` takes the front matter fields, the question body, the material
names with the sources to copy, and a name for the candidate folder. Without
`create` it is a dry run. Ana first leaves out the role declarations and asks
for full detail:

```json
{"fields": {"family": "open-inquiry", "model": "claude-opus-5-5", "destination": "/home/ana/returns",
            "limit-turns": "200", "limit-input-tokens": "20000000", "limit-output-tokens": "400000",
            "inquiry": "reminder-restarts"},
 "body": "Audit our app to make sure there are no bugs.\n",
 "guidance": null,
 "directories": ["materials"],
 "files": [{"name": "materials/a.py", "from": "reminders/a.py"},
           {"name": "materials/requirements.txt", "from": "reminders/requirements.txt"},
           {"name": "materials/supplied-report.txt", "from": "reminders/supplied-report.txt"}],
 "destination": "reminders",
 "detail": "full"}
```

```json
{"outcome": "completed",
 "data": {"assessment": {"valid": true,
   "defects": [{"reason": "role_unmapped", "severity": "suggestion", "role": "subject",
                "message": "No source is mapped to the subject role.",
                "remedy": "Identify what you want examined if it is available. A broad question is welcome."}],
   "unchecked": ["filesystem", "source_stability", "acceptance"]}},
 "writes": {"state": "none", "created": [], "incomplete": []},
 "explanation": ["This is a dry run: nothing was written. The same arguments with create:true create the candidate folder, which the CLI then prepares. Warnings and suggestions are optional."]}
```

The candidate is valid: the missing mapping is a suggestion. The assessment
uses exactly the diagnostics of CLI `prepare`, and it lists what only later
CLI operations can establish. Ana adds the declarations to `fields`:

```json
"material-roles": [{"role": "subject", "source": "materials/a.py"},
                   {"role": "context", "source": "materials/requirements.txt"},
                   {"role": "report", "source": "materials/supplied-report.txt"}]
```

and drops `detail`. The dry run now proposes:

```json
{"outcome": "completed",
 "data": {
   "question_file": "---\nstewart: question/2\ndestination: /home/ana/returns\nfamily: open-inquiry\ninquiry: reminder-restarts\nlimit-input-tokens: 20000000\nlimit-output-tokens: 400000\nlimit-turns: 200\nmaterial-roles: [{\"role\":\"subject\",\"source\":\"materials/a.py\"},{\"role\":\"context\",\"source\":\"materials/requirements.txt\"},{\"role\":\"report\",\"source\":\"materials/supplied-report.txt\"}]\nmodel: claude-opus-5-5\n---\nAudit our app to make sure there are no bugs.\n",
   "directories": ["materials"],
   "files": [
     {"name": "materials/a.py", "size": 175, "sha256": "3fed093a5696428b7440ae3a0f93d2bd3bc93084b495fc3ec6297ab78c23afce"},
     {"name": "materials/requirements.txt", "size": 662, "sha256": "3c8aa8422012374ddd204acebf0ef45a78fa49cf8fb129c0a3faa104329edb98"},
     {"name": "materials/supplied-report.txt", "size": 591, "sha256": "86b5be5c14dad39f2facfb70607658bdc637f2df5a678e78e70972c459b9296d"},
     {"name": "question.md", "size": …, "sha256": …}],
   "assessment": {"valid": true, "defects": [], "unchecked": ["filesystem", "source_stability", "acceptance"]}},
 "writes": {"state": "none", "created": [], "incomplete": []}}
```

The generated `question.md` writes the fields in a fixed order, with no
comments, and ends with the exact body. The server has read every source, so
`material_bytes` is no longer unchecked. Nothing has been written.

## 5. Create the candidate

The same arguments with `"create": true` create the folder:

```json
{"outcome": "completed",
 "writes": {"state": "complete",
   "created": ["reminders", "reminders/materials", "reminders/materials/a.py",
               "reminders/materials/requirements.txt", "reminders/materials/supplied-report.txt",
               "reminders/question.md"],
   "incomplete": []}}
```

The data is the dry run's. Creation is exclusive and writes `question.md`
last; each file is read back before it is listed as created. If creation
stops, `writes` names what exists and what is incomplete. A lost reply leaves
Ana unsure: she inspects the folder with ordinary file tools and retries under
a fresh name, because an existing candidate, complete or not, is never reused:

```json
{"outcome": "refused",
 "problem": {"reason": "destination_exists", "pointer": "/destination",
             "remedy": "Inspect the existing folder with ordinary file tools, then choose a fresh destination."},
 "data": null,
 "writes": {"state": "none", "created": [], "incomplete": []}}
```

## 6. Continue with the CLI

The candidate is an ordinary submission folder. `new` takes it as it is:

```text
$ stewart new /home/ana/candidates/reminders --archive /home/ana/stewart-archive
stewart new: completed
Effects: reference created

reference: REF
archive: /home/ana/stewart-archive
archive created: true
folder: /home/ana/candidates/reminders
scaffold created: false
writer:
  path: /usr/local/bin/stewart
  sha256: …
notices: none

Next:
  /usr/local/bin/stewart prepare REF
      Edit question.md and materials/, finish, then prepare. Leave the folder unchanged from prepare until commission returns.
```

From here Ana follows [files only](FILE-ONLY.md) from the second `prepare` of
step 3, since her destination already exists: commission, run, status and
close, with the same results, except that her audit has one diagnostic fewer,
so the final refusal retains `diag/1.json`. Her preparation
reports the same question body, materials and settings as the file-only
folder, and pins the same arrangement apart from its audit identifier and
time. Only `question.md`'s comments and field order differ, and the return
delivers the question body, not the file.
