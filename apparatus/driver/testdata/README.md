# Driver test data

## `messages/`: captured provider responses

[`messages/m4-summary.json`](messages/m4-summary.json) is the exact HTTP response
body from the 2026-11-15 M4 encounter, model `claude-opus-5-5`, effort omitted.
This is Stewart-owned capture, not an independent live wire witness.

| Origin | Bytes | SHA-256 |
| --- | --- | --- |
| `.scratch/readiness-m4-live-01/container/m4/export-0001/work.tar` | 5027840 | `c22abed412f2f7122c30fd03bc3d492976a81ea1823eaaee52f5920d41f2d2aa` |
| Member `private/archive/audits/alln5scv7txvccchz/runs/1/response-5-1.bin` | 5779 | `87d8c3ec491c8ee5b91a344472207a59effbae9964c09c0314ac433f01d77820` |
| Its complete `content` array, including signature | 5092 | `c513090fa4b59dba5a7a0b523b0e73a0260d9fefdc23d44e056d6603ed0c70a1` |

The [captured compaction case](../cases_compaction.py) serves that body unchanged
after a synthetic trigger. It checks exact signed-content reuse, context reset,
retained captures, one placement and preservation of a supplied account through
re-entry, read, exact-version replacement and auditor submission. It compares
both retained payload versions and the delivered `answer.json` with independent
expected bytes. Package-wide verification and close have separate cases. The scripted
auditor does not interpret the captured summary as instructions or as an account
of its synthetic question. This tests opaque custody and accounting, not the
summary's meaning, cryptographic validity or real-model behavior.

The original has zero top-level usage and one compaction iteration reporting
344449 input and 1212 output tokens. One variant changes only top-level
`usage.input_tokens` from 0 to 7: the charge and answer must stay the same.
Another changes only the iteration's `output_tokens` from 1212 to 1213: the
output charge must increase by one, with input, turns and answer unchanged.
Mutations replace the selected numeric span; every other byte stays unchanged.
Existing sabotage controls must detect omitted compaction, changed signed bytes,
retained old context and ignored iteration usage. The fake provider retains its
own transmitted response and received request bytes outside Stewart's archive.
Fixture self-tests pin the original bytes, exact changed fields and literal
expected charges. No test reads the retained study directory or invokes a model.

### M2/M3 cap and replacement forms

These originals come from `claude-haiku-5-5`, effort omitted, on 2026-11-13
(M2) and 2026-11-15 (M3). Their shared retained export is
`.scratch/readiness-m2-live-sw3z-default-01/container/m2-sw3z-default/export-0009/work.tar`:
4608000 bytes, SHA-256
`1c30749b8ea004762c1abebeab3674fc9a97cc6c65e2772e5a143c76a9bb757b`.
Member paths below are relative to `private/archive/audits/arlu5pv4dlxmku2na/`.
These are service-owned captures, including the notice record; the synthetic
fake provider supplies a separate witness of transmitted and received bytes.

| Fixture | Original member | Bytes | SHA-256 |
| --- | --- | --- | --- |
| [M2 cap](messages/m2-cap.json) | `runs/1/response-9-1.bin` | 54949 | `f2dc69b90bd373506e4029d09df7490e67f3f801a69863e59915fd6f8da1d562` |
| [M3 cap](messages/m3-cap.json) | `runs/3/response-9-1.bin` | 21530 | `7d6e531186186ba37cc42388d2d6f5680115dc3d56d23387ee3ccae76082a7b1` |
| [Incomplete replacement](messages/m3-replace-missing-citations.json) | `runs/3/call-19.json` | 1030 | `e480c004bea835f76e0deaea7b2a56a6c2d3a43a0051e8ebfaf0d90765f7254c` |
| [Near-limit text](messages/m3-near-limit.txt) | `log/11.json`'s decoded `body.text`, UTF-8 without a trailing LF | 182 | `e2c5ac7ed5659d93d7150e7ba1a85703bf7a016efdf95f8451843a5ed2eb3a95` |

