# Stewart

>Make it *just* so

Stewart is an experimental command-line tool for asking an AI auditor a bounded
question about files you choose. You supply the question, materials, answer form
and limits. Stewart preserves that commission, gives the auditor tools to read
and respond, and returns its recorded answer with verified delivery.

The aim is to make an inquiry easy to commission and possible to account for:
what the auditor received, what it said, and what Stewart actually did. The
auditor may find nothing, disagree with the premise or explain that the evidence
is insufficient. You judge the answer; Stewart does not grade its conclusions.

## Status

**Version 0.0.2 — experimental.** The audit lifecycle is implemented, and
recorded earlier builds passed Linux tests with a fake provider. Small commissions have run against a
real model across all three implemented forms and returned answers with verified
delivery. Its usefulness in real inquiries and readiness for routine use remain
to be established.

Stewart is written in Rust and built as one statically linked Linux binary for
x86_64 and aarch64. Native macOS is a development environment, not a product
target. The current adapter uses the Anthropic Messages API; no model is yet
qualified, and other auditor runtimes are unimplemented.

The `stewart.reply/2` interface revision and its citation-refusal correction have
passed recorded Linux acceptance. A six-placement matched Haiku comparison
demonstrated ordinary submission, seeded-refusal recovery and manager custody
after turn-limit stops. Matching launcher rehearsals covered the builds used
in those encounters.

The [qualification record](apparatus/qualified.md) identifies current Linux
results, exact source/binary identities and selected original evaluations.
Scripted acceptance has passed on native aarch64 and x86_64 under Rosetta;
reproducible static builds have been observed on both architectures. A result
applies to its recorded build. `python3 -I -B apparatus/qualified.py check`
verifies retained results and reports source drift.

Small commissions with Haiku, Fable and Opus have exercised all three forms,
citation repair, limits and manager custody. The [interface observations](apparatus/studies/interaction/RESULTS.md),
[recovery findings](apparatus/studies/haiku-recovery/RESULTS.md) and
[vocabulary comparison](apparatus/studies/vocabulary/RESULTS.md) preserve their
substantive readings and limitations. They establish no general model preference.
Real-provider captures have no independent direct-TLS witness; calculated cost
and independent billing remain distinct observations.

Full C10 repetitions, qualified real compaction and killed-and-continued audits,
native x86_64/WSL2 qualification, Linux Cargo tests and a claim-by-claim coverage
review remain outstanding. Observations on study builds qualify no model. A
release build configuration does not itself meet the
[release requirements](ACCEPTANCE.md).

