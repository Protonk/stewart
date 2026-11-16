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