The [captured cap case](../cases_captured.py) serves both complete cap bodies,
each containing one signed thinking block and no tool call. Its synthetic
two-placement schedule records a supplied account, interrupts, re-enters and
reads that same entry, attempts the captured replacement, then checks the
unchanged entry and payload before the final cap. The replacement changes only
its audit-specific entry handle; its omitted `citations` must produce
`fields_invalid` with unchanged-answer effects and the precise missing-field
description. The complete refusal is observed in the next provider request.

Synthetic charges leave 6170 output tokens for the final response, matching the
captured M3 cap. The test derives every request cap and the single transmitted
near-limit notice from its own ledger; the notice self-test separately pins the
original M3 text and numbers. These are two synthetic placements, not a replay
of the original three-placement history or its full charge schedule.

The original final `max_tokens` response must leave an interrupted ending even
when no output remains; advice then offers only close. A differing control
changes only that stop reason to `end_turn`, which ends with `limit_reached`.
An invariance control changes only the uninterpreted `thinking_tokens`
diagnostic to 1; usage and ending stay unchanged. Neither capped response spends
the ordinary reminder. Sabotage controls reset cumulative limits, hide the old
ledger or omit refusal effects; each must fail its named check.

The original thinking and proposed replacement text are opaque fixture content,
not expected answers to the synthetic question. Expected account bytes, counts
and endings come from the supplied script and interface contract. Coverage ends
with stopped, unsubmitted audits and retained work; it establishes neither a
better response cap nor live continuation, cancellation, delivery or close.

### M3 ordinary ending and citation recovery

The following originals come from the 2026-11-15 `claude-haiku-5-5` encounter,
effort omitted. The export is
`.scratch/readiness-m3-live-reminder-02/container/m3-reminder/export-0004/work.tar`:
788480 bytes, SHA-256
`0c9551f2e56266d5e6eaf9337bb5b61bf2afb4376306af6c880a9c650c9e35c4`.
Response and call paths below are relative to
`private/archive/audits/akzdcvcj6ajscilan/`; they are Stewart-owned captures.
The material comes from the separate pre-intake input witness.

| Fixture | Original member | Bytes | SHA-256 |
| --- | --- | --- | --- |
| [Ordinary ending](messages/m3-ordinary-ending.json) | `runs/1/response-4-1.bin` | 1555 | `ee1df6b283c322424e116e2e9a692a44ebd27e07546d5bd1928f27f407753728` |
| [Invalid citation](messages/m3-citation-invalid.json) | `runs/2/call-5.json` | 1187 | `bff4227f27d85e7991fa9e05d33dd35904c2d9b2a723eeeeb4fa842dc53291ff` |
| [Corrected citation](messages/m3-citation-corrected.json) | `runs/2/call-6.json` | 1167 | `1a6ea9ccc7d0936579e1734a30300f972e088e6e6f5fb6ad5fb816a8fd260b88` |
| [Supplied report](messages/m3-supplied-report.txt) | `private/evidence/input-witness/materials/context/supplied-report.txt` | 591 | `86b5be5c14dad39f2facfb70607658bdc637f2df5a678e78e70972c459b9296d` |

`c13.captured-reminder` serves the complete ordinary-ending response after
recording three supplied entries. Its reported charge is 6660 input and 248
output tokens. The fake provider witnesses the resulting reminder in a request,
then returns retryable HTTP errors until the placement interrupts. The next
placement re-enters with the same entries and reminder state. The original live
interruption was a signal before any request byte was written; its reminder
transmission was `unknown`. The synthetic HTTP sequence independently exercises
known transmission and does not change that historical result.

Both captured replacement calls change only their entry handle. The invalid
call combines the whole-file range `[0,591)` with a shorter quote. Refusal must
preserve every entry, the revision and the old account bytes. Its captured
correction removes that incorrect range, keeping the three unique quotes; a
fresh invocation ID distinguishes the new call. The test checks exact citation
annotations, version 2 of the same entry, both retained payload versions and
the complete prepared selection against independent expected bytes.

A synthetic prose ending then ends authoring without submission or another
reminder. In the differing variant, only the first response's stop reason is
changed to `max_tokens`; the reminder remains available until the continuation
ends. Changing only its uninterpreted thinking-count diagnostic leaves the
original path invariant. Every variant uses the reminder once and produces the
same prepared selection. Sabotage controls reset the reminder allowance, hide a
re-entry item or remove the superseded payload. The original live continuation
submitted; it supplies no evidence for the synthetic prose-ending branch.
These comparisons do not exercise live interruption, delivery or close.

