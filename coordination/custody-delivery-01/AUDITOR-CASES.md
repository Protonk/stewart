# Auditor submission-tool cases (discussion draft)

Discussion draft, 2026-10-28 UTC, from source `866a4c4`, prepared at the user's
request (“1. Yes.”) after they said “every wall carries a sign pointing at the
door” should be especially true of the auditor's submission tool, with pre-designed
cases giving the auditor quick, specific resolution. **Nothing here is agreed.**
Signs, reason identifiers and wording are proposals; rows marked open depend on
the questions at the end.

Produced by read-only workflow `wf_3f10a53c-1ac`: one finder derived cases from the
decided contracts and the prototype's refusals; another imagined what eager,
confused, bored or freshly compacted agent auditors will try; a merger combined
113 rows from 159 candidates. Full citations, test sketches (setup, action,
expectation, control) and the five dropped candidates are in
`.scratch/auditor-cases-01/RETURN.json`. The table assumes no particular enclosure;
the Linux work is a platform check, not auditor containment.

**How to read a row.** The situation is what the auditor was doing or believed.
*Tool says* gives the reason identifier (or none for success) and the gist of the
sign, including state shown. *Next* is the single most direct action. *Basis*
says whether the row rests on decided contracts, the prototype, a proposal or an
open question.

## What the table suggests, in the coordinator's reading

- Most walls already have doors in the decided design; the prototype's signs are
  the weak point. Its next steps are generic (“inspect the same store”), it names
  no holder when busy, and two of its walls have no door at all: damage to one
  selected payload blocks every operation, and a 10,000-record ceiling blocks even
  inspect.
- Three recurring agent instincts deserve first-class signs: re-adding everything
  after compaction (rows 76–77), editing the workspace file after adding it and
  expecting the change to travel (row 4), and treating a dry run as a submission
  (row 53).
- The first line of every reply could carry a fixed header (audit and question
  label, state, revision, usage, interrupted-operation count), so a confused or
  misbound agent sees where it is before reading anything else (rows 76, 98).
- Signs must never name custody paths; “absent rather than denied” applies to
  replies as well as the filesystem (row 93, question 5).

## Cases

### Getting started

**1.** A new auditor, or one back after context compaction, runs --help, 'help', the bare command, an unrecognised word or a plain-language question.

- Tool says: none. Read-only guide, the same for every form. It covers: the audit this tool is bound to (proposed); the operations add, replace, delete, inspect, read, prepare and submit; the ending sequence prepare, then submit <handle> (a dry run), then submit <handle> confirmed; 'files in your workspace are not returned unless you add them; add records a copy at that moment'; names are free labels; the optional account marker; 'there are no outcome, kind or status fields: state your outcome in the account'; each bound (256 elements, 64 MiB each, 256 MiB current, 1 GiB retained cap, 1 MiB threshold, 64 MiB reserve) as a limit of the custody undertaking; how to repeat an interrupted operation; and 'lost track? run inspect'. It shows no custody paths, manager operations or development hooks.
- Next: Run inspect.
- Basis: decided, prototype, proposed

**2.** Before making any edit, the auditor inspects the answer.

- Tool says: none. 'Answer: 0 elements, revision 0, editing open, account: none, nothing submitted', followed by the remaining allowances (proposed).
- Next: Add an element. An empty answer can also be prepared and submitted as it is.
- Basis: decided, prototype, proposed


### Adding material

**3.** The auditor adds a regular file. Afterwards the source is renamed, edited or deleted, and the helper process exits.

- Tool says: none. Reply: element id, version 1, handle, name, size, sha256, position, new revision and operation reference, plus 'Recorded a copy of <path>. Later edits to that file are not recorded unless you replace <handle>' (proposed wording). Earlier preparations are now stale.
- Next: Keep editing, or prepare when ready.
- Basis: decided, prototype

**4.** After adding answer.md, the agent keeps editing that file in its workspace, then prepares and submits expecting the edits to be included.

- Tool says: none. The manifest and dry run show the recorded size and digest. Proposed note, based on a stat of the recorded source that reads no content: 'source_changed: <handle> was recorded from <path>, which has changed since (2,314 -> 2,980 bytes). The recorded bytes will be submitted. To record the new content: replace <handle>.' If the source is gone, the note is source_missing.
- Next: Replace the element from the current file, then prepare again.
- Basis: decided, proposed, open

**5.** The auditor adds a 0-byte file, deliberately or by mistake.

- Tool says: none. An element of size 0 with the digest of empty input. Whether to add an 'empty file' note is open.
- Next: None. Replace it if the empty file was a mistake.
- Basis: decided, prototype

**6.** The auditor deliberately adds bytes identical to an existing element, for example the same log under a second label.

- Tool says: none. A new, distinct element and handle; equal content is never merged or treated as a retry. A duplicate_content note naming the other handle is proposed. It must match row 77's text, because the tool cannot tell a deliberate copy from an accidental one.
- Next: None.
- Basis: decided, prototype

**7.** Names reuse an earlier name, or contain '/', '../', absolute-path text or Unicode.

- Tool says: none. Each name is recorded as label text. Prepare and the dry run list every duplicate name with all the handles that share it, as information. The delivered copy uses generated file names plus an index.
- Next: Optionally delete a duplicate.
- Basis: decided, prototype

**8.** A name is empty, very long, contains a newline or control character, is not valid UTF-8, or is omitted.

- Tool says: Open. If refused: invalid_request (prototype) or invalid_name (proposed), naming the property and the bound; nothing recorded. The prototype refuses names over 512 bytes, admits empty names and control characters, and requires the name field.
- Next: Choose another label and repeat.
- Basis: decided, prototype, open

**9.** The agent supplies outcome, kind, status, completion or declaration fields (for example --kind answer, --complete or a JSON declaration), possibly primed by the frozen baseline.

- Tool says: invalid_request (unsupported_field proposed): 'Unknown option --kind; nothing recorded. Stewart records no outcome, kind, completion or role fields. State your outcome, including no supported finding, missing evidence or a reframe, in your account.'
- Next: Repeat without the field, and put the outcome in the account.
- Basis: decided, prototype


### Account marker

**10.** The auditor adds its readable account with the account marker.

