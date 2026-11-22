# Linux release signature verification

These are the complete stdout, stderr and exit status of three public-key
operations on Linux aarch64 in a Debian 13 container, captured on 2026-11-21
UTC. The input was Claude Code 2.1.322's public release key, detached signature
and manifest captured in the original Mac checkout's
`.scratch/claude-code-pin-01/`. The manifest SHA-256 is
`05d2eff648bb528c1479c719bb8eca9a759657631e285d03aaf37fe779173f1c`.

- `dearmor` converted the ASCII release key into a binary keyring in a fresh
  private directory using `gpg --no-options --batch --dearmor`.
- `signature` ran `gpgv` 2.4.7 with that keyring, detached signature and
  original manifest, with status records on stdout. It exited 0 and named
  the pinned signer in its `VALIDSIG` record.
- `signature-refused` used the same command, keyring and signature, with
  the manifest's version changed from `2.1.322` to `2.1.323`. The one changed
  byte produced SHA-256
  `fa8b186182d2257124c05edf2c46cfd74629f4a5c70b063c44ec847cc861cb58`.
  The verifier reported a bad signature and exited 1.

The offline tests pin the captures' sizes and digests and replay their process
results with synthetic installation and review records. The signer parser
also exercises a changed fingerprint, a missing status record, a signing
subkey and CRLF. Replaying these streams exercises parsing, retention and
refusal. Executable verification requires comparing its bytes with the
appropriate checksum from the authenticated manifest.
