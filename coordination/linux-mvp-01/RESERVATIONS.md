# What still bothers me

Written 2026-10-28 after re-reading the three views in this folder: the
[conversation](CONVERSATION.md), the [radical design](DESIGN.md) and the
[clean-sheet design](STEWART.md). These are my reservations about the new stance
itself, not about how well it was written up. Earlier held-back notes are in
[CONVERSATION-HELD-BACK.md](CONVERSATION-HELD-BACK.md); several of those are
dissolved by the new stance and aren't repeated here.

They are grouped by what they are about and ordered within each group by how much
they bother me.

## What Stewart has become

1. **Stewart now conducts the investigation, not just its custody.** Before, Stewart
   held material around an investigation that happened somewhere else. Now it
   writes the orientation, chooses the tools, sets the effort, sends a reminder
   when the model stops early, warns at 90% of a limit and decides when the run
   ends. Every one of those shapes what answers come back. The neutrality
   commitment says Stewart's influence lives in the auditor's world. That world is
   now almost entirely Stewart's own writing, prompt included. Neutrality only
   survives if each of those choices gets deliberated as an influence on outcomes,
   not treated as plumbing. Two of them, the reminder and the warning, are mine and
   both push toward submitting.

2. **A fast-moving vendor API is now at the core.** Compaction, task budgets,
   fallback, operator messages mid-conversation and the rule against editing
   history are betas or recent changes. Stewart's custody promises are meant to
   last for years, while its auditor depends on an interface that changes month to
   month. Pinning the API version covers the stable parts; betas don't pin. A good
   share of maintenance effort will move from filesystem custody to keeping up with
   the provider.

3. **The auditor is much weaker as an investigator.** Agents do a lot of their best
   work by running things: tests, scripts, quick experiments. Read and search over
   text is a large narrowing. The attention hypothesis may well hold, but nothing
   yet shows that `read` answers are useful, and the old tension between an
   effective investigation and a clean, constrained one has been settled by default
   on the constrained side. The provider-hosted execution profile is the escape
   hatch, but it isn't designed.

4. **Every material goes to the model provider by design.** That was already true
   of anything an agent auditor read. Now Stewart is the party doing the sending,
   and the receipt's one-line notice is thin for sensitive material. There is no
   way to commission material the model may not see, and no record of which bytes
   left the machine beyond the access log.

## The mechanics

5. **The likeliest real failure is an honest, empty answer.** A model that writes
   its conclusions as prose and never calls `answer_add` returns nothing. One
   reminder may not fix that. Stewart is right not to author on the auditor's
   behalf, but this is exactly how a capable model behaves when it forgets its
   tools. It needs evidence from real runs before release, not just the fake API.

6. **"Destroys nothing" also means "keeps everything".** Commission copies, every old
   answer version and full conversations, which quote material freely, all pile up
   in the home indefinitely. Disposal becomes the manager's job with ordinary
   tools, and read-only files make `rm -r` noisy. Some material comes with an
   obligation to destroy copies after use. Stewart can't honor that, and its layout
   scatters copies of the material across several places.

7. **Verification can't see a careful change before the seal.** Hashes sit next to
   the payloads they protect. The only outside anchors are the receipt digest at
   commissioning and the manifest digest at sealing. In between, an agent-manager
   "repairing" storage consistently would go unnoticed. That fits the premise that
   participants are cooperative but fallible, but the integrity section shouldn't
   be read as promising more.

8. **The manager can read the auditor's work live.** Storage is plain files. Nothing
   stops a manager, or an eager agent-manager, from reading the conversation while
   the run is going. The earlier stance kept managers out of live material; the
   clean sheet keeps them from steering but quietly drops that.

9. **Losing Git loses provenance by default.** Unless the manager writes it down,
   the receipt can't say which commit the files came from. For questions about code
   at a particular version, that binding was the point. A provenance note is an
   open decision, but an optional, uninterpreted note is weak.

10. **Text and lines are assumed everywhere.** Large files, generated or minified
    content, non-UTF-8 encodings, binaries and line-less formats are untreated
    beyond "listed but not read".

11. **People as auditors don't fit the new world.** A person on the same machine can
    read storage, other audits and anything else, so "the auditor's world is its
    tool list" is false for them. Keeping them makes Stewart two products with one
    interface. Dropping them gives up a group earlier work treated as required.

12. **Stewart now spends money.** Every run costs tokens. An agent-manager can start
    runs freely, and nothing in Stewart limits that beyond each run's own limits.

## How the three views were made

13. **The clean sheet turns my inventions into the design.** It reads as settled on
    purpose, and anyone reading only STEWART.md will take its specifics as decided.
    Many of them came from me in one sitting, not from you:

    | From your decisions | From me, undecided |
    | --- | --- |
    | Auditor has only Stewart's tools | The ten `read` tools and their caps |
    | Stewart runs the auditor | The reminder and the 90% warning |
    | Linux only | The access log in the return |
    | No Python baseline | Directory expansion and the commission limits |
    | No Git; history exported as files | Destination naming and copy layout |
    | | The run lock and status liveness |
    | | Home location and refusing `/mnt/` on WSL |
    | | Verification as the integrity stance (still an open pitch) |
    | | Profiles as the form typing takes (still open) |
    | | Never deleting (followed from R2, never confirmed) |
    | | The fake-API acceptance standard |

    Commitments 3 and 4 in the clean sheet (nothing is destroyed; verify rather
    than wall off) are presented as principles, but you haven't adopted either.

14. **The API facts are second-hand.** What compaction preserves, how fallback
    behaves, task budgets, and the absence of forced tool choice come from a
    reference, not from running anything. The design leans on them.

15. **The views disagree in small ways.** The request format, destination naming and
    acceptance standard differ between DESIGN.md and STEWART.md. STEWART.md is the
    latest; the others are records of how we got there.

16. **The redesign moved faster than anything else in this project.** In one
    conversation it reversed choices made over the previous two days: custody tied
    to the repository, an auditor workspace, close that removes things, Python as
    the baseline, Git-based material. The stance invites that, and it's your call.
    Still, something valuable may have been dropped through silence rather than
    choice. Before adoption I'd want a fresh reader to check STEWART.md against
    CONTRACTS for exactly that: holds, Stewart's process promises to the auditor
    (raw capture before interpretation, a disposition of every gap, attribution
    never turned into a verdict), managers' independent workspaces, and the
    known-missing close details.

17. **Adoption would change most project guidance at once.** CLAUDE.md's custody rules,
    AGENTS, CONTRACTS and the development plan are written for the old design.
    CLAUDE.md is yours, and I won't edit it without your direction. Until it
    changes, every worker I dispatch inherits rules for a Stewart that would no
    longer exist.

18. **Dropping Python leaves a gap with no audit tool.** Nothing can run an audit
    between removing Python and the new binary working, including the project's own
    preparation audits and self-audits.