- Tool says: none. Inspect and the manifest flag the element as the account, apart from the ordered artifacts. How the marker is supplied (for example a flag on add) is open; the prototype has no marker.
- Next: None.
- Basis: decided, prototype

**11.** The auditor revises the account by replace, or deletes it.

- Tool says: none. Replace keeps the marker, identity and place, with a new version and handle. Delete leaves 'account: none'.
- Next: None.
- Basis: decided

**12.** No element carries the marker. The auditor may be relying on a file named ACCOUNT.md or a label 'account'.

- Tool says: none. Inspect and the manifest state 'account: none' as a neutral fact; names never imply the marker. Whether prepare or the dry run add a no_account_marked note is open under the agnosticism principle.
- Next: None required. To mark the element, delete it and add it again with the marker.
- Basis: decided

**13.** The auditor adds a second element with the marker, for example re-adding its account after compaction.

- Tool says: account_exists (proposed), nothing recorded: 'H3 summary.md is already the account. To change its content, or to make another file the account, replace H3 with that file (replace keeps the marker).' Whether to refuse or move the marker is open.
- Next: Replace the existing account by its handle.
- Basis: proposed, constraint

**14.** The auditor tries to mark an existing artifact, unmark the account, or reorder or move artifacts.

- Tool says: invalid_request (unknown_operation proposed): 'There is no mark, unmark or reorder. The marker is set at add and kept by replace; artifacts keep their addition order, and replace keeps position. Delete the element and add it again from its file, with or without the marker; it then goes to the end.'
- Next: Delete the element, then add it again from its file.
- Basis: decided, proposed, open


### Source files

**15.** The source path is relative, contains '.' or '..', a literal '~' or a NUL, or the shell's cwd is not what the agent believes.

- Tool says: unsafe_path (the prototype requires an absolute path), or missing. Proposed: name the absolute path Stewart would have used and the actual cwd. Stewart never expands '~' and never searches for similar names. Whether relative paths resolve against cwd is open.
- Next: Repeat with the correct absolute path.
- Basis: prototype, open

**16.** The source sits under a symlinked ancestor: on macOS /tmp points to private/tmp, $TMPDIR lies under /var (which points to private/var), or a workspace directory is linked.

- Tool says: unsafe_path (link_in_path proposed), nothing recorded: '/tmp is a symbolic link (to private/tmp); Stewart does not follow links anywhere in a path. Use: add /private/tmp/answer.md.' The prototype gives raw OS text and a generic next step. Whether to accept root-owned system links is open.
- Next: Repeat with the suggested link-free path.
- Basis: decided, prototype, proposed

**17.** The source is itself a symlink, for example latest.log pointing to run-0423.log.

- Tool says: unsafe_path in the prototype (proposed: not_regular with found=symlink): '<path> is a symbolic link (to run-0423.log). Stewart does not follow links. Add the file itself.' The link text comes from readlink and is never followed.
- Next: Add the target file's own path.
- Basis: decided, prototype

**18.** The source is a directory, such as out/, the workspace or .git.

- Tool says: not_regular (detail found=directory proposed): 'Directories are not elements. Add each file (names may contain / to keep the layout), or add an archive you create; Stewart keeps it as opaque bytes.' The prototype gives the same message as for a FIFO.
- Next: Add the files one by one, or as one archive.
- Basis: decided, prototype

