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
