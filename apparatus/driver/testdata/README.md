# Driver test data

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
