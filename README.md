# Stewart

Stewart is a custodian for bounded inquiries between cooperative parties. The
manager supplies a question, selected files, an answer family and limits.
Stewart places an AI auditor in that arrangement and returns its answer
faithfully, without judging its conclusions.

The manager's working model is one submission folder, one acceptance boundary
and one close action. Stewart's opinions live in its question families and
instructions; missing evidence, no finding and disagreement remain ordinary
answers. Records preserve who said what and what Stewart actually did.

## What it is

Stewart is a command-line program written in Rust, the crate in
[`service/`](service/README.md). It is built as one statically linked binary,
`stewart`, for Linux x86_64 and aarch64; Linux is the only supported platform.
An audit goes through these commands:

1. `stewart new FOLDER [--archive ROOT]` creates a reference to the audit in
   the archive that `--archive` names, or else `STEWART_ARCHIVE`. An absent
   FOLDER is created as the submission folder: `question.md` (settings and the
   question) and `materials/` (the files the auditor may read). An existing
   folder is used unchanged.
2. `stewart prepare REF` scans and hashes the folder, checks the intake rules
   and pins the arrangement: instructions, tools and limits. It accepts
   nothing.
3. `stewart commission REF HANDLE --i-am-finished` copies and verifies the
   prepared selection. Acceptance fixes that copy; later edits to the folder
   cannot change it.
4. `stewart run REF` places the auditor. Only `run` uses the network and the
   provider key; it speaks the Anthropic Messages API. The auditor works only
   through Stewart's tools on the captured copies, recording, preparing and
   submitting its answer. A submitted answer is sealed, copied to the
   manager's destination and read back to verify it. If a run dies, `run`
   again continues the same audit with its records and cumulative limits.
   During a long run, Stewart asks the provider to summarize its active context
   and continues from that signed summary. Original exchanges and recorded work
   remain in the archive; summary calls use the same cumulative allowances.
5. `stewart close REF` ends the audit from any state. Before launch it creates
   no answer. After launch it stops any run, seals the recorded answer for the
   manager if the auditor did not, and delivers the copy if one is still owed.
   A plain close finishes only when a copy without losses was verified before
   the first close request. Otherwise close stops unfinished, awaiting
   confirmation, and the audit ends with `stewart close REF --confirm TOKEN`,
   adding `--surrender LOSS` for each loss the copy names.

`stewart receipt` and `stewart status` read the fixed commission and the
audit's state at any time, and `stewart help` explains the rest. Stewart keeps
its records in the manager's archive and removes nothing.

## Status (2026-10-31)

**Built:** the manager commands above, the auditor's tools and answer protocol,
the run adapter, seal, verified delivery and close. The crate is at version
0.1.0.

**Tested on Linux against a fake provider.** The scripted acceptance suite
([`apparatus/acceptance.sh`](apparatus/acceptance.sh)) builds the release
binary and a test build with fault points and sabotage controls in pinned Linux
containers, then runs an independent black-box driver against them, on aarch64
natively and on x86_64 under Rosetta emulation. The driver is written in Python
from the specification by an author who does not read the implementation, and
a fake provider stands in for the model. The suite's sabotage and driver
controls show that the checks catch the failures they look for, and an
integrated end-to-end audit (prepare, commission, a fake auditor working
through the run, submit and seal, verified delivery, close) runs on each
architecture's release binary. The suite passed at source `dc85948`: on
aarch64 natively, with its timing gate on, and on x86_64 under Rosetta
emulation, where the gate is reported but not enforced. Since that run the
service has gained the manager's optional effort setting, reports the
provider's error message with a refusal, and enables provider compaction;
those changes and the matching driver cases await the next suite run.
[`apparatus/qualified.md`](apparatus/qualified.md) records the latest runs of
each suite, the source commits they cover and their results, and
`python3 -I -B apparatus/qualified.py check` reports what has changed since.

**Not yet done:**

- Native WSL2 qualification with the same binary, driver and fake provider,
  and any native x86_64 run: the x86_64 runs so far were emulated.
- Linux runs of the crate's own cargo tests. They have run only on the
  development Mac, where the Linux-only calls use development fallbacks.
- The two-build reproducibility comparison on the service. It has run only on
  an early skeleton of the crate.
- Retention of damaged originals for review (ACCEPTANCE C18): the suites
  discard a variant's working copies once it has passed or its control has
  fired.
- Container runs of the service and apparatus changes made since the last
  suite run; `qualified.py check` lists them.
- A claim-by-claim check of the suite's coverage against
  [ACCEPTANCE.md](ACCEPTANCE.md).
- Real-model conformance: whether named models can use the arrangement and
  finish. It needs named models and a budget. Stewart has not been run against
  a real model, the release's TLS path to the real provider, with its built-in
  roots, is unexercised, and the pinned request settings (16,000 `max_tokens`
  per request, a 600 s timeout) are untested against real responses, as is
  the effort parameter and provider compaction.

## Where to read next

- [DESIGN.md](DESIGN.md): design and vision: responsibilities, the manager's
  path and the architecture.
- [CONTRACTS.md](CONTRACTS.md): the decided behavior, its status and the
  reasons for declined changes.
- [ACCEPTANCE.md](ACCEPTANCE.md): the evidence the implementation owes.
- [docs/INTERFACE.md](docs/INTERFACE.md): the exact CLI, auditor tools, records
  and test builds.
- [docs/QUESTION-FORMS.md](docs/QUESTION-FORMS.md): the three question forms,
  the exact texts the auditor sees and the answer renderer.
- [examples/questions/](examples/questions/README.md): worked examples of the
  three forms: submission folders that prepare as written, with hand-written
  walkthroughs of an auditor's calls and the rendered answers.
- [service/README.md](service/README.md): a guide to the crate.
- [DEVELOPMENT.md](DEVELOPMENT.md): building, testing and evidence retention.
- [AGENTS.md](AGENTS.md) (CLAUDE.md links to it): the guide for development
  agents.
- [riker/](riker/RIKER.md): a development procedure for relaying questions
  between the local agent and Riker, a separate Claude Project.

## Repository map

| Entry | Contents |
| --- | --- |
| `service/` | The Rust crate: the product. |
| `apparatus/` | Build and test apparatus: the Containerfile from which `step2.sh` builds the pinned Linux toolchain images, the container scripts, the independent driver with its fake provider (Python, standard library only), the repository checks (`check_links.py`) and the qualification record of tested runs (`qualified.py`, `qualified.json`, `qualified.md`). It does not ship. |
| `docs/` | `INTERFACE.md` and `QUESTION-FORMS.md`. |
| `examples/` | Worked question examples. |
| `DESIGN.md`, `CONTRACTS.md`, `ACCEPTANCE.md` | The design, the decided behavior and the evidence owed. |
| `DEVELOPMENT.md` | Building, testing and evidence retention. |
| `AGENTS.md`, `CLAUDE.md` | Development rules; `CLAUDE.md` is a link to `AGENTS.md`. |
| `riker/` | Development procedure: relaying questions to Riker, a separate Claude Project. |
| `*-PLAN.md` | Active development plans: working accounts, not specification. |
| `.tmp/` | Ignored temporary storage; only its note, `AGENTS.md`, and a `CLAUDE.md` link to it are tracked. |
| `LICENSE` | The license. |

Earlier versions of Stewart were a Python tool, with a separate Rust intake
program; both were retired on 2026-10-30. Their code and the design-era records
remain in Git history (the last commit containing them is `267aaf0`).

## License

MIT. See [LICENSE](LICENSE).
