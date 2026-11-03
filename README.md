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

**Version 0.0.2 — experimental.** The audit lifecycle is implemented, and Linux
tests with a fake provider have passed. One small commission has run against a
real model and returned a verified answer. Its usefulness in real inquiries and
its readiness for routine use remain to be established.

Stewart is written in Rust and built as one statically linked Linux binary for
x86_64 and aarch64. Native macOS is a development environment, not a product
target. The current adapter uses the Anthropic Messages API; no model is yet
qualified, and other auditor runtimes are unimplemented.

What the evidence establishes:

- **Scripted Linux behavior:** the current acceptance suite, including the
  credential checks, passed on native aarch64 and x86_64 under Rosetta emulation.
  The suite exercises the release build through
  independently witnessed audits, with faults and deliberately broken controls
  in a separate test build. Native timing checks passed; emulated timings do not
  gate the result.
- **One real-model sanity run:** a single open-inquiry commission on
  `claude-haiku-5-5` went through the direct Anthropic endpoint with the
  release's built-in TLS roots. The model read both materials through Stewart's
  tools, recorded four cited entries, prepared and submitted; the auditor seal,
  verified delivery and ordinary close were observed, and the credential scans
  were clean. An earlier attempt under a host VPN never reached the provider
  and consumed nothing.
- **Four mechanism runs** on the same specimen then observed a real 401
  rejection recorded without retry, a turn limit with the manager close and
  confirmation path, an accepted effort setting under the request cap, and
  the minimum output allowance ending at its limit.
- **Limits of that result:** one model, one family, no compaction, no
  interruption and no `max_tokens` stop against real responses. It is a
  sanity result, not release conformance, and qualifies no model. Native x86_64 and
  WSL2 qualification, Linux Cargo tests and a claim-by-claim coverage review
  also remain outstanding.
- **Credential launch:** a synthetic-key rehearsal passed on native Linux,
  including same-user and different-user process-access controls, interrupted
  requests, exact return verification, and withholding contaminated exports.
  The private originals and independent credential witness remain retained.
- **Small-commission apparatus:** a Linux aarch64 rehearsal covered ordinary
  and inadequate-evidence submissions for all three forms. All 13 audit scenarios,
  14 reviewer comparisons and seven later-custody comparisons behaved as expected;
  both process-access controls fired. This demonstrates the bounded launch and
  review apparatus against a fake provider. Full real-model conformance remains
  outstanding.
- **Reproducible builds:** two service builds produced identical static binaries
  for each Linux architecture using the recorded toolchain images.

[The qualification record](apparatus/qualified.md) holds the exact source and
binary identities, counts and retained evidence. A result applies to those
recorded builds, not automatically to this version or the current checkout.
`python3 -I -B apparatus/qualified.py check` validates the record and reports
source drift. A release build is a build configuration, not a claim that the
project has met all of [its release requirements](ACCEPTANCE.md).

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
