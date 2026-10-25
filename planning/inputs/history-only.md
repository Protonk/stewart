Captured 2026-10-25: a second external proposal the user relayed for the same
decision round as [the custodial-core proposal](custodial-core.md). It is
preserved verbatim below; it is input to an inquiry, not a decision or a
commission, and its claims about Stewart are to be rechecked against the
source selected for that inquiry.

---

# Capsule Proposal: `--history-only` Audit Mode

## Idea

Introduce `stewart --history-only`, a restricted audit profile in which an auditor investigates Git history without receiving a working tree or direct access to a Git repository.

Stewart supplies a bounded historical inspection interface. The auditor asks questions of Git material, examines the observations returned, and produces a report. Stewart retains custody of the commission, observations, return, and outcome.

This is complementary to `--files-only`:

| Mode | Workspace | Git history | Custody |
|---|---|---|---|
| Standard | Yes | Yes | Yes |
| `--files-only` | Yes | No | Yes |
| `--history-only` | No | Yes | Yes |

These are authorization profiles over Stewart's three custodial responsibilities, not separate audit systems.

## Operation

1. **Commission.** The manager supplies a pinned revision, question, authorized historical scope, and stopping condition. The default scope is the pinned commit and its reachable ancestry; other refs or unreachable objects require explicit authorization.

2. **Inspection.** Stewart exposes bounded, read-only facilities corresponding to Git operations such as `log`, `show`, `diff`, `blame`, `ls-tree`, `rev-list`, and `cat-file`. The auditor receives results, not repository access. Historical file contents may be read without materializing files in a workspace.

3. **Return.** The auditor reports an `answer`, `needs-evidence`, or `reframe`, with its completion state recorded separately.

4. **Custody.** Stewart preserves the commission, authorized queries, their parameters and results or durable references to them, object identities, historical-view configuration, auditor's return, failures, and managerial disposition. No working-tree harvest is necessary.

Git's object database makes this unusually economical: commits, trees, and blobs can be interrogated without checkout, staging, or branch manipulation. Stewart may use its own protected repository and Git plumbing to serve these observations.

## Boundaries and difficulties

- **Historical view:** Replacement refs, grafts, configuration, moving refs, and missing objects can change or limit what Git reports. Stewart must establish and preserve the effective view, normally using immutable object IDs and disabling unintended replacements.
- **Read-only enforcement:** The auditor receives a typed inspection interface, not unrestricted Git commands. Stewart must also prevent inspection operations from unexpectedly modifying repository metadata.
- **Scope and volume:** Queries must respect the commission's authorized reachability, paths, and resource limits. A broad history query may require pagination or a bounded result rather than unlimited output.
- **Interpretation:** Git history is evidence of recorded repository states, not necessarily a complete history of development activity, authorship, or intention.
- **Responsibility:** Stewart must not become a historical-analysis agent. It provides observations; the auditor formulates hypotheses, connects evidence, and draws conclusions.

An auditor may still require ordinary execution infrastructure to reason and compose its report. `--history-only` withholds a *subject workspace*, not necessarily every form of temporary computation.

## Proposed decision

Accept `--history-only` as a provisional third audit profile, initially limited to the pinned commit's ancestry and a small set of controlled inspection operations.

Its chief attraction is architectural: **Stewart can provide useful custody over an inquiry into Git material without ever giving the auditor a Git repository or working tree.**

It also provides a clean test of the three-responsibility design. Historical inspection and custody capture remain; workspace access is deliberately absent. No new custodial responsibility is required.