## `runtime/`: C1 surface-observer captures

These inputs come from the 2026-11-13 native C1 supplied-surface encounter,
CLI `2.1.322`, model `claude-haiku-5-5`, effort omitted. Originals live under
`.scratch/readiness-c1-01/packet/observation/cases/`; the
[qualification index](../../qualified.md#readiness-c1-01) binds that retained
encounter. These are separately observed harness/helper bytes, not provider
HTTP capture. Authentication is the already sanitized three-member receipt,
not raw authentication output.

| Fixture | Original relative path / slice | Original bytes | Original SHA-256 |
| --- | --- | ---: | --- |
| [`c1-init.json`](runtime/c1-init.json) | `positive/stdout.bin line 1` | 2730 | `476a551295d1d5be167af4574d3586c2e58ec7241837c85267c45d302e1ff4b9` |
| [`c1-rate.json`](runtime/c1-rate.json) | `positive/stdout.bin line 3` | 403 | `ca9dca9a62370cd22670a82f6e5b6d45043b5853a778d55e4aed497b6fd80d5b` |
| [`c1-result-positive.json`](runtime/c1-result-positive.json) | `positive/stdout.bin final line` | 2422 | `e16b4d239f22c402580fe7bd71b32d462dbd5e3bdf432ed3eff01f5fec5f7199` |
| [`c1-result-closed-gate.json`](runtime/c1-result-closed-gate.json) | `closed-gate/stdout.bin final line` | 2731 | `05b52ac15dc3998925323784730abb29f2864a0a6690aaa23a06149cbbb4a84b` |
| [`c1-hook.json`](runtime/c1-hook.json) | `positive/hook-0001-received.bin` | 655 | `8e7a3de2386fd55678a9924b90ccedb1a4b80ae77a6238a103d9e5682763ef5c` |
| [`c1-auth.json`](runtime/c1-auth.json) | `positive/authentication.json` | 124 | `be1c88efda8ff76a7f5ade3ea2928a1b22b41c7d74f9ff47bc78a3784defd676` |
| [`c1-mcp.jsonl`](runtime/c1-mcp.jsonl) | `positive/mcp-received.bin` | 1155 | `120d2aabbc2653d5618f77debcc3e3e2ecc7fb5a59b1d83b9cd3eaa74bce7bd6` |

Line slices include their terminating LF. The positive stdout is 8374 bytes,
SHA-256 `dbbee298a581558f684c10acf62788703755284535957a196dea7c7e7ef79ed0`;
the closed-gate stdout is 11374 bytes,
SHA-256 `088a77b8479fbc55c5d46ffe3cd9e7bdf1a43aa802f735d23513cc8afd8faa5e`.

The stored startup changes only `cwd` and `original_cwd` to
`/synthetic/workspace`. The hook changes only `cwd` to that path and
`transcript_path` to `/synthetic/transcript.jsonl`. Authentication changes only
`configDirectory` to `/synthetic/no-credentials`. Both results replace only
`credential_expires_at` with `2099-01-01T00:00:00.000Z`; no real expiry is claimed.
Rate and MCP bytes are unchanged. The observer self-test pins every stored size
and digest. No fixture opens a captured or placeholder path.

The [observer controls](../claude_code_observer.py) bind startup session, version,
model, tool inventory and working directory to each synthetic case. Other
session-bearing records take that session; the hook takes the case directory,
and authentication takes the bound configuration directory. The MCP stream
preserves discovery, initialization, notification, inventory and the correlated
tool-use/progress metadata. Its refused pre-initialization discovery does not
prevent the subsequent valid handshake. Closed-gate cases omit the denied MCP
call and use the captured closed-gate result. The synthetic schedule does not
replay the complete assistant conversation or original timing.

The positive and fragmented invariance cases observe the same one fixture
effect and the literal checkpoint: 2 turns, 4 input, 4819 cache creation,
4692 cache read and 161 output tokens. Overlapping per-model fields are not
added. Changing one output count changes only that reported count; changing
cost leaves it invariant; removing a required usage field leaves it unknown.
The captured rate event allows subscription use while reporting overage rejected.
Changing only quota status, overage-in-use, or adding overage-enabled causes the
specified stop; changing only result `is_error` also stops. These mutated events
are synthetic negative controls, not observed live rejection or overage forms.

Control sender witnesses remain outside observer captures. Rehearsal evidence
includes the exact fixture files. This establishes observer behavior on these
forms, not real cap enforcement, provider completeness, billing, authentication
execution or process stopping. Those distinctions also apply to the copied
result prose and reported costs.

### C4/C5 authoring and error forms

`runtime-captured-authoring` uses these exact captured calls and one complete
conversation result from native CLI `2.1.322`, model `claude-haiku-5-5`, effort
omitted. C4 ran on 2026-11-14; C5 on 2026-11-15. Calls are Stewart-owned captures;
the C5 user frame is captured harness output, not provider HTTP. Materials are
from the separately frozen pre-intake packet inputs.

The table's origin prefixes are:

- `C4`: `.scratch/readiness-c4-01/long/packet/closure/service-archive/audits/akyhrcucf3yvc5zkh/runs/1/`
- `C5-checklist`: `.scratch/readiness-c5-01/checklist/archive/audits/aplifuihi4h2xrht5/runs/1/`
- `C5-long`: `.scratch/readiness-c5-01/long-entry/archive/audits/a7ygtsnnhccz3vz5y/runs/1/`
- Material paths: the matching C5 arm's `packet/inputs/submission/materials/`.

| Fixture | Origin | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| [c4-account.json](runtime/c4-account.json) | `C4 / call-150.json` | 2121 | `053812aae916a50722882c238849af911c25b6628f401bb7c83261a1fe7f5328` |
| [c4-replace-missing.json](runtime/c4-replace-missing.json) | `C4 / call-151.json` | 1930 | `ef69aa5c530fe963dd5ef898673f102d5f2bdff454d9f4b460bf98368cc823d6` |
| [c4-replace-corrected.json](runtime/c4-replace-corrected.json) | `C4 / call-152.json` | 1945 | `b8904a9aea51fbaa24a8b1b6459e68d32fa1e35cb96eca131ad4e3f368476bdb` |
| [c5-quote-call.json](runtime/c5-quote-call.json) | `C5-checklist / call-50.json` | 1391 | `8bc749174d6ed1c3cde45f52f74acb027cc6d7126d391be98b910f68ee3928a2` |
| [c5-replace-account.json](runtime/c5-replace-account.json) | `C5-long / call-102.json` | 29128 | `c773ec95caccd20e1fe9b07d54812746a9da628e49b825293f01d6e836941c62` |
| [c5-quote-result.json](runtime/c5-quote-result.json) | `C5-checklist / runtime-447-stdout.bin (complete LF-terminated user frame)` | 1256 | `c4d932e271161c9e2de5e009307c9b117b5122efab43a9b403863b6aa459a180` |
| [authoring-materials/R/frsr.R](runtime/authoring-materials/R/frsr.R) | `C5-checklist material R/frsr.R` | 7800 | `5a96c182f9f322e9d04426c860c2f281d3f23d73ec8ede1993fd8ec5e14e41b0` |
| [authoring-materials/00-review-rules.txt](runtime/authoring-materials/00-review-rules.txt) | `C5-long material 00-review-rules.txt` | 1073 | `5da12479c3a190c1b3864c2ec65bb09119d326e4e3b16f3be7438cf3ce976487` |
| [authoring-materials/R001-claim.txt](runtime/authoring-materials/R001-claim.txt) | `C5-long material R001-claim.txt` | 390 | `7a43df94f3dff98410a76eccb1a9c5e9b4cc3fbc3be09b2e8b25f5607ea35f1e` |
| [authoring-materials/R001-receipt.txt](runtime/authoring-materials/R001-receipt.txt) | `C5-long material R001-receipt.txt` | 418 | `3edccbfd1c4b0a931dc9509830eb1c22b97187912604221caf807b289e63775a` |
| [authoring-materials/R002-receipt.txt](runtime/authoring-materials/R002-receipt.txt) | `C5-long material R002-receipt.txt` | 399 | `53b97e0e54f98326b622911737fc813e2f65fa944bae120350e2774f554ff340` |
| [authoring-materials/R003-receipt.txt](runtime/authoring-materials/R003-receipt.txt) | `C5-long material R003-receipt.txt` | 426 | `dd7dba83039e7a43e84e764f9b036aee8df3ccdd8ce2905e9a7f8b1a0fe8df54` |
| [authoring-materials/R004-claim.txt](runtime/authoring-materials/R004-claim.txt) | `C5-long material R004-claim.txt` | 390 | `f80dce402282d4f3a0d7f14be975529d2515946d7fee3ee1cc8c53403692b9db` |
| [authoring-materials/R004-receipt.txt](runtime/authoring-materials/R004-receipt.txt) | `C5-long material R004-receipt.txt` | 418 | `801bac2f6439bd9d8898a0e8138a3c74c470712a46df7e0a8de064bfb367a49b` |
| [authoring-materials/R005-receipt.txt](runtime/authoring-materials/R005-receipt.txt) | `C5-long material R005-receipt.txt` | 420 | `cd5032e8b9c0b1bec8685852c3bfa000e2b180371c8e6dbfa987c3a97be0fc53` |
| [authoring-materials/R006-claim.txt](runtime/authoring-materials/R006-claim.txt) | `C5-long material R006-claim.txt` | 390 | `f801a3b8460ee9a542dd7f49aae4d5388ca66ea06dd30cf5eba6fb9677695e61` |
| [authoring-materials/R006-receipt.txt](runtime/authoring-materials/R006-receipt.txt) | `C5-long material R006-receipt.txt` | 418 | `5f6e37340feb19efde8c30ef3c8e052a4a07eb3ab2da06bac17eb67b1ea0b398` |
| [authoring-materials/R048-receipt.txt](runtime/authoring-materials/R048-receipt.txt) | `C5-long material R048-receipt.txt` | 419 | `f5213f294bdf6a25828cc1ed28225e2ae5dd53f15195e5fd84d066130b1b9d55` |

The script reuses each call's `arguments`, changing only a replacement's exact
entry handle. Fresh assistant, hook and MCP identifiers correlate the new calls;
original RPC envelopes are retained fixtures, not replayed request identities.
The C5 refusal is compared byte for byte with the captured 344-byte complete
text (SHA-256 `4d287a2987efce5a306249415d9028f3ab98aa21f9dbac7900dfc91d8af4af09`).
Its conversation frame changes only session ID and the two tool-use identity
fields. The auxiliary `Error: ` string remains unchanged and is not used as
the conversation result.

The synthetic sequence records one C4 account, refuses its replacement without
`citations`, reads the old version, then applies the captured correction with
`citations: []`. C5's missing-quote call must refuse without an edit. The long
C5 replacement then creates version 3 of the same entry. A fresh call deliberately
targets the superseded version 2 and must refuse with `stale_entry`; it cannot
overwrite the long account. Reads and all three retained payloads must be exact.
Independent citation annotations, the complete prepared selection and delivered
`answer.json` come from the supplied material and call bytes. Close preserves
the delivered package. The peer remains alive after explicit submission, so its
own exit or an ordinary result cannot stand in for Stewart stopping it.

A second variant changes only the missing-quote conversation content from the
captured string to a one-text-block array; it must deliver the same answer.
A differing variant changes only its error flag to false and keeps the peer
alive. Stewart must interrupt for a reply mismatch, preserve version 2 and
publish no seal. The three variants retain external input/output/MCP witnesses,
correlated hook calls, and observed absent authentication/model groups.

These are combined synthetic sequences, not replays of either full live audit.
Captured account prose is opaque authored content, not a correctness claim about
the selected synthetic question. C4's original correction was entry 49 at
revision 51, and C5's original long replacement was entry 1 version 2. The new
sequence deliberately uses one entry and three versions. It does not establish
live near-limit partial submission, timing, model behavior or provider usage.

## `citations/`: M1/C2/C3 recovery operands

These are exact captured calls from M1 direct (Messages API, 2026-11-13), C2
ordinary (native CLI, 2026-11-13), and C3 pages (native CLI, 2026-11-13). All used
`claude-haiku-5-5`, effort omitted; the two CLI encounters used `2.1.322`.
Calls are Stewart-owned capture, not an independent provider wire witness.
Material bytes come from the separate pre-intake inputs. M1's independent
input witness has exactly the same 175-byte `src/a.py` as C2's packet.

Origin prefixes:

- `M1`: `.scratch/readiness-m1-live-direct-01/container/m1-direct/export-0002/work.tar`,
  member `private/archive/audits/aujahvrflxkzbthr2/runs/1/`.
- `C2`: `.scratch/readiness-c2-01/open-ordinary/packet/closure/service-archive/audits/alwuy5pjrhn2vlugq/runs/1/`.
- `C3`: `.scratch/readiness-c3-01/packet/closure/service-archive/audits/a3gyjpm2wnl2vnrtj/runs/1/`.
- Material paths: the corresponding packet's `inputs/submission/materials/`.

The M1 export is 706560 bytes, SHA-256
`311e5dda499fd40c643facb6a937c33536a229a70f397ad9a9ac656ead9b248f`.

| Fixture | Origin | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| [m1-invalid.json](citations/m1-invalid.json) | `M1 / call-7.json` | 553 | `7921ec111192371e6b680bc8a455ae684c2bb47a94b519fb53d65e65b3ef237d` |
| [m1-corrected.json](citations/m1-corrected.json) | `M1 / call-13.json` | 407 | `a46aaa88d900600cd71c080ffbfb58b2f84954c74c47f4702ffb13d15c68e221` |
| [c2-invalid.json](citations/c2-invalid.json) | `C2 / call-8.json` | 801 | `59c95bcf98e1cdb247e10d98267b9997cfbf19a8d024224eae809fd5dd99af68` |
| [c2-corrected.json](citations/c2-corrected.json) | `C2 / call-16.json` | 711 | `7a9977e1c379e2071242d58d84f9c982ccf9f6013d0d9c60685709de6b2346ca` |
| [c3-invalid.json](citations/c3-invalid.json) | `C3 / call-5.json` | 607 | `847bc04962038544049e39a208c48f348076af37ed067f4d984af53e499b282f` |
| [c3-corrected.json](citations/c3-corrected.json) | `C3 / call-9.json` | 587 | `276dd05080de15a031453a0dd27370bf530302daccdba00359397ec647105d97` |
| [a.py.txt](citations/a.py.txt) | `C2 material src/a.py` | 175 | `3fed093a5696428b7440ae3a0f93d2bd3bc93084b495fc3ec6297ab78c23afce` |
| [control.txt](citations/control.txt) | `C3 material control.txt` | 49152 | `947ae167c6e71f036d5c603c3f273706c2252b1b18d381bbf7da3045da49e0d2` |

[`c14.captured-citations`](../cases_citation_captures.py) supplies M1's complete
Messages tool blocks unchanged. It projects C2/C3 MCP calls into Messages tool
blocks using their tool names, correlated tool-use IDs and exact raw argument
objects. The original MCP envelopes and metadata remain in these fixture files;
this comparison exercises shared citation behavior through Messages, not MCP
framing or real-harness behavior.

Each synthetic audit first records a control account. The original malformed
range/quote call must refuse at citation 0, preserve that account and revision,
and retain its exact raw block and error result. The captured corrected call
must then add the expected observation with independently derived annotations.
The prepared selection, delivered `answer.json` and every retained payload are
compared with the supplied inputs. Captured prose remains opaque authored text,
not an oracle about the subject of the synthetic question.

The differing variant changes only the invalid call's `quote` to the exact
bytes of its unchanged range. That call must now add an observation, so this
variant deliberately has one more entry and revision. The invariance variant
changes only top-level input-member order: it must preserve the refusal and
produce the same final answer as the original. Each origin has all three
variants. Controls omit refused capture, omit refusal effects or add a support
grade to the recorded citation; each must fail its named check.

### C4 partial account in the timing comparison

The existing `runtime-near-limit` case uses
[`runtime/c4-partial-account.json`](runtime/c4-partial-account.json), the exact
C4 short-placement call from 2026-11-14, CLI `2.1.322`, `claude-haiku-5-5`,
effort omitted. Its origin is
`.scratch/readiness-c4-01/short/packet/closure/service-archive/audits/ah3m7bxzpowsvmtfn/runs/1/call-53.json`:
931 bytes, SHA-256 `6b1cfbfd4c6d179d195a91489473ff7dcbb463b6f222e2535ad8d45caedbefe0`.

The script sends its complete argument object unchanged with fresh MCP identity.
The literal label and 708-byte account must survive the short/long timing
comparison, explicit continuation and verified delivery/close. The comparison
records one copy before its synthetic observation window; the original audit
added this checkpoint after sixteen earlier accounts. This is not a replay of
that history or evidence that the model would make the same decision at a
new deadline. Original notice provenance and the timing comparison's limits are
in the [runtime driver guide](../CLAUDE-CODE.md).

## `os/`: local environment and process observations

[Local OS fixtures](os/README.md) preserve complete NUL-delimited environment
output, owned-group and denied signal-0 observations, and Linux procfs
readable/denied comparisons. Their controls keep the observer mechanisms and
synthetic replay limits separate.

## `tls/`: TEST-ONLY certificates and keys

These certificates and their **private keys are deliberately published**. They
exist only so the acceptance driver's fake Messages API can serve HTTPS on
loopback and through its CONNECT proxy. Nothing outside the driver may trust
them; the release binary never does (it trusts only the web PKI roots built into
it). The test build trusts `testonly-ca.pem` only when the driver passes it as
`STEWART_TEST_TLS_ROOT` (INTERFACE Appendix C.1).

| File | What it is |
| --- | --- |
| `testonly-ca.pem`, `.key` | The test CA, `CN=Stewart acceptance driver TEST-ONLY CA`. Its certificate is the file given as `STEWART_TEST_TLS_ROOT`. |
| `testonly-provider.pem`, `.key` | Server certificate issued by the test CA for `provider.test`, `localhost` and `127.0.0.1`: the fake provider's HTTPS identity, directly and behind the proxy. |
| `testonly-wrongname.pem`, `.key` | Issued by the test CA for `other.test` only: a fake-provider self-test name-mismatch fixture. |
| `testonly-expired.pem`, `.key` | Issued by the test CA for the right names, valid only during 2001: a fake-provider self-test expiry fixture. |
| `testonly-other-ca.pem`, `.key` | A second CA that is never given to the binary. |
| `testonly-untrusted.pem`, `.key` | Issued by the second CA for the right names: an untrusted-issuer control. |
| `VERSION`, `SHA256SUMS` | The OpenSSL version that made them and the files' digests. |

All keys are ECDSA P-256 in PKCS#8 PEM. The certificates are X.509 v3; the leaves
have the subject alternative names above and `serverAuth` extended key usage.
Both CAs and every leaf except `testonly-expired.pem` are valid from
2025-01-01 00:00:00 UTC to 2125-01-01 00:00:00 UTC. The expired leaf is valid from
2001-01-01 00:00:00 UTC to 2001-12-31 00:00:00 UTC. The test clock must therefore
be within the ordinary certificates' interval and after the expired leaf's end.

The [fake-provider self-test](../fake_provider.py) uses a Python SSL client to
check wrong-name, expired, untrusted-issuer and other-root rejection. These
checks test the fixture and fake-provider machinery. The
[`c1.tls-proxy` acceptance case](../cases_run.py) exercises the Stewart binary
with the valid provider and untrusted-issuer certificates; it does not exercise
the binary with the wrong-name or expired fixtures.

They were made by [`make-tls.sh`](make-tls.sh), on 2026-10-30 with the OpenSSL
named in `tls/VERSION`:

```sh
sh apparatus/driver/testdata/make-tls.sh     # OpenSSL 3.4 or later (-not_before/-not_after)
```

The script regenerates every file (new keys, new serial numbers), checks that the
provider and wrong-name leaves verify against the test CA and that the untrusted
leaf does not, and writes `SHA256SUMS`. Keep the generator's names, issuers,
validity intervals and usages when replacing fixtures; commit the regenerated
set together.
