# Coordinator notes

Steps 4–6 milestone in progress. All implementation fixes from first
contact are on main at `2c927ab` (run loop: seal read from the log, refusal
delivery effect; close: closure and retained, and the exiting-run race;
retained rule in 1.3). Every service test passes in both configurations.

Active workers: driver authors 1 and 2, running all cases natively against
`2c927ab` (author 1 also extends `T.check_retained` to `runs/`, `payload/`
and the damaged log). Remaining after their reports: settle any last
disagreements, then the user runs `apparatus/acceptance.sh`.

Agent worktrees may be created at an old base commit; check and fast-forward
before work starts.

Loopback listening was enabled by the user on 2026-10-30, so the fake
provider runs natively; only the milestone container suite counts as evidence.
The setting is broader than tests need (it also allows listening on external
interfaces and connecting to any existing localhost service). Every worker
brief limits use to listeners bound explicitly to 127.0.0.1 on port 0 and
connections only to ports the same test opened; no other local service is
contacted.
