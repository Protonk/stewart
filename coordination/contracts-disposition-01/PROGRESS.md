# Progress: contracts-disposition-01

Reviewer: fresh-eyes worker (not party to the 2026-10-28 conversation).

## Checkpoint 1 — 2026-10-28T18:25-0700

- Working tree: `main`, HEAD `5bebe98` (adds only this brief); `CONTRACTS.md`
  verified byte-identical to `7e49301` via `git diff --quiet 7e49301 5bebe98 -- CONTRACTS.md`.
  Line numbers in RETURN.md therefore read the same at `7e49301`.
- Tree otherwise clean. No Git state changes, no network, no Claude launches.
- Sizes: CONTRACTS.md 1777 lines; ROUTER.md 397; END-TO-END.md 343;
  RESERVATIONS.md 142; AGENTS.md 237; CONVERSATION.md 1620 (consult only if a
  decision's reason is unclear).

### Plan

1. Extract the heading skeleton (`##`, `###`) and the bold paragraph titles in
   Principles, the three successor sections and Close, with line numbers.
2. Read CONTRACTS.md in full in ~400-line parts; record a disposition and
   reason per row as I go (scratch table kept in this file's companion notes).
3. Read ROUTER.md and END-TO-END.md (coordinator proposals unless CONTRACTS
   records the decision), RESERVATIONS.md items 13 and 16, AGENTS.md.
4. Write RETURN.md: Table, Would-be-lost-silently (holds; process promises to
   the auditor; managers' independent workspaces; close details; export and
   evidence packages; evidence interpretation across implementations; writer
   continuity and runtime handoff; request keys; legacy Python records),
   Contradictions, Counts.
5. Reconcile table row count against the skeleton count; final checkpoint.

## Checkpoint 2 — 2026-10-28T18:40-0700

- CONTRACTS.md read in full (lines 1–1777) with line numbers.
- Skeleton found: 25 `##` headings, 2 `###` headings; bold titles: Principles 12
  (65, 71, 89, 101, 126, 131, 143, 160, 178, 208, 219, 234); "Successor answer
  construction" 5 (325, 339, 364, 390, 420); "Successor manager receipt" 6 (458,
  468, 476, 499, 516, 544); "Successor interfaces decided 2026-10-28" 7 (569,
  583, 591, 600, 614, 631, 643); Close 18 (1117, 1137, 1160, 1178, 1197, 1216,
  1229, 1245, 1255, 1262, 1274, 1280, 1285, 1299, 1316, 1326, 1333, 1338).
  Required rows = 75. "First successor leg" (246) has no bold paragraph titles.
- Extra rows planned (beyond the brief's required set, reported separately in
  Counts): preamble (1–33), `####` sub-headings of Public contract (778, 843,
  899, 927, 957), Public-status bold titles (1094, 1103), Return-arrangements
  bold titles (1428, 1435, 1439, 1445, 1453, 1457), Program-execution bold
  titles (1513, 1521), Declined bullets (13, lines 1707–1769). Untitled
  superseded paragraph at 435–443 is covered inside row 420.
- Next: ROUTER.md, END-TO-END.md, RESERVATIONS.md, AGENTS.md; then draft table.

## Checkpoint 3 — 2026-10-28T18:55-0700

- Read ROUTER.md (397), END-TO-END.md (343), RESERVATIONS.md (142, items 13
  and 16 noted), AGENTS.md (237) in full.
- Draft dispositions assigned for all 75 required rows plus planned extras;
  candidate contradictions noted: (a) "return is the submission" (631) vs
  limit refusals "listed in the return's provenance" (413–414); (b) "manager
  access to live material very restricted" (661–669) vs record "readable by
  whoever runs Stewart" (635–636) and ROUTER 244–245; (c) "the auditor is not
  shown the question type" (442–443) vs the form as the auditor's tool (569)
  and ROUTER's coupling frame/slots; (d) ROUTER `answer/` rendered by the
  coupling (300) vs END-TO-END C5 "manifest and elements and nothing else";
  (e) ROUTER "Stewart deletes nothing" (361) is a proposal while several
  decided paragraphs still speak of disposal at close (494, 513).
- Consulting CONVERSATION.md only for the user's words on deletion, live
  readability and the question type. Then write RETURN.md.

## Checkpoint 4 (final) — 2026-10-28T19:25-0700

- Consulted CONVERSATION.md turns 4–6, 12, 17–18, 22–23 for the user's words on
  deletion (R3 never adopted; RESERVATIONS 13 confirms), live readability
  (turn 12 #5 "I don't care ... free to inspect reasoning summaries") and the
  question-type sentence (turn 6 cites it as a standing decision).
- RETURN.md written with sections 1–4. Table: 105 rows (75 required + 30 extra,
  reconciled in §4). Tallies verified by grep after writing: Carry 32/25,
  Restate 31/23, Retire 35/21, Undecided 7/6 (all/required); the Counts table
  was corrected from an earlier running count that was wrong.
- §2 covers the nine items the brief requires plus six more (commission-copy
  custodian, status liveness, live access, the R6/R7/R8 decisions not being in
  CONTRACTS, file modes, deliberation of nudges). §3 lists nine contradictions
  and two minor wording items.
- No Git state changed; nothing written outside this directory; no network; no
  Claude launches.