Interfaces and record formats are still evolving. Each audit is bound to the
exact binary that created it: keep that binary until its audits close. A newer
binary cannot continue or close them. Existing records are never upgraded in
place; see [Versions and legacy obligations](CONTRACTS.md#versions-and-legacy-obligations).

## What an inquiry looks like

You might ask whether supplied code meets stated requirements, compare two
implementations, or turn a concern into a working question and investigate it.
Stewart has three answer forms: open inquiry, inquiry framing and comparison. The
[worked examples](examples/questions/README.md) show their inputs, auditor calls
and rendered answers; the answers are hand-written illustrations, not model
results.

The submission is an ordinary folder containing `question.md` (settings and
your question) and `materials/` (selected UTF-8 text files). Stewart does not
execute the supplied code or fetch more material. The auditor works through
Stewart's tools on accepted copies, with no shell, general filesystem access
or network retrieval.

For open inquiry, `guidance: guidance.md` in the question's front matter selects
that file beside `question.md` as the complete replacement for built-in family
guidance. Omit the setting to use the default. The attachment is nonblank UTF-8
text without NUL, at most 256 KiB. It changes guidance, not tools or custody.
Prepare shows its text and origin; `receipt REF --read guidance-file` recovers
its accepted bytes. For example, a guidance file can ask for a connected account:

```text
Address the question from the supplied materials in one connected account.
State your conclusion and its reach early, and connect it to evidence. Add
separate observations or limits when they help explain the answer. Uncertainty,
missing evidence and disagreement remain valid responses.
```

Acceptance fixes that text; editing the source later does not change the audit.
The [interface](docs/INTERFACE.md#selected-family-guidance) defines selection,
source-change checks and readback. The guidance facility awaits its Linux
qualification; a worked instruction is not evidence that it improves answers.

Run allowances count cumulative turns and input/output tokens. Stewart enforces
no dollar ceiling.

A launcher can supply the provider key through a one-use inherited descriptor
with `run REF --key-fd FD`; `ANTHROPIC_API_KEY` is an explicit alternative.
Supplying both refuses. The descriptor path keeps the key out of arguments and
environment. If the provider reflects it, Stewart stops and marks the exact
private evidence for review; derived diagnostics are redacted. Review that state
and revoke the exposed key before further provider use. The input bounds and
protection limits are in [the credential interface](docs/INTERFACE.md#61-provider).

Three locations have separate roles:

| Location | What it holds |
| --- | --- |
| Submission folder | Your editable question and materials. |
| Archive | The accepted copies, instructions, exchanges, recorded work and custody records. |
| Answer destination | A sealed answer package, copied and read back to verify delivery. |

Stewart retains archive records through close and provides no deletion service.
You manage storage and backups. Its access boundaries serve cooperative parties;
they do not protect records against the archive owner.

## The command path

1. **Set up:** `stewart new FOLDER [--archive ROOT]` creates an audit reference.
   It scaffolds an absent submission folder and leaves an existing one unchanged.
   The archive comes from `--archive` or `STEWART_ARCHIVE`.
2. **Prepare:** after editing, `stewart prepare REF` inventories and hashes the
   files and pins the instructions, tools and limits. It returns a preparation
   handle; it accepts no commission yet.
3. **Commission:** `stewart commission REF HANDLE --i-am-finished` copies and
   verifies that prepared selection. Later edits to your folder cannot change
   the accepted copy.
4. **Run:** `stewart run REF` places the auditor. This is the only step that
   needs the provider key and network. The auditor reads, records, prepares and
   explicitly submits its answer. Submission seals the answer and initiates
   verified delivery. An interrupted run can continue the same audit with its
   records and cumulative limits; `run` again is a continuation, not a reset.
5. **Close:** `stewart close REF` ends authoring. Before launch it creates no
   answer. After launch it stops the run and, if needed, seals recorded work
   with manager attribution and delivers it. If close requests confirmation,
   inspect the delivered copy and use the returned token to finish. Any known
   loss needs explicit surrender. Manager preservation is distinct from auditor
   submission.

`stewart receipt REF` reads the fixed commission; `stewart status REF` reports
run, seal, delivery and close separately. `stewart help` explains the commands
and their continuation paths. The exact interface is in
[docs/INTERFACE.md](docs/INTERFACE.md).

## Working on Stewart

Start with [AGENTS.md](AGENTS.md) for development rules and
[DEVELOPMENT.md](DEVELOPMENT.md) for setup, builds, checks and evidence retention.
The crate needs vendored dependencies and the Linux suites use pinned container
images; DEVELOPMENT describes how to prepare them. Local Mac tests help
development but do not qualify Linux behavior.

Active work lives in tracked `*-PLAN.md` files. List them with
`git ls-files '*-PLAN.md'`; the coordinating plan owns work order, and topic
plans own their remaining decisions and tasks. Plans describe proposed work;
the specification below defines the product.

| Read | For |
| --- | --- |
| [DESIGN.md](DESIGN.md) | Purpose, responsibilities and architecture. |
| [CONTRACTS.md](CONTRACTS.md) | Decided behavior, boundaries and their reasons. |
| [ACCEPTANCE.md](ACCEPTANCE.md) | The evidence required to establish those claims. |
| [docs/INTERFACE.md](docs/INTERFACE.md) | CLI, auditor tools, records and test builds. |
| [docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md) | Question forms, exact auditor instructions and answer rendering. |
| [service/README.md](service/README.md) | The Rust crate and its modules. |
| [apparatus/README.md](apparatus/README.md) | Build and test apparatus, including the independent acceptance driver. |

`service/` is the product; `apparatus/` does not ship. `examples/` contains worked
questions. `riker/` describes an optional [consultation procedure](riker/RIKER.md).
`CLAUDE.md` links to `AGENTS.md` so development agents read the same rules.

## License

MIT. See [LICENSE](LICENSE).
