# Coordinator notes

Steps 4–6 milestone in progress from the specification committed in `bad341f`.
Active workers and edit ownership:

- Foundation (post-launch record bodies, shared records, component
  interfaces as stubs, Appendix C names, the `2026-10-21` pin): `service/` in
  the main tree.
- Provider transport and the loop's pure parts: new files under
  `service/src/provider/` in its own worktree under `.claude/worktrees/`;
  merged after the foundation.
- Independent driver, stage A (fake provider, reacting auditor, run harness,
  case plan): `apparatus/` in the main tree; builds binaries only from
  committed revisions.

Loopback listening was enabled by the user on 2026-10-30, so the fake
provider runs natively; only the milestone container suite counts as evidence.
The setting is broader than tests need (it also allows listening on external
interfaces and connecting to any existing localhost service). Every worker
brief limits use to listeners bound explicitly to 127.0.0.1 on port 0 and
connections only to ports the same test opened; no other local service is
contacted.
