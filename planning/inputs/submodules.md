# Candidate: custody of submodule code and work

The user has retained submodule support as a custody-addition candidate.
Reading pinned code and working in populated submodules are separate possible
responsibilities; either can be accepted, narrowed, deferred or declined.

At the planning reset, Stewart detects gitlinks and requires acknowledgment
before preparing a prompt commit that holds them. It does not populate or
audit their contents. Collection captures files its own walk finds below
gitlink paths and reports `gitlink_contents`; cleanup must account for those
bytes. See `src/stewart/prepare.py`, `src/stewart/collect.py` and
`tests/test_submodules.py` for the current implementation.

Questions for the addition inquiry:

- Which inquiries need only read access to the pinned submodule revision,
  and which need to execute checks or change files there?
- Where do objects come from, what authority permits obtaining them, and
  what happens when they are missing locally?
- How are the submodule repository, revision and any recursive submodules
  identified, retained and verified independently of the top-level repository?
- What may the auditor write, and how do collection, declarations, custody
  gaps and cleanup account for those changes?
- How can inspection avoid executing auditor-controlled repository
  configuration, and how are filesystem and harness boundaries qualified?
- What happens to sessions created before any support change?

Source: the former `SUBMODULES-PLAN.md` at `e95a80b`, condensed into a candidate
without its obsolete performance-plan dependency. No implementation approach
has been selected.
