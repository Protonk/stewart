# Coordinator notes

The steps 1–6 commission is complete (milestone run `.scratch/acceptance-02`,
recorded in TRANSITION-PLAN.md). No workers are active and no operation is
uncertain.

Agent worktrees from this round remain under `.claude/worktrees/` (branches
`worktree-agent-*`, all merged into main; each holds only an untracked
`service/vendor` symlink besides the merged history). They can be removed
with `git worktree remove` when convenient; nothing in them is unmerged.

Loopback listening was enabled by the user on 2026-10-30 for native
iteration. It is broader than tests need; every worker brief limited use to
listeners bound to 127.0.0.1 on port 0 and connections to ports the same test
opened. The user may turn it off; the container suite does not need it.
