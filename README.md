# Stewart

>Make it *just* so

Stewart bounds inquiries over files you choose for examination by an auditor,
currently implemented as calls to Anthropic's Messages API. Supply a question,
materials, an answer form and limits. Stewart preserves the inputs, gives the
auditor tools to investigate them, and delivers its recorded answer as structured
data and readable Markdown.

## Choose a question form

| Form | Example question |
| --- | --- |
| [Open inquiry](examples/questions/open/WALKTHROUGH.md) | Does this implementation meet the supplied requirements? |
| [Inquiry framing](examples/questions/framing/WALKTHROUGH.md) | We are concerned about missed reminders. Frame and investigate a useful question from these materials. |
| [Comparison](examples/questions/comparison/WALKTHROUGH.md) | How do implementations A and B compare against these reliability criteria? |

Each form permits uncertainty, inadequate evidence and disagreement with the
question's premise. You judge the conclusions. Citation checks verify locations
and exact quotations; assessing their support for a conclusion remains your
judgment. The linked walkthroughs are hand-written illustrations of inputs,
auditor calls and rendered answers.

Open inquiry also accepts [your own guidance](docs/INTERFACE.md#selected-family-guidance).

## Run an inquiry

The submission is an ordinary folder: `question.md` holds settings and your
question; `materials/` holds the selected UTF-8 text files. Use absolute paths
for the submission folder, archive and answer destination, keeping the three
locations separate. The [worked examples](examples/questions/README.md#preparing-an-example)
include a submission you can copy and prepare.

1. **Set up:** `stewart new FOLDER --archive ROOT` creates the reference `REF`
   and scaffolds an absent folder. An existing submission folder is left intact.
2. **Prepare:** edit the question and materials, then run `stewart prepare REF`
   to inspect the selection, instructions, tools and limits. It returns a handle
   `HANDLE`; no commission is accepted yet.
3. **Commission:** `stewart commission REF HANDLE --i-am-finished` captures and
   verifies the prepared selection. Later source edits cannot change the audit.
4. **Run:** `stewart run REF` starts the auditor, which reads and records through
   Stewart's tools. Explicit submission seals the answer and initiates delivery, which
   Stewart verifies by reading the copy back.
5. **Close:** `stewart close REF` ends authoring and reports what remains to close
   the audit. After launch, it preserves any unsubmitted work with manager
   attribution. If it requests confirmation, inspect the delivered copy and
   follow the returned command to finish.

Steps 1–3, `status`, `receipt` and a `close` before launch are local and need
no provider key, so they check a new installation without spending anything.

An interrupted run can continue the same audit with its recorded work and
cumulative limits intact. `stewart receipt REF` recovers the accepted commission;
`stewart status REF` distinguishes execution, submission, delivery and closure.
`stewart help` explains the commands. The [CLI interface](docs/INTERFACE.md)
also defines structured JSON replies for scripts and agent managers.

## Before running

- **Platform:** Linux x86_64 or aarch64, including WSL2. The archive must be on
  local ext4, xfs or btrfs; on WSL2 keep it on the Linux filesystem, since
  Windows drives under `/mnt/` are refused for it. The answer destination may
  be under `/mnt/`.
- **Access:** the auditor works on accepted text through Stewart's tools. It
  cannot execute supplied code, use a shell or retrieve additional material.
- **Credentials:** only `run` needs the provider key and network. Supply the key
  through `--key-fd FD` or `ANTHROPIC_API_KEY`, never both. The
  [credential interface](docs/INTERFACE.md#61-provider) describes the descriptor
  route and protection limits.
- **Allowances:** turns and input/output tokens accumulate across the audit,
  including continuations. They are not a dollar ceiling.
- **Storage:** the archive keeps accepted inputs, exchanges and recorded work;
  the destination receives the sealed answer package. Close retains the archive.
  You manage storage and backups; Stewart provides no deletion service or
  protection against the archive owner.
- **Writer:** keep the exact binary that created an audit until it closes.
  A newer binary cannot continue or close that audit. Records are never upgraded
  in place; see [version obligations](CONTRACTS.md#versions-and-legacy-obligations).

## Status

**Version 0.0.2 — experimental.** Small live commissions have returned answers
with verified delivery across all three forms. Recorded Linux acceptance runs
cover their exact builds; endpoint alignment for the models a release will name
and platform qualification remain outstanding. Bounded Messages continuations preserved recorded work; one audit
submitted and another exhausted its allowance with a partial account later
sealed and closed by the manager. A bounded Opus encounter preserved an account
through real provider compaction, revised it and submitted a verified return.
The [qualification record](apparatus/qualified.md)
identifies those builds and results.

A default-off development adapter, included only in source builds, has
completed native open inquiries through an agent harness with auditor
submission, verified delivery and close. Its captured usage remains partial and
live continuation unexercised. Full 64 KiB material pages that the harness once
replaced with previews arrived whole in one bounded encounter after a transport
change. These native encounters establish no model or platform qualification.

Stewart is a single Rust binary, supported on Linux x86_64 and aarch64. The
source also builds on Apple-silicon macOS, without a support or qualification
claim. See [building and testing](development/DEVELOPMENT.md), the
[crate guide](service/README.md) and [contributing](AGENTS.md), or read the [design](DESIGN.md),
[behavioral contracts](CONTRACTS.md) and [acceptance requirements](ACCEPTANCE.md).

## License

MIT. See [LICENSE](LICENSE).