**19.** The agent runs add out/*.csv. The shell passes several paths, or the pattern arrives literally, or it matches nothing.

- Tool says: too_many_sources (proposed): 'add takes one file but got 7 paths (this looks like a shell glob); run add once per file.' A literal pattern gives missing with 'Stewart does not expand patterns'. Nothing is recorded. This depends on the CLI form, which is open.
- Next: Add each file with its own add.
- Basis: proposed

**20.** The source is a FIFO (including the /dev/fd/N path from <(...)), /dev/stdin, a socket or a device, or /dev/null used to get an empty element.

- Tool says: not_regular (detail found=fifo|device|socket proposed), returned promptly without blocking or reading: '/dev/fd/63 is a pipe; write the output to a regular file and add that.' For /dev/null: 'To record an empty element, add an empty regular file.' Where /dev/fd/N or /dev/stdin is a link, the reason may be unsafe_path, but the sign must still fit the case.
- Next: Write the content to a regular file and add it.
- Basis: decided, prototype, open

**21.** The agent pipes or heredocs content, for example echo text | add --name note.

- Tool says: Open whether bytes supplied on stdin are a source. If not: stdin_not_supported (proposed): 'add reads a regular file, not standard input; write the text to a file, then add it.' If yes, Stewart reads the input fully and within bounds before taking the lock.
- Next: Write the content to a file, then add it, unless stdin is adopted.
- Basis: open

**22.** The agent passes a URL, a git ref or a digest as the source, or as a 'reference' element.

- Tool says: unsafe_path or missing, because it is not an absolute regular-file path; Stewart makes no network or Git access. Proposed: 'Stewart does not fetch references; save the bytes to a file and add it. A URL in your account is just text.'
- Next: Save the content to a file, then add it.
- Basis: decided

**23.** The source path does not exist, or the file cannot be read because of permissions.

- Tool says: missing | unreadable, with the path and the cause; nothing recorded. Proposed addition: 'Stewart reads sources only with your own access.'
- Next: Correct the path or permissions and repeat.
- Basis: prototype

**24.** The agent adds a file from outside its supplied material (a home config, another audit's file), possibly one that only the tool's identity can read.

- Tool says: Stewart does not judge relevance: bytes the auditor can read are recorded as auditor-attributed bytes. If the tool holds authority the auditor lacks, it must not read beyond the auditor's own access; the mechanism is open. A file the auditor cannot read refuses unreadable.
- Next: None. If the add is refused, note the gap in the account.
- Basis: decided, open

**25.** The file changes while being read, for example a log or plot that a running job is still writing.

- Tool says: changed_during_read: 'run.log changed while being read (3.1 -> 3.4 MB); nothing recorded. Wait until whatever writes it has finished, then add it again.' In the prototype the source is read before binding, so the same reference stays usable. A 'recently modified' note on success is proposed.
- Next: Wait for the writer to finish, then repeat the same call.
- Basis: prototype

**26.** The size or SHA-256 the auditor declared does not match the source bytes.

- Tool says: source_mismatch, showing expected and observed size and digest; nothing recorded. This exists only if add takes a declared identity, which is open; the prototype requires one.
- Next: Re-supply consistent values, or omit them if Stewart computes identity itself.
- Basis: prototype, open


### Bounds

**27.** The auditor adds or replaces with a file over 64 MiB, such as a dataset, binary, archive or a 210 MiB log.

- Tool says: limit_exceeded, checked before copying: 'run.log is 210 MiB; each element may be at most 64 MiB. Remaining: 190 of 256 MiB, 251 of 256 elements. These bytes are not in Stewart's custody; existing preservation obligations toward them are unaffected. This refusal is recorded and will appear in the return's provenance.' The answer is unchanged.
- Next: Add an excerpt or compressed copy you make, or say in the account what was left out.
- Basis: decided, prototype

**28.** The 257th add arrives, for example when adding an output tree file by file.

- Tool says: limit_exceeded: 'The answer already has 256 elements (the limit); 0 remaining. Delete an element to free a slot, or add an archive you create (kept as opaque bytes).' The refusal is recorded as in row 27.
- Next: Delete elements, or combine files into an archive.
- Basis: decided, prototype

**29.** An add, or a replace with a larger file, would take the current selection above 256 MiB, for example after splitting a large file into chunks.

- Tool says: limit_exceeded, showing the current total, the bound and the remaining amount; the refusal is recorded. Deleting or shrinking elements does reduce the current selection.
- Next: Delete or replace elements to make room.
- Basis: decided, prototype

**30.** Edits land exactly at a bound: a 64 MiB element, the 256th element, a 256 MiB total.

- Tool says: none. Normal success, with the allowance now 0.
- Next: None.
- Basis: decided, prototype

**31.** Repeated large replacements bring retained replaced and deleted bytes to 1 GiB. The auditor then tries an edit over 1 MiB, or deletes elements hoping to free space.

- Tool says: limit_exceeded: 'Replacing data.parquet (48 MiB) would raise the bytes Stewart retains from replaced and deleted versions above 1 GiB (now 1,003 MiB). Edits up to 1 MiB still work (62 MiB reserve left). Deleting does not free retained space. prepare and submit are unaffected.' What the cap counts is open.
- Next: Prepare and submit, or make only small edits.
- Basis: decided

**32.** Small edits continue past the cap until the 64 MiB reserve is used up, for example an agent revising its account hundreds of times.

- Tool says: Replies and inspect show the remaining reserve (proposed). What happens at exhaustion is open; ANSWER-STRUCTURE says this design ensures 'the account can always be revised'.
- Next: Per decision.
- Basis: open

**33.** At or over the retained cap, with the reserve exhausted, the auditor deletes, prepares, dry-runs or confirms.

- Tool says: none. Normal replies; none of these refuses on the retained cap.
- Next: None.
- Basis: decided

**34.** An eager agent repeats an oversized add many times, under the same or new references.

- Tool says: limit_exceeded each time, with the answer unchanged. Open: whether every repeat records another observation, or a same-reference repeat returns the one recorded refusal (proposed: name the earlier observation).
- Next: Stop repeating, and record something else.
- Basis: open

**35.** After a refusal (oversize file, missing source, stale handle), the agent corrects the request and reuses the same operation reference.

- Tool says: Open. In the prototype, refusals before binding leave the reference unbound, so the corrected request proceeds. If recorded limit_exceeded observations bind their reference, reuse may refuse with request_conflict naming the recorded refusal.
- Next: Follow the reply; a new reference always works.
- Basis: prototype, open

**36.** A long audit, or an agent looping on prepares, edits or refusals, accumulates many custody records.

- Tool says: Open. Past 10,000 store entries the prototype refuses every operation with limit_exceeded, inspect included: a wall with no door. Proposed requirement: inspect, prepare and submit (and manager collect) stay available, or the refusal gives a specific door.
- Next: Per decision.
- Basis: decided, prototype, open

**37.** Control input or arguments are oversized: a huge name or reference, or a pasted manifest.

- Tool says: limit_exceeded (prototype) or invalid_request, naming the limit hit; nothing recorded. Whether this counts as a recorded custody observation is open; probably not.
- Next: Shorten the input.
- Basis: prototype


### Changing and reading

**38.** The auditor replaces an element's bytes using its current handle.

- Tool says: none. Same id, position and marker; version+1, a new handle and a new revision. 'The old handle is now stale; preparations issued before this edit are stale.' The superseded payload is held until close but not served.
- Next: Use the new handle for further edits.
- Basis: decided, prototype

**39.** The auditor replaces an element with identical bytes (only to rename it), or restores bytes it replaced earlier.

- Tool says: none. A new version and revision, with 'preparations issued before this edit are stale'. Equal digests never restore an old revision. Whether replace may change the name is open; the prototype requires a name on replace.
- Next: Prepare again before submitting.
- Basis: decided, prototype

**40.** The auditor deletes an element by its current handle.

- Tool says: none. The remaining membership and new revision, with: 'Deleted bytes are held until close but cannot be read back or restored; deleting does not free retained capacity.'
- Next: None.
- Basis: decided, prototype

**41.** The auditor reads an element back to check it, for example after compaction or for a 64 MiB element.

- Tool says: none. The verified exact held bytes, never the live source, with handle, name, size and digest. The delivery form is open: stdout with a JSON qualification on stderr (like the commission reader), a new destination file, or hex in JSON (the prototype's form, impractical at 64 MiB).
- Next: None. Compare the digest with the source if wanted.
- Basis: decided, prototype

**42.** The agent reads an element to a destination that already exists (such as its own workspace file), or reads a binary element to a terminal.

- Tool says: destination_exists, if destination files are adopted: 'Not written: /w/plot.png already exists; choose a new path.' The destination is created exclusively, without following links. A refusal to write binary output to a terminal is not among the refusal grounds; a note pointing to a destination file is the proposed alternative.
- Next: Read to a new path.
- Basis: decided, open

**43.** The auditor replaces, deletes or reads using an older version's handle.

- Tool says: stale_handle. Proposed: 'Not changed. That handle is version 1 of answer.md, replaced by version 2 (<handle>) in <ref>.' Never applied to the later version. The prototype says only 'no longer selected; inspect'.
- Next: Repeat with the current handle.
- Basis: prototype, open

**44.** A deleted element's handle is used again under a new reference, for example deleting twice.

- Tool says: stale_handle (element_deleted proposed): 'Element <id> was deleted at revision r by <ref>.' The prototype cannot tell deleted from superseded.
- Next: Inspect. Nothing more is needed if the delete was intended.
- Basis: prototype

**45.** The auditor wants an earlier version or a deleted element back, or tries undo, reset or clear.

- Tool says: stale_handle for an old handle (history_not_served proposed); invalid_request (unknown_operation proposed) for undo, reset or clear: 'Earlier and deleted versions are held until close but are not served, and there is no undo or reset. To restore content, add it again from a file; to clear the answer, delete elements one by one.'
- Next: Add or replace from its own copy of the file, or describe the loss in the account.
- Basis: decided, prototype

**46.** The agent passes a name where a handle belongs, for example replace answer.md.

- Tool says: invalid_handle (detail matches_names proposed): 'answer.md is a name, not a handle. Current elements with that name: H2 (v3, 2,314 bytes). To replace it: replace H2.' Every match is listed; none is chosen.
- Next: Repeat with the explicit handle.
- Basis: decided, prototype

**47.** The agent guesses an element handle ('1', 'e-1', an id without its version), truncates one, or uses one from another audit.

- Tool says: invalid_handle: 'No element in this audit has handle e-1. Handles are issued by this tool and listed by inspect.' Proposed: tell a malformed or truncated handle apart from a well-formed one not issued here. Never resolved by position or prefix; other audits are never revealed.
- Next: Run inspect and copy the handle.
- Basis: decided, prototype

**48.** Two replacements of the same element compete, from parallel tool calls or subagents.

- Tool says: One wins. The other gets busy or stale_handle, with the current handle (proposed). There is never a merged or partial state.
- Next: Inspect, then decide.
- Basis: prototype


### Preparing and submitting

**49.** The auditor prepares the current answer.

- Tool says: none. A manifest (audit, commission identity, revision, account, ordered elements) and an opaque handle bound to that revision, with the duplicate-name note if any, and: 'Nothing submitted; editing remains open. Next: submit <handle> (dry run), then submit <handle> confirmed.'
- Next: Dry-run submit with the handle.
- Basis: decided, prototype

**50.** The auditor prepares again, either after losing the handle or after every edit, treating prepare as 'save'.

- Tool says: none. A manifest and handle for the current revision, again stating that editing remains open and nothing was submitted. All handles issued for an unchanged revision remain valid. Whether prepare takes an operation reference, and how record growth is bounded, are open.
- Next: When ready, dry-run the newest handle.
- Basis: decided, prototype

**51.** Prepare runs while an edit is in flight, for example in a parallel tool call.

- Tool says: none, busy, or later stale_preparation. The manifest describes one coherent revision; if the edit commits afterwards, the handle is stale.
- Next: If refused, prepare again.
- Basis: prototype

**52.** The auditor prepares or dry-runs while one of its own operations is interrupted and unrecorded.

- Tool says: none. The manifest holds only recorded elements; the pending operation is neither a member nor discarded. Proposed note: 'op-17 (add run.log, 3 MB) was interrupted and is not part of this selection. Repeat that exact call to complete it. If you confirm, it can no longer complete.' Whether prepare or the dry run surface it is open.
- Next: Repeat the interrupted call, or proceed to confirm.
- Basis: prototype, proposed

**53.** The agent dry-runs (submit without confirmation, or submit=false), reads ok or 'would submit', and may report that it submitted and stop.

- Tool says: none. The first line reads 'DRY RUN - NOT SUBMITTED. Editing is still open.', followed by what would be submitted (count, revision, account, names, notes) and the exact confirming call. No custody bytes change. Success does not promise that a later confirm will succeed. The prototype reply is only {dry_run:true, would_submit:true, state}.
- Next: Confirm with the same handle.
- Basis: decided, prototype, proposed

**54.** The auditor confirms with a current handle. Afterwards it may poll inspect or look for proof that the manager received the answer.

- Tool says: none. 'Submitted. Editing has ended.', with the fixed result reference, revision and element count, then: 'Nothing further is required from you. Delivery and close are handled separately; Stewart does not report the manager's receipt to you.' There is no acceptance state to poll.
- Next: None. The auditor may end its session.
- Basis: decided, prototype, proposed

**55.** The auditor prepares and confirms an empty answer, having added nothing or deleted everything.

- Tool says: none. The dry run states 'this would submit an empty answer (0 elements)'; whether to include this neutral note is open under agnosticism. Submit replies 'Submitted an empty answer (0 elements).' The return is auditor-attributed and distinguishable from an empty manager collection.
- Next: None.
- Basis: decided, prototype

**56.** The account says 'see analysis.csv', but the auditor never added that file.

- Tool says: none. The manifest and dry run list exactly the members ('only these N elements will be returned'). Stewart does no matching between text and names.
- Next: Add the file if it should be returned.
- Basis: decided

**57.** After preparing, the auditor makes 'one last fix' (even one that restores equal bytes), then dry-runs or confirms with the old handle.

- Tool says: stale_preparation. Proposed: 'Not submitted; nothing changed. <h> was issued at revision 7; the answer is now at revision 8 (op-15 added H10 notes.md). Prepare again and review the new manifest.' Stewart never re-prepares or selects newer material silently. The prototype's message and next step are generic.
- Next: Prepare again, dry-run the new handle, then confirm.
- Basis: decided, prototype

**58.** Submit receives no handle, 'latest' or 'current', a manifest digest the agent computed, a pasted manifest, or a mistyped, truncated or foreign preparation handle.

- Tool says: invalid_handle: 'This handle was not issued by prepare for this audit.' A missing handle gives invalid_request (preparation_required proposed): 'Not submitted; nothing changed. submit needs the handle printed by prepare.' Stewart never prepares implicitly or selects by recency, and equal bytes in another audit do not help.
- Next: Run prepare and use the handle it prints.
- Basis: decided, prototype

**59.** The wrong kind of handle is used: an element handle given to submit, or a preparation handle given to replace, delete or read.

- Tool says: invalid_handle. Proposed: 'That is an element handle; submit takes the handle printed by prepare' (or the converse). The prototype says only 'not issued'.
- Next: For submit, use the handle from prepare. For edits, take the element handle from inspect.
- Basis: prototype, proposed

**60.** The confirmation is a near miss: submit="true", 1, "yes", or a misspelled flag.

- Tool says: invalid_request, showing the exact accepted confirmation spelling. Neither a dry run nor a submission happens. Whether a near miss should instead fall back to a dry run is open, together with the CLI spelling.
- Next: Repeat with the exact confirmation syntax.
- Basis: decided, prototype

**61.** The agent tries finalize, done, complete or finish.

- Tool says: invalid_request (unknown_operation proposed): 'There is no finalize. Run prepare, then submit <handle> (a dry run), then submit <handle> confirmed.'
- Next: Run prepare.
- Basis: decided, prototype, proposed


### Interruptions

**62.** The tool is killed (harness timeout, Ctrl-C, crash) before the operation's intent binding is published.

- Tool says: none, on the repeat. Nothing was recorded and leftover residue is not adoptable, so repeating the same call proceeds as a new operation under that reference.
- Next: Repeat the same call.
- Basis: prototype

**63.** An add is killed after its intent binding but before its payload is held; the source is unchanged.

- Tool says: none. The answer is unchanged until the repeat, which completes exactly the bound intent (proposed note: 'completed interrupted operation <ref>').
- Next: Repeat the same call.
- Basis: decided, prototype

**64.** An add was interrupted before its bytes were held, and the source has since changed or vanished.

- Tool says: source_mismatch | missing: 'Operation <ref> was interrupted before its bytes were held. Its source now differs or is missing, so it cannot complete. Nothing was added. To include the current content, add it as a new operation.' Stewart never adopts different bytes, or equal bytes found at an unplanned location. The prototype's next step offers resume or cancel instead.
- Next: Add the current file under a new reference.
- Basis: prototype, proposed

**65.** An add is killed after its payload was held (at after_stage or before_publish).

- Tool says: none. The repeat completes from Stewart's own planned bytes, without needing the source, giving exactly one element.
- Next: Repeat the same call.
- Basis: prototype

**66.** An add is killed after publication or sync, or it completed but the reply was lost (stdout lost, harness crash, compaction).

- Tool says: none. The repeat returns the recorded outcome without rereading the source and creates no duplicate. Proposed: show the recorded digest, mark the reply 'recorded earlier', and say when the returned state is historical because the answer has changed since.
- Next: Repeat the same call, or inspect.
- Basis: decided, prototype

**67.** A call timed out with no reply, and the agent's next call is a different command rather than a repeat.

- Tool says: Proposed notice on the next reply (the route is open). Recorded: 'op-17 (add run.log from /w/run.log) was interrupted. It WAS recorded as H8; the reply may not have reached you. Nothing to redo.' Not recorded: 'op-17 was NOT recorded; nothing from it is in your answer. To complete it: <exact call>.' Still running: busy, naming it. Unverifiable: integrity_error, without inferring absence.
- Next: Follow the notice: continue, run the printed call once, wait, or leave storage alone.
- Basis: decided, prototype, proposed

**68.** The agent reuses an operation reference with a different file, name or handle: a counter reset after compaction, the example key copied into every add, or an edit before retrying.

- Tool says: request_conflict, before the source is touched: 'Reference <ref> is already bound to add notes.md (H4, size, digest). Repeat exactly that call to see its outcome, or use a new reference for new intent.' The prototype message omits the bound intent.
- Next: Use a new reference.
- Basis: prototype, open

**69.** An add was interrupted; the auditor then made other edits, and now repeats the interrupted add.

- Tool says: Open. The prototype refuses with stale_request ('cancel this request'); the contracts complete the operation when its material, revision and authority permit. If refused, operation_superseded (proposed): 'Operation <ref> was never recorded and can no longer complete, because the answer changed after it was interrupted (r -> r'). Add the content again as a new operation.' Never a double add.
- Next: Add the content again under a new reference.
- Basis: prototype

**70.** A replace or delete was interrupted, and another operation changed the target element before the auditor repeats it.

- Tool says: stale_request (prototype), or operation_superseded or stale_handle (proposed): 'Operation <ref> was not recorded; element <id> has changed since (now <handle>).' It is never applied to the newer version.
- Next: Inspect and decide on a new edit.
- Basis: prototype

**71.** A confirmed submit was killed before publication, and nothing has changed since.

- Tool says: none. The answer is not yet submitted; repeating the same confirmed call completes it, because the handle is the identity.
- Next: Repeat the same confirmed call.
- Basis: decided, prototype

**72.** A confirmed submit was killed before publication. Believing it failed, the auditor edited, then repeated the confirm.

- Tool says: stale_preparation (proposed mapping of the prototype's stale_request): 'Submission <h> was never recorded, and the answer has changed since; prepare again.'
- Next: Prepare again, dry-run, then confirm.
- Basis: decided, prototype

**73.** The auditor repeats an identical confirmed submit: after a lost reply, after a kill that followed publication, or 'to be sure'.

- Tool says: none. The same recorded outcome: 'Already submitted with <h> at revision 7 (5 elements). This is that same submission; nothing changed. Nothing further is required from you.' No second submission is created.
- Next: None.
- Basis: decided, prototype

**74.** The agent tries resolve, resume or cancel (from prototype documents, or by guessing) to recover an interrupted operation.

- Tool says: invalid_request (unknown_operation proposed): 'Not an operation. To recover an interrupted operation, repeat the original call with the same reference; inspect shows the answer.' Whether the operation is pending, committed, superseded or unrecoverable must appear in the reply to that repeat.
- Next: Repeat the original call.
- Basis: see citation

**75.** A custody write fails mid-operation (disk full, I/O error), or a sync fails after publication.

- Tool says: storage_error (proposed; the prototype reports unreadable or io_error, with effect partial or uncertain): 'Stewart storage error (not caused by your input). Answer unchanged' or 'answer may have changed', then 'repeat this same call later'. Stewart never claims a definite no-change when effects may have occurred, and partial work is retained.
- Next: Repeat the same call later.
- Basis: prototype


### After compaction

**76.** After compaction the agent no longer knows what it recorded, its handles, whether it prepared or submitted, or which operations were interrupted.

- Tool says: none. inspect (a 'status' alias is proposed) shows: the audit and a question label (proposed); the state (open, submitted at T with <h>, or collected by the manager at T); the revision; the ordered elements with handle, name, size, digest, account marker and recorded-from path; usage against the bounds; each interrupted operation with its exact next call (route open); and duplicate-name notes. Preparations are not shown as a state.
- Next: Inspect, then read the account to recover what it wrote.
- Basis: decided, prototype, open

**77.** Unsure whether earlier adds happened, the agent adds the same files again under new references, possibly re-adding everything including the account.

- Tool says: none. Each re-add is a new element: Stewart cannot tell it from a deliberate equal-byte add (row 6) and does not deduplicate. Proposed reply note: 'Recorded H9 answer.md. H2 has the same name and identical bytes. If this was a repeat, delete H9; to update H2, replace H2. Tip: run inspect before adding after a break.' Prepare and the dry run list duplicate names (decided). A marked re-add of the account meets row 13.
- Next: Delete the unwanted duplicates, and inspect before adding anything more.
- Basis: decided, proposed


### Submitted, collected or ended

**78.** After submitting, the auditor tries to fix a typo or add a forgotten file (add, replace, delete), perhaps escalating.

- Tool says: already_submitted: 'Not recorded. This answer was submitted at T (<h>, revision 7) and is fixed. There is no reopening and no further channel for this audit. Repeating, preparing again or changing files in Stewart's storage will not alter it. Nothing further is required from you.' The attempted bytes are not taken into custody.
- Next: Stop authoring.
- Basis: decided, prototype

**79.** After submitting, the auditor prepares again, or confirms a second handle (prepared twice for the same revision, or obtained after compaction).

- Tool says: already_submitted: 'Not submitted again. This answer was already submitted with <h> at revision r; nothing changed.' At most one submission exists.
- Next: None. The answer is already submitted.
- Basis: prototype

**80.** A confirmed submit races an edit, from parallel tool calls or a subagent.

- Tool says: Exactly one takes effect. The loser gets stale_preparation or already_submitted, possibly busy first.
- Next: Follow the loser's refusal.
- Basis: decided, prototype

**81.** After submitting, the auditor repeats an operation that was interrupted before the submission.

- Tool says: already_submitted (proposed mapping of the prototype's stale_request): 'Operation <ref> was never recorded; editing ended when <h> was submitted.' Its records remain.
- Next: None.
- Basis: prototype

**82.** The manager collected while the auditor kept working. The auditor's next add, replace, delete, prepare, or confirm with an earlier handle arrives.

- Tool says: already_collected (proposed): 'Not recorded. The manager collected this answer at T (revision 6, 4 elements; manager-collected, not auditor-submitted), and authoring has ended. Your op-14 is included; this <edit|submission> is not. Nothing further can be added.'
- Next: Stop. Nothing more is needed through this tool.
- Basis: decided, proposed

**83.** The auditor confirms while the manager collects, and the submit is serialized first.

- Tool says: none. Normal submit success, or the recorded outcome on a repeat. Collect cannot replace it.
- Next: None.
- Basis: decided

**84.** Submit and collect race and the collect wins. The auditor's reply arrives after the collect, or is lost and the auditor repeats.

- Tool says: already_collected (proposed): 'Your submission <h> was not recorded: the manager collected revision 6 first.' Proposed addition: 'Your prepared revision 6 is identical to what was collected.' A repeat gives the same refusal.
- Next: None.
- Basis: decided, proposed

**85.** The auditor's add was interrupted (bound but unpublished), the manager collected, and the auditor then repeats the add.

- Tool says: already_collected (proposed): 'Operation <ref> was never recorded; the manager collected the answer before it completed.' The collect neither promoted nor discarded it, and its records remain.
- Next: None.
- Basis: see citation

**86.** The auditor's add committed but the reply was lost; the manager then collected, and the auditor repeats the add.

- Tool says: none. The recorded outcome; the element appears in the collected return exactly once. Proposed note: 'recorded earlier; the answer has since been collected by the manager at revision r'.
- Next: None.
- Basis: decided, prototype, proposed

**87.** After submitting, or after a manager collect, the auditor inspects or reads its answer.

- Tool says: none (proposed). Read-only verified access with attribution: 'Fixed: submitted by auditor' or 'Fixed: collected by manager', with revision and elements. The prototype allows inspect and read after submit; reading after collect is not decided.
- Next: None.
- Basis: prototype, proposed, open

**88.** The manager's collect is interrupted after binding its intent but before publication, and the auditor keeps editing.

- Tool says: Open. Either already_collected, if authoring ends when the collect binds, or a normal edit that the continued collect consistently excludes and reports.
- Next: Per decision.
- Basis: prototype, open

**89.** The auditor, a leftover process, or a session resumed days later calls the tool after the audit was closed.

- Tool says: Open. audit_closed (proposed): 'This audit is closed; nothing can be recorded or read here. Nothing further is required from you.' Stewart never falls back to another audit and never writes or recreates records.
- Next: Stop.
- Basis: open

**90.** The agent writes REPORT.md in its workspace and stops without ever recording it, perhaps primed by baseline guidance to write the report in the checkout.

- Tool says: Nothing at the time, because the tool is never called. The sign has to come first, in help and successor guidance: 'Files in your workspace are not returned unless you add them.' A manager collect then gives an honest empty, manager-collected return.
- Next: Add REPORT.md, if the auditor reads help; otherwise the manager collects.
- Basis: decided, proposed


### Things outside the tool

**91.** The agent tries manager or setup operations: collect, close, deliver, list audits, or init --store /tmp/x 'to start fresh'.

- Tool says: invalid_request (unknown_operation proposed): '<verb> is not an auditor operation. This tool is already bound to audit A and takes no store or audit argument. You finish with prepare, then submit <handle> confirmed; collect and close belong to the manager.' Nothing is created.
- Next: Use prepare and submit.
- Basis: decided, prototype, proposed

**92.** The agent asks the tool for more material, or for files it was not given.

- Tool says: invalid_request (unknown_operation proposed): 'Stewart cannot supply more material during an audit and fetches nothing. If something you need is missing, say what and why in your account; that is a permitted answer.'
- Next: Write the gap into the account.
- Basis: decided

**93.** The agent searches the filesystem for where Stewart keeps the answer (find, ls, grep for digests), to check or edit it.

- Tool says: Proposed text in help and the add reply: 'Your recorded answer is held in Stewart's storage, not your workspace. You never need to find it; inspect and read show exactly what is recorded.' Auditor-facing replies name no custody paths. Custody is absent from the auditor's world where an arrangement allows that; where it is reachable, a plain note at its root points back to the tool (proposed).
- Next: Run inspect.
- Basis: decided, proposed

**94.** Malformed control input: an unknown field, a repeated or escape-equivalent key, invalid or trailing JSON, a wrong field type, or an unknown operation.

- Tool says: invalid_request | duplicate_key | invalid_json, naming the field or key at fault; for an unknown operation, the list of operations. Nothing recorded.
- Next: Correct the input (see help).
- Basis: prototype

**95.** The operation reference is empty, too long, or contains control characters. This applies only if auditors supply references.

- Tool says: invalid_request, stating the reference rules; nothing recorded.
- Next: Use a valid reference.
- Basis: prototype, open

**96.** The tool runs without its audit binding: a new shell, env -i, a subagent, a scheduled job, or a copied command.

- Tool says: audit_not_bound (proposed; the prototype's analog is not_initialized or invalid_arguments): 'This tool is not bound to an audit here. Use the exact command from your instructions; Stewart will not guess an audit.' Other audits and custody paths are not listed; nothing is written.
- Next: Repeat the command exactly as given in the instructions.
- Basis: prototype, open

**97.** The binding names an audit this tool cannot reach: a typo, an earlier audit, or another auditor's audit.

- Tool says: unknown_audit (proposed): 'No audit with this reference is available to this tool.' Nothing about other audits is disclosed.
- Next: Use the binding provided in the instructions.
- Basis: proposed

**98.** Another audit's binding leaks into the agent's shell (a shared profile, a command line copied from another session, two audits on one machine), so it records into the wrong audit.

- Tool says: none. Proposed: the first line of every reply names the bound audit and a short question label, for example 'Audit A, Does parser X preserve keys? - OPEN, revision 4', so a mismatch is visible at once.
- Next: If the question is not its own, stop and use the command from its own instructions.
- Basis: proposed

**99.** A different Stewart build reaches the audit: through PATH, by the agent rebuilding the tool, or because the installation behind the instructed command changed mid-audit.

- Tool says: writer_mismatch: 'Not recorded. This audit was written by Stewart build <A>; this program is build <B>. Use the tool command given in your instructions; if that is the command you ran, stop: your recorded answer is intact, this is not yours to fix, and the manager can collect.' inspect, read and the dry run stay available. Stewart never relays to or executes the recorded binary.
- Next: Repeat with the instructed command. If that is what failed, stop editing.
- Basis: prototype, open

**100.** The agent makes parallel calls: several adds at once, an add backgrounded with &, or subagents using the tool alongside it.

- Tool says: busy (the prototype's next step mentions a 'bundle'). Proposed: 'Busy: op-21 (add b.csv) is running. This command changed nothing; repeat it.' Elements land in commit order. Whether to refuse or wait briefly, and whether reads need the lock, are open.
- Next: Repeat the same call. Add sequentially if order matters.
- Basis: decided, prototype

**101.** An earlier tool process is suspended (Ctrl-Z, SIGSTOP, a hung read) and holds the lock indefinitely.

- Tool says: busy. In the prototype this lasts indefinitely and names no holder. The door is open; proposed: name the holding operation's reference and state that nothing changed.
- Next: Per decision.
- Basis: prototype, open

**102.** The auditor runs the tool from an unrelated or nested directory, or repeats an interrupted operation from another shell.

- Tool says: none. The same audit and the same results; a repeat under the same reference resolves the same operation, whatever the process or cwd.
- Next: None.
- Basis: see citation

**103.** The tool cannot write custody from the auditor's environment (permission denied, read-only mount). An eager agent may retry with elevated permissions or outside its sandbox.

- Tool says: custody_unavailable (proposed), with a definite effect line: 'Not recorded. Stewart could not write its storage from this environment (permission denied). This is a setup problem, not something to work around: do not rerun with elevated permissions or outside your sandbox. Your recorded elements are unaffected. If this persists, stop; the manager can collect what is recorded.'
- Next: Stop retrying.
- Basis: proposed, unsettled

**104.** The same situations occur on Linux. The Linux work checks that Stewart itself runs there; it is not an auditor enclosure. Known differences: /tmp is usually a real directory, /dev/fd/N is a link, and flock and non-UTF-8 names may behave differently.

- Tool says: Per row: the same reason id and next step as on macOS. Results differ only where the filesystem fact differs, and the difference is stated.
- Next: Per row.
- Basis: prototype, proposed


### Damage

**105.** A currently selected element's held bytes are corrupted or missing (storage fault, or a shell touched custody). The agent may try to fix it by re-adding or by restoring files.

- Tool says: integrity_error. Proposed: 'Stewart cannot verify the held bytes of H4 data.csv (expected digest D). This is damage to Stewart's records, not yours to repair; editing Stewart's storage will not fix it. Your other 3 elements verify. The manager will see this and can collect what verifies.' Bytes are never repaired from the live source. Prepare and submit of a selection containing the element refuse. The prototype blocks every operation (a whole-answer wall); the scope is open.
- Next: Leave storage alone. Continue unaffected work, or stop.
- Basis: prototype

**106.** A committed membership record is damaged, or an acknowledged publication is missing.

- Tool says: integrity_error: 'Stewart cannot establish your recorded answer. This is not yours to repair; do not recreate records. No further edits are possible through this tool; the manager can collect or close.' An earlier state is never presented as current, and acknowledged operations are never treated as pending.
- Next: Stop.
- Basis: prototype

**107.** An unrelated historical attempt record is malformed.

- Tool says: none. Ordinary operations continue; the auditor sees no sign.
- Next: None.
- Basis: prototype

**108.** The records of the auditor's own interrupted operation are damaged, and the auditor repeats that operation.

- Tool says: integrity_error: 'Operation <ref> cannot be verified, and it is not part of your recorded answer. This is not yours to repair. To include the content, add it under a new reference.' The operation is treated neither as pending nor as absent; other operations continue.
- Next: Add the content under a new reference.
- Basis: prototype, proposed

**109.** Before submission, the preparation record behind the handle being submitted is damaged or missing, while the selected bytes are intact.

- Tool says: integrity_error. Proposed: 'Preparation <h> cannot be verified; nothing was submitted, and your answer is intact. Prepare again for a new handle.' Inspect, read and edits continue. A missing acknowledged issuance never becomes a pending issuance to recreate. The prototype's next step says only to preserve the records.
- Next: Prepare again and submit the new handle.
- Basis: prototype

**110.** After submission, the preparation record behind the submitted result is damaged.

- Tool says: integrity_error: 'Your submission is recorded, but its preparation record cannot be verified; there is nothing for you to repair.' Claims about the final state refuse. The submission is neither undone nor redone, and a repeated confirm creates no second submission.
- Next: None.
- Basis: prototype

**111.** A superseded or deleted payload, held until close, is damaged.

- Tool says: none. It is not a dependency of the current answer, so auditor operations continue; the damage remains for the manager and for close.
- Next: None.
- Basis: prototype

**112.** A curious or eager auditor uses its shell to edit, plant or delete custody records or payloads: fixing a typo after submitting, deleting a 'stale lock' after busy, or tidying.

- Tool says: integrity_error: 'Stewart's records for this audit fail verification (<what>). This command changed nothing. Do not modify, restore or delete files in Stewart's storage: changes there are detected, not accepted, and are not yours to fix. The manager will see this in status.' Relevant changes are detected and the affected claims refused; unrelated planted names are ignored; nothing is rewritten. There is no lock file to delete: the prototype locks a descriptor. Detection must not depend on containment.
- Next: Leave storage alone.
- Basis: prototype

**113.** Custody is missing, moved or destroyed: the repository moved or was restored from backup, custody moved mid-operation, or cleanup run from the workspace reached it (git clean -fdx, rm -rf $TMPDIR/*, git worktree prune).

- Tool says: custody_unavailable (proposed; the prototype gives bundle_moved_during_operation for a move mid-operation): 'Stewart cannot find this audit's records. Your recorded answer cannot be read or changed here, and you cannot restore it. Nothing further can be recorded; stop. The manager will see this in status.' Stewart never reports an empty answer and never guesses another store. Open: placing custody where workspace cleanup cannot reach it, and move and backup behavior.
- Next: Stop.
- Basis: prototype, open

## Open questions, triaged by the coordinator

Numbers refer to the merger's 36 questions (full text in the scratch return).
The triage is the coordinator's proposal; it decides nothing.

### For the user: these touch what participants can express or what Stewart promises

- **Q1. Make the signs acceptance criteria.** Should each reason's sign and next
  step become an acceptance case, and should “absent rather than denied” and
  “every wall carries a sign” be written down as principles? Today the nearest
  decided text is “informative failures from which the auditor can recover”.
- **Q5. No custody paths in auditor-facing replies.** The project convention says
  refusals carry retained paths; “absent rather than denied” says the auditor
  should never be shown where custody lives. Proposed: auditor replies use
  audit-relative identifiers only; custody paths stay in the manager's status.
- **Q10. Submitting with an unresolved operation of one's own.** Proceed with a
  note in the dry run and a record in provenance, or refuse until it is resolved?
  Lean: proceed with the note; refusal would wall off submission.
- **Q20. Scope of damage while authoring.** The prototype blocks every operation
  when one selected payload fails verification. Lean: block only claims that
  depend on it (inspect shows the gap; replace or delete of that element works;
  prepare and submit refuse while it is selected).
- **Q26. Informational notes and author pressure.** Notes such as “no account
  marked”, “empty selection” or “duplicate content” help a confused agent but
  could nudge authors toward a shape. Which are neutral facts, and which need
  deliberation under the agnosticism principle?
- **Q32. “Stop” as the final door.** After submission, collection, closure or
  unrepairable damage, the auditor has no channel for a further note. Confirm.
- **Q33. Pointing a compacted auditor back to its question.** Should help or
  inspect remind the auditor of its question and supplied materials, not only its
  recorded answer? This bears on acclimating an agent to the role.

### For the access-route document (item 1)

Q14 (a tool with authority the auditor lacks must not read on its behalf beyond
the auditor's own access), Q27 (how the tool is bound to its audit across
subshells and subagents without picking up another audit's binding), Q28 (manager
operations reachable from an unenclosed auditor shell), Q29 (writer pinning seen
from the auditor), Q30 (custody location, moves, and reach of workspace cleanup),
Q31 (whether “continuing participant” is enforced or policy).

### Mechanical, for the coordinator within the commission (with current leans)

- Q2 check every proposed refusal against the contract's refusal grounds;
  Q3 choose reason identifiers; Q4 give each reason its own next step, an explicit
  effect line (changed, unchanged, unknown) and the fixed header.
- Q6 operation references assigned by the integration and shown in every reply,
  rather than invented by agents (copied example keys and resets after compaction
  favour assignment); Q7 interrupted operations shown both as a notice on the next
  reply and in inspect; Q8 an interrupted add may complete onto a newer revision,
  since its intent is not tied to one; Q9 a definite “not recorded” reply on repeat
  suffices, with a new add as the door.
- Q11 Stewart computes identity rather than requiring declared size and digest;
  Q12 relative paths resolve through the caller's directory descriptor, and
  root-owned system links (macOS `/tmp`, `/var`) are accepted because no auditor
  can plant them; Q13 regular files only in the first leg, with a sign for piped
  input; Q16 name rules (length bound, no control characters, UTF-8).
- Q15 account marker set by a flag on add; a second marked add refuses with a sign
  pointing to replace; replace may change bytes and name but not the marker.
- Q17 retained-cap accounting and reserve exhaustion, keeping the promise that the
  account can always be revised; Q18 bounded refusal records; Q19 inspect,
  prepare, submit and collect stay available at any record-count bound.
- Q21 a bound collect ends edits; Q22 after collection the auditor sees
  attribution and the fixed selection (close behavior belongs to the close leg);
  Q23 busy waits briefly before refusing and names the holder; Q24 reads go to an
  exclusively created destination file; Q25 replayed outcomes say they are
  historical when the answer has moved on; Q34 no atomic multi-file add in the
  first leg; Q35 a near-miss confirmation refuses with the exact syntax rather
  than falling back to a dry run, and `status` is accepted as an alias of inspect;
  Q36 reason identifiers are platform-neutral, with the filesystem fact in detail.
